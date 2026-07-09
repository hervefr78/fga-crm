# =============================================================================
# FGA CRM - Tests Lead Engine : detecteur de signaux + Signal Inbox
# =============================================================================
"""Couvre le detecteur (funding_detected / mmf_gap / inbound_new, dedup,
exclusions) et l'API /lead-engine (liste + stats, transitions DC5, draft
outreach-v1, queue priorisee, funnel, RBAC, kill switch).

Regle metier verifiee : la levee ne cree qu'un funding_detected (-> audit),
le mmf_gap ne vient que d'un score d'audit < seuil, et SEUL le mmf_gap
peut etre drafte (l'outreach ne se declenche jamais sur une levee).
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
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.organization import Organization
from app.models.user import User
from app.schemas.ai_workflows import OutreachDraftOutput
from app.services.ai_workflows import outreach

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
    assert created == {"funding_detected": 1, "mmf_gap": 0, "inbound_new": 0}

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
    assert created == {"funding_detected": 0, "mmf_gap": 0, "inbound_new": 0}


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
    assert created == {"funding_detected": 1, "mmf_gap": 1, "inbound_new": 0}

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


# ---------------------------------------------------------------------------
# Detecteur — inbound_new (P3 : contact entrant a qualifier)
# ---------------------------------------------------------------------------

async def _seed_inbound_contact(
    db: AsyncSession, org_id: uuid.UUID, **kwargs
) -> Contact:
    contact = Contact(
        first_name=kwargs.pop("first_name", "Lea"),
        last_name=kwargs.pop("last_name", f"Martin-{uuid.uuid4().hex[:4]}"),
        organization_id=org_id,
        source=kwargs.pop("source", "nomo-ia"),
        **kwargs,
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


async def test_scan_creates_inbound_signal(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User,
):
    org_id = test_user.organization_id
    contact = await _seed_inbound_contact(
        db_session, org_id, email="lea@beams.fr", source="nomo-ia",
    )
    # Contact deja qualifie : pas de signal
    await _seed_inbound_contact(db_session, org_id, ai_routing="standard")
    # Source non-inbound : pas de signal
    await _seed_inbound_contact(db_session, org_id, source="linkedin")

    created = await _scan(client, auth_headers)
    assert created["inbound_new"] == 1

    body = await _signals(client, auth_headers, signal_type="inbound_new")
    signal = body["items"][0]
    assert signal["payload_json"]["contact_id"] == str(contact.id)
    assert signal["payload_json"]["lead_source"] == "nomo-ia"


# ---------------------------------------------------------------------------
# Draft outreach-v1 (POST /signals/{id}/draft)
# ---------------------------------------------------------------------------

FAKE_DRAFT = OutreachDraftOutput(
    subject="Votre message mesure a 24/75",
    body="Bonjour, votre clarte de message est mesuree a 24/75. "
         "Seriez-vous ouvert a un echange de 15 minutes ?",
    angle_rationale="MMF gap mesure, fonds recents en urgence.",
    personalization_used=["audit_score", "funding_date"],
)


@pytest.fixture()
def mock_outreach_llm(monkeypatch: pytest.MonkeyPatch):
    """Mock du LLM outreach + OpenAI configure (l'appel reel est toujours mocke)."""
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    calls = {"n": 0}

    async def _fake(schema_model, **kwargs):
        calls["n"] += 1
        return FAKE_DRAFT, {"input_tokens": 700, "output_tokens": 180}

    monkeypatch.setattr(outreach, "call_openai_structured", _fake)
    return calls


async def _seed_mmf_signal(
    client: AsyncClient, auth_headers: dict, db: AsyncSession,
    test_user: User, with_contact_email: str | None = "cto@acme.fr",
) -> tuple[dict, Company]:
    """Cree une societe + audit bas (+ contact optionnel) et scanne."""
    org_id = test_user.organization_id
    company = await _seed_company(
        db, org_id, name=f"Acme-{uuid.uuid4().hex[:4]}",
        startup_radar_id=f"sr-{uuid.uuid4().hex[:6]}",
        funding_date=RECENT, funding_amount=2_000_000,
    )
    await _seed_audit(db, org_id, company.id, test_user.id, score=24)
    if with_contact_email:
        db.add(Contact(
            first_name="Jean", last_name="CTO", email=with_contact_email,
            email_status="valid", organization_id=org_id, company_id=company.id,
        ))
        await db.commit()
    await _scan(client, auth_headers)
    body = await _signals(client, auth_headers, signal_type="mmf_gap")
    return body["items"][0], company


async def test_draft_outreach_persists_on_signal(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User, mock_outreach_llm,
):
    signal, _ = await _seed_mmf_signal(client, auth_headers, db_session, test_user)

    r = await client.post(
        f"/api/v1/lead-engine/signals/{signal['id']}/draft", json={}, headers=auth_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["subject"] == FAKE_DRAFT.subject
    assert body["contact_email"] == "cto@acme.fr"
    assert body["meta"]["prompt_version"] == "outreach-v1"
    assert mock_outreach_llm["n"] == 1

    # Draft persiste sur le signal (relu par l'inbox / la queue)
    got = await _signals(client, auth_headers, signal_type="mmf_gap")
    assert got["items"][0]["payload_json"]["draft"]["subject"] == FAKE_DRAFT.subject


async def test_draft_outreach_refused_on_funding_signal(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User, mock_outreach_llm,
):
    """Regle metier : une levee ne declenche JAMAIS un outreach."""
    await _seed_company(
        db_session, test_user.organization_id,
        startup_radar_id="sr-f", funding_date=RECENT,
    )
    await _scan(client, auth_headers)
    signal = (await _signals(client, auth_headers, signal_type="funding_detected"))["items"][0]

    r = await client.post(
        f"/api/v1/lead-engine/signals/{signal['id']}/draft", json={}, headers=auth_headers,
    )
    assert r.status_code == 422
    assert "MMF gap" in r.json()["detail"]
    assert mock_outreach_llm["n"] == 0


async def test_draft_outreach_requires_contact_with_email(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User, mock_outreach_llm,
):
    signal, _ = await _seed_mmf_signal(
        client, auth_headers, db_session, test_user, with_contact_email=None,
    )
    r = await client.post(
        f"/api/v1/lead-engine/signals/{signal['id']}/draft", json={}, headers=auth_headers,
    )
    assert r.status_code == 422
    assert "decideurs" in r.json()["detail"]
    assert mock_outreach_llm["n"] == 0


async def test_draft_outreach_kill_switch(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User, mock_outreach_llm, monkeypatch: pytest.MonkeyPatch,
):
    signal, _ = await _seed_mmf_signal(client, auth_headers, db_session, test_user)
    monkeypatch.setattr(settings, "ai_workflows_enabled", False)
    r = await client.post(
        f"/api/v1/lead-engine/signals/{signal['id']}/draft", json={}, headers=auth_headers,
    )
    assert r.status_code == 503
    assert mock_outreach_llm["n"] == 0


# ---------------------------------------------------------------------------
# Queue priorisee + funnel
# ---------------------------------------------------------------------------

async def test_queue_sorted_by_gap_then_funding(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User,
):
    """Gap le plus profond d'abord ; a gap egal, fonds les plus frais d'abord."""
    org_id = test_user.organization_id
    shallow = await _seed_company(db_session, org_id, name="Shallow")
    await _seed_audit(db_session, org_id, shallow.id, test_user.id, score=28)
    deep_old = await _seed_company(
        db_session, org_id, name="DeepOld", funding_date=date.today() - timedelta(days=25),
    )
    await _seed_audit(db_session, org_id, deep_old.id, test_user.id, score=10)
    deep_fresh = await _seed_company(
        db_session, org_id, name="DeepFresh", funding_date=RECENT,
    )
    await _seed_audit(db_session, org_id, deep_fresh.id, test_user.id, score=10)
    # Contact joignable sur DeepFresh uniquement
    db_session.add(Contact(
        first_name="A", last_name="B", email="a@deepfresh.fr",
        organization_id=org_id, company_id=deep_fresh.id,
    ))
    await db_session.commit()
    await _scan(client, auth_headers)

    r = await client.get("/api/v1/lead-engine/queue", headers=auth_headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    names = [i["signal"]["payload_json"]["company_name"] for i in items]
    assert names == ["DeepFresh", "DeepOld", "Shallow"]
    assert items[0]["contacts_with_email"] == 1
    assert items[1]["contacts_with_email"] == 0
    assert items[0]["has_draft"] is False


async def test_funnel_counts_by_play(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User, mock_outreach_llm,
):
    signal, _ = await _seed_mmf_signal(client, auth_headers, db_session, test_user)
    # Drafter puis marquer envoye (actioned/outreach)
    r = await client.post(
        f"/api/v1/lead-engine/signals/{signal['id']}/draft", json={}, headers=auth_headers,
    )
    assert r.status_code == 200
    r = await client.patch(
        f"/api/v1/lead-engine/signals/{signal['id']}",
        json={"status": "actioned", "action_kind": "outreach"}, headers=auth_headers,
    )
    assert r.status_code == 200

    r = await client.get("/api/v1/lead-engine/funnel", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["p1_mmf_gap"] == {"detected": 1, "actioned": 1, "drafted": 1, "sent": 1}
    # La levee de la meme societe a aussi cree un funding_detected (non actionne)
    assert body["p2_funding"]["detected"] == 1
    assert body["p2_funding"]["sent"] == 0


async def test_actioned_self_loop_updates_action(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    test_user: User,
):
    """DC5 : actioned -> actioned autorise (enrichi puis outreach envoye)."""
    signal, _ = await _seed_mmf_signal(
        client, auth_headers, db_session, test_user, with_contact_email=None,
    )
    r1 = await client.patch(
        f"/api/v1/lead-engine/signals/{signal['id']}",
        json={"status": "actioned", "action_kind": "contacts"}, headers=auth_headers,
    )
    assert r1.status_code == 200
    r2 = await client.patch(
        f"/api/v1/lead-engine/signals/{signal['id']}",
        json={"status": "actioned", "action_kind": "outreach"}, headers=auth_headers,
    )
    assert r2.status_code == 200
    assert r2.json()["payload_json"]["action"]["kind"] == "outreach"
