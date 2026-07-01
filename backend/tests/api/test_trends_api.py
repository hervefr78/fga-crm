"""Tests des routes Trends (flux quick + RBAC + dedup)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.services.trends import cache


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch: pytest.MonkeyPatch):
    """Cache Redis neutralise -> tests hermetiques (dedup teste via la DB)."""

    async def _get(_hash):
        return None

    async def _set(_hash, _payload, _ttl):
        return None

    monkeypatch.setattr(cache, "get_cached_report", _get)
    monkeypatch.setattr(cache, "set_cached_report", _set)


async def _first_category_id(client: AsyncClient, headers: dict) -> str:
    r = await client.get("/api/v1/trends/categories", headers=headers)
    assert r.status_code == 200
    cats = r.json()
    assert len(cats) >= 1
    return cats[0]["id"]


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

async def test_categories_forbidden_for_sales(client: AsyncClient, sales_headers: dict):
    r = await client.get("/api/v1/trends/categories", headers=sales_headers)
    assert r.status_code == 403


async def test_categories_ok_for_manager(client: AsyncClient, manager_headers: dict):
    r = await client.get("/api/v1/trends/categories", headers=manager_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_health_admin_only(
    client: AsyncClient, manager_headers: dict, auth_headers: dict
):
    # manager -> 403
    assert (await client.get("/api/v1/trends/health", headers=manager_headers)).status_code == 403
    # admin -> 200
    r = await client.get("/api/v1/trends/health", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["provider"] == "mock"


# ---------------------------------------------------------------------------
# Flux quick
# ---------------------------------------------------------------------------

async def test_create_quick_report_completes(client: AsyncClient, auth_headers: dict):
    cat_id = await _first_category_id(client, auth_headers)
    r = await client.post(
        "/api/v1/trends/reports",
        headers=auth_headers,
        json={"mode": "quick", "category_id": cat_id, "seed_terms": ["prospection"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "completed"
    assert body["provider_effective"] == "mock"
    assert body["cache_hit"] is False
    job_id = body["job_id"]

    # Le rapport est disponible immediatement.
    rep = await client.get(f"/api/v1/trends/reports/{job_id}", headers=auth_headers)
    assert rep.status_code == 200
    data = rep.json()
    assert data["opportunity_score"] is not None
    assert data["signals"]["market_pulse"]["interest_index"] >= 0
    assert len(data["signals"]["rising_queries"]) > 0


async def test_get_job_status(client: AsyncClient, auth_headers: dict):
    cat_id = await _first_category_id(client, auth_headers)
    body = (await client.post(
        "/api/v1/trends/reports", headers=auth_headers,
        json={"mode": "quick", "category_id": cat_id},
    )).json()
    r = await client.get(f"/api/v1/trends/jobs/{body['job_id']}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


async def test_dedup_returns_cache_hit(client: AsyncClient, auth_headers: dict):
    cat_id = await _first_category_id(client, auth_headers)
    payload = {"mode": "quick", "category_id": cat_id, "seed_terms": ["dedup"]}
    first = (await client.post("/api/v1/trends/reports", headers=auth_headers, json=payload)).json()
    second = (await client.post("/api/v1/trends/reports", headers=auth_headers, json=payload)).json()
    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    # Meme job reutilise (pas de doublon).
    assert second["job_id"] == first["job_id"]


async def test_latest_report(client: AsyncClient, auth_headers: dict):
    cat_id = await _first_category_id(client, auth_headers)
    await client.post(
        "/api/v1/trends/reports", headers=auth_headers,
        json={"mode": "quick", "category_id": cat_id},
    )
    r = await client.get(
        "/api/v1/trends/reports/latest",
        headers=auth_headers,
        params={"category_id": cat_id, "country": "FR", "language": "fr"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


async def test_create_report_unknown_category_404(client: AsyncClient, auth_headers: dict):
    r = await client.post(
        "/api/v1/trends/reports",
        headers=auth_headers,
        json={"mode": "quick", "category_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert r.status_code == 404


async def test_get_report_unknown_job_404(client: AsyncClient, auth_headers: dict):
    r = await client.get(
        "/api/v1/trends/reports/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert r.status_code == 404


async def test_invalid_job_id_422(client: AsyncClient, auth_headers: dict):
    r = await client.get("/api/v1/trends/jobs/not-a-uuid", headers=auth_headers)
    assert r.status_code == 422
