# =============================================================================
# FGA CRM - Tests Lead Engine : detecteur de signaux + Signal Inbox
# =============================================================================
"""Couvre le detecteur (funding_detected / mmf_gap, dedup, exclusions) et
l'API /lead-engine (liste + stats, transitions DC5, RBAC, kill switch).

Regle metier verifiee : la levee ne cree qu'un funding_detected (-> audit),
le mmf_gap ne vient que d'un score d'audit < seuil.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.activity import Activity
from app.models.company import Company
from app.models.deal import Deal
from app.models.organization import Organization
from app.models.user import User

RECENT = date.today() - timedelta(days=5)
OLD = date.today() - timedelta(days=120)


async def _seed_company(db: AsyncSession, org_id: uuid.UUID, **kwargs) -> Company:
    company = Company(
        name=kwargs.pop("name", f"Startup {uuid.uuid4().hex[:6]}"),
        organization_id=org_id,
        **kwargs,
    )
    db.add(company)
    await db.commit()
    await db.refresh(company)
    return company


async def _seed_audit(
    db: AsyncSession, org_id: uuid.UUID, company_id: uuid.UUID,
    user_id: uuid.UUID, score: int,
) -> None:
    db.add(
        Activity(
            organization_id=org_id,
            type="audit",
            subject="Audit messaging",
            user_id=user_id,
            company_id=company_id,
            metadata_={"audit_type": "messaging", "messaging_score": str(score)},
        )
    )
    await db.commit()


async def _scan(client: AsyncClient, headers: dict) -> dict:
    r = await client.post("/api/v1/lead-engine/scan", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["created"]


async def _signals(client: AsyncClient, headers: dict, **params) -> dict:
    r = await client.get("/api/v1/lead-engine/signals", params=params, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Detecteur — funding_detected (P2 : levee -> audit du message)
# ---------------------------------------------------------------------------

async def test_scan_creates_funding_signal(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User,
):
    company = await _seed_company(
        db_session, test_user.organization_id,
        name="Sopht", startup_radar_id="sr-123",
        funding_date=RECENT, funding_amount=4_500_000, funding_series="Série A",
    )

    created = await _scan(client, auth_headers)
    assert created == {"funding_detected": 1, "mmf_gap": 0}

    body = await _signals(client, auth_headers)
    assert body["total"] == 1
    signal = body["items"][0]
    assert signal["signal_type"] == "funding_detected"
    assert signal["status"] == "new"
    assert signal["company_id"] == str(company.id)
    assert signal["payload_json"]["company_name"] == "Sopht"
    assert signal["payload_json"]["startup_radar_id"] == "sr-123"
    assert signal["payload_json"]["funding_amount"] == 4_500_000
    assert body["stats"]["new_funding"] == 1


async def test_scan_skips_old_funding_and_non_auditable(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User,
):
    org_id = test_user.organization_id
    # Levee trop ancienne
    await _seed_company(db_session, org_id, funding_date=OLD, startup_radar_id="sr-old")
    # Pas de lien SR (audit impossible -> pas d'action possible sur le signal)
    await _seed_company(db_session, org_id, funding_date=RECENT)
    # Investisseur (non auditable)
    await _seed_company(db_session, org_id, funding_date=RECENT, startup_radar_id="inv:42")

    created = await _scan(client, auth_headers)
    assert created == {"funding_detected": 0, "mmf_gap": 0}


async def test_scan_skips_company_with_open_deal(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User,
):
    """Une societe deja en pipeline (deal ouvert) n'est pas re-signalee ;
    un deal ferme (won/lost) ne bloque pas."""
    org_id = test_user.organization_id
    in_pipeline = await _seed_company(
        db_session, org_id, startup_radar_id="sr-a", funding_date=RECENT,
    )
    closed = await _seed_company(
        db_session, org_id, startup_radar_id="sr-b", funding_date=RECENT,
    )
    db_session.add(Deal(title="Ouvert", organization_id=org_id,
                        company_id=in_pipeline.id, stage="proposal"))
    db_session.add(Deal(title="Perdu", organization_id=org_id,
                        company_id=closed.id, stage="lost"))
    await db_session.commit()

    created = await _scan(client, auth_headers)
    assert created["funding_detected"] == 1
    body = await _signals(client, auth_headers)
    assert body["items"][0]["company_id"] == str(closed.id)


# ---------------------------------------------------------------------------
# Detecteur — mmf_gap (P1 : seul declencheur d'outreach)
# ---------------------------------------------------------------------------

async def test_scan_creates_mmf_gap_signal(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User,
):
    org_id = test_user.organization_id
    company = await _seed_company(
        db_session, org_id, name="Acme", startup_radar_id="sr-9",
        funding_date=RECENT, funding_amount=2_000_000,
    )
    await _seed_audit(db_session, org_id, company.id, test_user.id, score=24)

    created = await _scan(client, auth_headers)
    # La levee recente cree AUSSI un funding_detected — les deux coexistent.
    assert created == {"funding_detected": 1, "mmf_gap": 1}

    body = await _signals(client, auth_headers, signal_type="mmf_gap")
    assert body["total"] == 1
    signal = body["items"][0]
    assert signal["payload_json"]["audit_score"] == 24
    # Qualificateur de solvabilite toujours joint au signal d'outreach.
    assert signal["payload_json"]["funding_amount"] == 2_000_000


async def test_scan_ignores_audit_above_threshold(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User,
):
    org_id = test_user.organization_id
    company = await _seed_company(db_session, org_id)
    await _seed_audit(db_session, org_id, company.id, test_user.id, score=60)

    created = await _scan(client, auth_headers)
    assert created["mmf_gap"] == 0


async def test_scan_dedup_window(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User,
):
    """Un signal deja emis (quel que soit son statut) n'est pas recree."""
    org_id = test_user.organization_id
    await _seed_company(
        db_session, org_id, startup_radar_id="sr-dd", funding_date=RECENT,
    )
    first = await _scan(client, auth_headers)
    assert first["funding_detected"] == 1

    # 2e scan immediat : dedup.
    assert (await _scan(client, auth_headers))["funding_detected"] == 0

    # Signal ignore -> toujours pas recree (memorise, pas de re-nag).
    body = await _signals(client, auth_headers)
    sid = body["items"][0]["id"]
    r = await client.patch(
        f"/api/v1/lead-engine/signals/{sid}",
        json={"status": "ignored"}, headers=auth_headers,
    )
    assert r.status_code == 200
    assert (await _scan(client, auth_headers))["funding_detected"] == 0


# ---------------------------------------------------------------------------
# API — transitions (DC5), RBAC, isolation, kill switch
# ---------------------------------------------------------------------------

async def test_patch_transitions(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User,
):
    org_id = test_user.organization_id
    await _seed_company(db_session, org_id, startup_radar_id="sr-t", funding_date=RECENT)
    await _scan(client, auth_headers)
    sid = (await _signals(client, auth_headers))["items"][0]["id"]

    # new -> actioned (action tracee dans le payload)
    r = await client.patch(
        f"/api/v1/lead-engine/signals/{sid}",
        json={"status": "actioned", "action_kind": "audit"}, headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "actioned"
    assert r.json()["payload_json"]["action"]["kind"] == "audit"

    # actioned -> ignored : transition invalide (etat terminal)
    r2 = await client.patch(
        f"/api/v1/lead-engine/signals/{sid}",
        json={"status": "ignored"}, headers=auth_headers,
    )
    assert r2.status_code == 422


async def test_patch_ignored_reopen(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User,
):
    org_id = test_user.organization_id
    await _seed_company(db_session, org_id, startup_radar_id="sr-r", funding_date=RECENT)
    await _scan(client, auth_headers)
    sid = (await _signals(client, auth_headers))["items"][0]["id"]

    for status, expected in (("ignored", 200), ("new", 200), ("ignored", 200)):
        r = await client.patch(
            f"/api/v1/lead-engine/signals/{sid}",
            json={"status": status}, headers=auth_headers,
        )
        assert r.status_code == expected, r.text


async def test_signals_org_isolation(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    """Un signal d'une autre org est invisible (GET) et intouchable (PATCH 404)."""
    from app.models.lead_engine import LeadSignal

    org_b = Organization(id=uuid.uuid4(), name="Org B", slug=f"b-{uuid.uuid4().hex[:8]}")
    db_session.add(org_b)
    await db_session.flush()
    foreign = LeadSignal(
        organization_id=org_b.id, signal_type="mmf_gap",
        payload_json={"company_name": "Ailleurs"}, status="new",
        dedup_key=f"mmf:{uuid.uuid4()}",
    )
    db_session.add(foreign)
    await db_session.commit()

    body = await _signals(client, auth_headers)
    assert body["total"] == 0

    r = await client.patch(
        f"/api/v1/lead-engine/signals/{foreign.id}",
        json={"status": "ignored"}, headers=auth_headers,
    )
    assert r.status_code == 404


async def test_rbac_sales_forbidden(client: AsyncClient, sales_headers: dict):
    for method, url in (
        ("get", "/api/v1/lead-engine/signals"),
        ("post", "/api/v1/lead-engine/scan"),
    ):
        r = await getattr(client, method)(url, headers=sales_headers)
        assert r.status_code == 403, f"{method} {url}: {r.status_code}"


async def test_scan_kill_switch(
    client: AsyncClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "lead_engine_enabled", False)
    r = await client.post("/api/v1/lead-engine/scan", headers=auth_headers)
    assert r.status_code == 503
