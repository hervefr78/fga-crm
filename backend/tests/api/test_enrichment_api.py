"""Tests des endpoints d'enrichissement (RBAC + validation + flux)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.fixture(autouse=True)
def _no_broker_quota(monkeypatch: pytest.MonkeyPatch):
    """Neutralise l'enqueue Celery + le quota Redis (tests hermetiques)."""
    from app.api.v1 import enrichment
    from app.tasks.enrichment import enrichment_run_job_task

    async def _allow(*a, **k):
        return True

    monkeypatch.setattr(enrichment, "reserve_daily_credits", _allow)
    monkeypatch.setattr(enrichment_run_job_task, "delay", lambda *a, **k: None)


# --- RBAC ---

async def test_jobs_forbidden_for_sales(client: AsyncClient, sales_headers: dict):
    r = await client.post(
        "/api/v1/enrichment/jobs", headers=sales_headers,
        json={"mode": "company", "siren": "123456789"},
    )
    assert r.status_code == 403


async def test_list_ok_for_manager(client: AsyncClient, manager_headers: dict):
    r = await client.get("/api/v1/enrichment/jobs", headers=manager_headers)
    assert r.status_code == 200
    assert r.json()["total"] == 0


async def test_jobs_isolated_cross_org(client: AsyncClient, auth_headers: dict, db_session):
    """Un user de l'org A ne voit ni ne lit les jobs d'enrichissement d'une autre org."""
    import uuid

    from app.models.enrichment import EnrichmentJob
    from app.models.organization import Organization

    org_b = Organization(id=uuid.uuid4(), name="Org B", slug=f"ob-{uuid.uuid4().hex[:8]}")
    db_session.add(org_b)
    await db_session.flush()
    job_b = EnrichmentJob(
        mode="company", status="done", target_json={}, organization_id=org_b.id,
    )
    db_session.add(job_b)
    await db_session.commit()

    r = await client.get("/api/v1/enrichment/jobs", headers=auth_headers)
    assert r.status_code == 200
    assert str(job_b.id) not in [j["id"] for j in r.json()["items"]]

    r = await client.get(f"/api/v1/enrichment/jobs/{job_b.id}", headers=auth_headers)
    assert r.status_code == 404


# --- Validation ---

async def test_company_without_siren_422(client: AsyncClient, auth_headers: dict):
    r = await client.post("/api/v1/enrichment/jobs", headers=auth_headers, json={"mode": "company"})
    assert r.status_code == 422


async def test_batch_without_sirens_422(client: AsyncClient, auth_headers: dict):
    r = await client.post("/api/v1/enrichment/jobs", headers=auth_headers, json={"mode": "batch"})
    assert r.status_code == 422


async def test_icp_without_filter_422(client: AsyncClient, auth_headers: dict):
    r = await client.post("/api/v1/enrichment/jobs", headers=auth_headers, json={"mode": "icp"})
    assert r.status_code == 422


async def test_contacts_without_selection_422(client: AsyncClient, auth_headers: dict):
    # mode contacts sans contact_ids ni all_missing_email -> 422 (Feature B)
    r = await client.post("/api/v1/enrichment/jobs", headers=auth_headers, json={"mode": "contacts"})
    assert r.status_code == 422


# --- Flux ---

async def test_create_company_job(client: AsyncClient, auth_headers: dict):
    r = await client.post(
        "/api/v1/enrichment/jobs", headers=auth_headers,
        json={"mode": "company", "siren": "123456789"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "company" and body["status"] == "queued"
    # GET -> queued (task mockee, pas executee)
    g = await client.get(f"/api/v1/enrichment/jobs/{body['id']}", headers=auth_headers)
    assert g.status_code == 200 and g.json()["status"] == "queued"


async def test_enrich_company_shortcut(client: AsyncClient, auth_headers: dict):
    r = await client.post(
        "/api/v1/enrichment/companies/987654321/enrich", headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["mode"] == "company"


async def test_create_contacts_job(client: AsyncClient, auth_headers: dict):
    # Feature B : mode contacts avec contact_ids -> job cree, target serialise
    import uuid
    cid = str(uuid.uuid4())
    r = await client.post(
        "/api/v1/enrichment/jobs", headers=auth_headers,
        json={"mode": "contacts", "contact_ids": [cid], "reverify": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "contacts" and body["status"] == "queued"
    g = await client.get(f"/api/v1/enrichment/jobs/{body['id']}", headers=auth_headers)
    assert g.status_code == 200


async def test_icp_job_ok(client: AsyncClient, auth_headers: dict):
    r = await client.post(
        "/api/v1/enrichment/jobs", headers=auth_headers,
        json={"mode": "icp", "icp_filter": {"naf_codes": ["5829C"], "limit": 10}},
    )
    assert r.status_code == 200
    assert r.json()["mode"] == "icp"


async def test_get_unknown_404(client: AsyncClient, auth_headers: dict):
    r = await client.get(
        "/api/v1/enrichment/jobs/00000000-0000-0000-0000-000000000000", headers=auth_headers,
    )
    assert r.status_code == 404
