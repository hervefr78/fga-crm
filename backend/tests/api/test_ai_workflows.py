# =============================================================================
# FGA CRM - Tests Workflows IA : scoring des deals (LLM mocke)
# =============================================================================

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ai_workflow import AiWorkflowRun
from app.schemas.ai_workflows import (
    ContactQualifyOutput,
    DealScoreOutput,
    SpicedDimension,
    SpicedGrid,
)
from app.services.ai_workflows import qualification, scoring
from app.services.ai_workflows.client import AiWorkflowError

FAKE_OUTPUT = DealScoreOutput(
    score=72, tier="A", fit_points=40, intent_points=20, message_points=12,
    rationale="Startup B2B post-levee, audit bas : opportunite mesuree.",
    missing_signals=["effectif inconnu"],
    recommended_product="audit-999",
)


@pytest.fixture(autouse=True)
def _openai_configured(monkeypatch: pytest.MonkeyPatch):
    """Les tests supposent OpenAI configure ; l'appel reel est toujours mocke."""
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")


@pytest.fixture()
def mock_llm(monkeypatch: pytest.MonkeyPatch):
    """Mock du client LLM : renvoie FAKE_OUTPUT et compte les appels."""
    calls = {"n": 0}

    async def _fake(schema_model, **kwargs):
        calls["n"] += 1
        return FAKE_OUTPUT, {"input_tokens": 900, "output_tokens": 150}

    monkeypatch.setattr(scoring, "call_openai_structured", _fake)
    return calls


async def _create_deal(client: AsyncClient, headers: dict, **kwargs) -> dict:
    payload = {"title": "Deal Scoring", **kwargs}
    resp = await client.post("/api/v1/deals", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_score_deal_persists_and_logs(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, mock_llm
):
    deal = await _create_deal(client, auth_headers)

    r = await client.post(f"/api/v1/deals/{deal['id']}/score", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["score"] == 72
    assert body["tier"] == "A"
    assert body["cached"] is False
    assert body["recommended_product"] == "audit-999"
    assert body["meta"]["prompt_version"] == "scoring-v1"

    # Persiste sur le deal (expose par GET).
    got = (await client.get(f"/api/v1/deals/{deal['id']}", headers=auth_headers)).json()
    assert got["ai_score"] == 72
    assert got["ai_tier"] == "A"
    assert got["ai_score_missing"] == ["effectif inconnu"]

    # Run d'audit trace (ok + tokens).
    run = (
        await db_session.execute(
            select(AiWorkflowRun).where(AiWorkflowRun.target_id == uuid.UUID(deal["id"]))
        )
    ).scalar_one()
    assert run.workflow == "scoring"
    assert run.status == "ok"
    assert run.input_tokens == 900


async def test_score_deal_cached_within_ttl(
    client: AsyncClient, auth_headers: dict, mock_llm
):
    deal = await _create_deal(client, auth_headers)
    r1 = await client.post(f"/api/v1/deals/{deal['id']}/score", headers=auth_headers)
    assert r1.json()["cached"] is False
    # 2e appel < TTL : renvoye du cache, pas de nouvel appel LLM.
    r2 = await client.post(f"/api/v1/deals/{deal['id']}/score", headers=auth_headers)
    assert r2.json()["cached"] is True
    assert mock_llm["n"] == 1
    # force_rescore : re-appel LLM.
    r3 = await client.post(
        f"/api/v1/deals/{deal['id']}/score?force_rescore=true", headers=auth_headers
    )
    assert r3.json()["cached"] is False
    assert mock_llm["n"] == 2


async def test_score_deal_kill_switch(
    client: AsyncClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch, mock_llm
):
    monkeypatch.setattr(settings, "ai_workflows_enabled", False)
    deal = await _create_deal(client, auth_headers)
    r = await client.post(f"/api/v1/deals/{deal['id']}/score", headers=auth_headers)
    assert r.status_code == 503
    assert mock_llm["n"] == 0


async def test_score_deal_cross_org_404(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, mock_llm
):
    """Un deal d'une autre organisation est introuvable (404, pas 403)."""
    from app.models.deal import Deal
    from app.models.organization import Organization

    org_b = Organization(id=uuid.uuid4(), name="Org B", slug=f"b-{uuid.uuid4().hex[:8]}")
    db_session.add(org_b)
    await db_session.flush()
    foreign = Deal(title="Ailleurs", organization_id=org_b.id)
    db_session.add(foreign)
    await db_session.commit()

    r = await client.post(f"/api/v1/deals/{foreign.id}/score", headers=auth_headers)
    assert r.status_code == 404
    assert mock_llm["n"] == 0


async def test_score_deal_sales_ownership(
    client: AsyncClient, auth_headers: dict, sales_headers: dict, mock_llm
):
    """Un sales ne peut pas scorer le deal d'un autre (403) mais peut scorer le sien."""
    other = await _create_deal(client, auth_headers)  # owner = admin
    r = await client.post(f"/api/v1/deals/{other['id']}/score", headers=sales_headers)
    assert r.status_code == 403

    mine = await _create_deal(client, sales_headers)  # owner = sales
    r2 = await client.post(f"/api/v1/deals/{mine['id']}/score", headers=sales_headers)
    assert r2.status_code == 200


async def test_score_deal_llm_failure_leaves_deal_intact(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    async def _boom(schema_model, **kwargs):
        raise AiWorkflowError("LLM down", kind="api_error")

    monkeypatch.setattr(scoring, "call_openai_structured", _boom)
    deal = await _create_deal(client, auth_headers)

    r = await client.post(f"/api/v1/deals/{deal['id']}/score", headers=auth_headers)
    assert r.status_code == 502

    # Deal intact (pas de score partiel) + run d'echec trace.
    got = (await client.get(f"/api/v1/deals/{deal['id']}", headers=auth_headers)).json()
    assert got["ai_score"] is None
    run = (
        await db_session.execute(
            select(AiWorkflowRun).where(AiWorkflowRun.target_id == uuid.UUID(deal["id"]))
        )
    ).scalar_one()
    assert run.status == "api_error"


# ---------------------------------------------------------------------------
# Workflow 2 — Qualification SPICED
# ---------------------------------------------------------------------------

def _qualify_output(routing: str) -> ContactQualifyOutput:
    known = SpicedDimension(value="startup B2B post-levee", source="fiche entreprise")
    unknown = SpicedDimension(value="unknown", source="unknown")
    return ContactQualifyOutput(
        spiced=SpicedGrid(
            situation=known, pain=unknown, impact=unknown,
            critical_event=unknown, decision=known,
        ),
        routing=routing,  # type: ignore[arg-type]
        routing_rationale="Fit ICP probable, dimensions cles inconnues.",
        suggested_product="audit-999",
        next_action="Appeler pour qualifier la douleur.",
    )


@pytest.fixture()
def mock_qualify_llm(monkeypatch: pytest.MonkeyPatch):
    """Mock LLM qualification : routing pilotable par test."""
    state = {"routing": "standard", "n": 0}

    async def _fake(schema_model, **kwargs):
        state["n"] += 1
        return _qualify_output(state["routing"]), {"input_tokens": 700, "output_tokens": 200}

    monkeypatch.setattr(qualification, "call_openai_structured", _fake)
    return state


async def _create_contact(client: AsyncClient, headers: dict, **kwargs) -> dict:
    payload = {"first_name": "Lea", "last_name": "Inbound", **kwargs}
    resp = await client.post("/api/v1/contacts", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_qualify_contact_persists(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession, mock_qualify_llm
):
    contact = await _create_contact(client, auth_headers)
    r = await client.post(
        f"/api/v1/contacts/{contact['id']}/qualify", headers=auth_headers,
        json={"submission_text": "Telechargement Observatoire 2026"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["routing"] == "standard"
    assert body["spiced"]["pain"]["value"] == "unknown"
    assert body["deal_created_id"] is None  # standard : pas de deal auto
    assert body["meta"]["prompt_version"] == "qualif-v1"

    got = (await client.get(f"/api/v1/contacts/{contact['id']}", headers=auth_headers)).json()
    assert got["ai_routing"] == "standard"
    assert got["ai_qualification"]["next_action"]

    run = (
        await db_session.execute(
            select(AiWorkflowRun).where(AiWorkflowRun.target_id == uuid.UUID(contact["id"]))
        )
    ).scalar_one()
    assert run.workflow == "qualification"
    assert run.status == "ok"


async def test_qualify_fast_track_creates_deal(
    client: AsyncClient, auth_headers: dict, mock_qualify_llm
):
    mock_qualify_llm["routing"] = "fast_track"
    contact = await _create_contact(client, auth_headers, first_name="Max")
    r = await client.post(
        f"/api/v1/contacts/{contact['id']}/qualify", headers=auth_headers, json={},
    )
    assert r.status_code == 200, r.text
    deal_id = r.json()["deal_created_id"]
    assert deal_id is not None

    deal = (await client.get(f"/api/v1/deals/{deal_id}", headers=auth_headers)).json()
    assert deal["stage"] == "new"           # stage reel FGA (pas 'qualified')
    assert deal["product"] == "audit-999"
    assert deal["contact_id"] == contact["id"]


async def test_qualify_filter_human_review(
    client: AsyncClient, auth_headers: dict, mock_qualify_llm
):
    """File 'A revoir' : filtre ai_routing sur la liste des contacts."""
    mock_qualify_llm["routing"] = "human_review"
    c = await _create_contact(client, auth_headers, first_name="Zoe")
    await client.post(f"/api/v1/contacts/{c['id']}/qualify", headers=auth_headers, json={})

    r = await client.get(
        "/api/v1/contacts", params={"ai_routing": "human_review"}, headers=auth_headers
    )
    assert r.status_code == 200
    ids = [it["id"] for it in r.json()["items"]]
    assert c["id"] in ids
    # Valeur inconnue -> 422 (DC1)
    bad = await client.get(
        "/api/v1/contacts", params={"ai_routing": "poubelle"}, headers=auth_headers
    )
    assert bad.status_code == 422


async def test_qualify_llm_failure_leaves_contact_intact(
    client: AsyncClient, auth_headers: dict, monkeypatch: pytest.MonkeyPatch
):
    async def _boom(schema_model, **kwargs):
        raise AiWorkflowError("down", kind="api_error")

    monkeypatch.setattr(qualification, "call_openai_structured", _boom)
    contact = await _create_contact(client, auth_headers, first_name="Bob")
    r = await client.post(
        f"/api/v1/contacts/{contact['id']}/qualify", headers=auth_headers, json={},
    )
    assert r.status_code == 502
    got = (await client.get(f"/api/v1/contacts/{contact['id']}", headers=auth_headers)).json()
    assert got["ai_routing"] is None
