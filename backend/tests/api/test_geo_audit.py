"""Tests des endpoints d'audit-visibilite GEO (integration Startup Radar)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import GeoAuditJob
from app.models.user import User
from app.services.api_keys import create_api_key
from app.services.geo.audit import compute_request_hash

_BODY = {
    "company_name": "Acme Corp",
    "domain": "acme.com",
    "aliases": ["Acme"],
    "prompts": ["Quel est le meilleur CRM ?", "Meilleur outil B2B ?"],
    "country": "FR",
    "language": "fr",
}


@pytest_asyncio.fixture
async def service_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(), email="sr-service@fga.fr",
        hashed_password="x", full_name="SR Service", role="admin", is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def audit_headers(db_session: AsyncSession, service_user: User) -> dict[str, str]:
    _, raw = await create_api_key(
        db=db_session, user_id=service_user.id, name="sr-geo-audit", scopes=["geo:audit"],
    )
    await db_session.commit()
    return {"Authorization": f"Bearer {raw}"}


@pytest_asyncio.fixture
async def wrong_scope_headers(db_session: AsyncSession, service_user: User) -> dict[str, str]:
    _, raw = await create_api_key(
        db=db_session, user_id=service_user.id, name="sr-wrong", scopes=["read:deals"],
    )
    await db_session.commit()
    return {"Authorization": f"Bearer {raw}"}


@pytest.fixture(autouse=True)
def _no_broker(monkeypatch: pytest.MonkeyPatch):
    """Neutralise l'enqueue Celery + le quota Redis (tests hermetiques)."""
    from app.api.v1 import geo_audit

    async def _allow(_key):
        return True

    monkeypatch.setattr(geo_audit, "_quota_allow", _allow)


@pytest.fixture(autouse=True)
def _no_delay(monkeypatch: pytest.MonkeyPatch):
    from app.tasks.geo import geo_audit_visibility_task
    monkeypatch.setattr(geo_audit_visibility_task, "delay", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# RBAC / auth
# ---------------------------------------------------------------------------

async def test_post_requires_key(client: AsyncClient):
    r = await client.post("/api/v1/geo/audit-visibility", json=_BODY)
    assert r.status_code == 401


async def test_post_wrong_scope_forbidden(client: AsyncClient, wrong_scope_headers: dict):
    r = await client.post("/api/v1/geo/audit-visibility", headers=wrong_scope_headers, json=_BODY)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

async def test_post_empty_prompts_422(client: AsyncClient, audit_headers: dict):
    body = {**_BODY, "prompts": []}
    r = await client.post("/api/v1/geo/audit-visibility", headers=audit_headers, json=body)
    assert r.status_code == 422


async def test_post_too_many_prompts_422(client: AsyncClient, audit_headers: dict):
    body = {**_BODY, "prompts": ["a", "b", "c", "d", "e", "f"]}  # > 5
    r = await client.post("/api/v1/geo/audit-visibility", headers=audit_headers, json=body)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Flux
# ---------------------------------------------------------------------------

async def test_post_creates_queued_job(client: AsyncClient, audit_headers: dict):
    r = await client.post("/api/v1/geo/audit-visibility", headers=audit_headers, json=_BODY)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "queued"
    assert body["cache_hit"] is False
    # GET -> queued, result null
    g = await client.get(f"/api/v1/geo/audit-visibility/{body['audit_id']}", headers=audit_headers)
    assert g.status_code == 200
    assert g.json()["status"] == "queued"
    assert g.json()["result"] is None


async def test_dedup_returns_cache_hit(
    client: AsyncClient, audit_headers: dict, db_session: AsyncSession
):
    # Un job complete recent avec le meme request_hash -> cache_hit.
    request_hash = compute_request_hash(
        domain=_BODY["domain"], engine="perplexity", prompts=_BODY["prompts"],
        country="FR", language="fr",
    )
    job = GeoAuditJob(
        domain=_BODY["domain"], company_name=_BODY["company_name"], request_hash=request_hash,
        engine="perplexity", status="completed", finished_at=datetime.now(UTC),
        result_json={"visible": False, "summary": "0/2"},
    )
    db_session.add(job)
    await db_session.commit()

    r = await client.post("/api/v1/geo/audit-visibility", headers=audit_headers, json=_BODY)
    assert r.status_code == 200
    assert r.json()["cache_hit"] is True
    assert r.json()["audit_id"] == str(job.id)


async def test_get_unknown_404(client: AsyncClient, audit_headers: dict):
    r = await client.get(
        "/api/v1/geo/audit-visibility/00000000-0000-0000-0000-000000000000",
        headers=audit_headers,
    )
    assert r.status_code == 404


async def test_get_invalid_uuid_422(client: AsyncClient, audit_headers: dict):
    r = await client.get("/api/v1/geo/audit-visibility/not-a-uuid", headers=audit_headers)
    assert r.status_code == 422
