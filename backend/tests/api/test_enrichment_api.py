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
