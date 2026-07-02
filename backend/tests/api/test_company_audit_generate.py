# =============================================================================
# FGA CRM - Tests generation d'audit SR a la demande (2026-06)
# =============================================================================
"""Tests des endpoints de generation d'audit (trigger SR + polling) :
- POST /integrations/startup-radar/audit/{id}/generate : 202 / 409 / 422 / 403
- GET  .../audit/{id}/generate-status : proxy idle / running / completed / failed

Le client StartupRadarClient est mocke (pas d'appel reseau a SR).
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.user import User
from app.services.startup_radar import StartupRadarConflict

# ---------------------------------------------------------------------------
# Fake SR client
# ---------------------------------------------------------------------------


class _FakeSR:
    def __init__(self, *, status_payload=None, conflict=False, launch_msg="Audit lance"):
        self._status = status_payload
        self._conflict = conflict
        self._launch_msg = launch_msg
        self.launched_with = None

    async def authenticate(self):
        return "tok"

    async def launch_diagnostic_audit(self, sr_id):
        self.launched_with = sr_id
        if self._conflict:
            raise StartupRadarConflict("deja en cours")
        return {"status": "started", "message": self._launch_msg}

    async def get_diagnostic_status(self, sr_id):
        return self._status


def _patch_sr(monkeypatch, fake: _FakeSR):
    monkeypatch.setattr("app.api.v1.integrations.StartupRadarClient", lambda: fake)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_company(db: AsyncSession, owner: User, sr_id: str | None) -> Company:
    company = Company(
        id=uuid.uuid4(),
        name="Acme SR",
        lead_source="startup_radar",
        owner_id=owner.id,
        startup_radar_id=sr_id,
        organization_id=owner.organization_id,
    )
    db.add(company)
    await db.commit()
    return company


def _gen_url(cid) -> str:
    return f"/api/v1/integrations/startup-radar/audit/{cid}/generate"


def _status_url(cid) -> str:
    return f"/api/v1/integrations/startup-radar/audit/{cid}/generate-status"


# ---------------------------------------------------------------------------
# POST /generate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_audit_returns_202(
    client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession, monkeypatch,
):
    company = await _make_company(db_session, test_user, "sr-abc-123")
    fake = _FakeSR(launch_msg="Audit diagnostic lance")
    _patch_sr(monkeypatch, fake)

    resp = await client.post(_gen_url(company.id), headers=auth_headers)

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert "lance" in body["message"].lower()
    assert fake.launched_with == "sr-abc-123"  # trigger SR avec le bon sr_id


@pytest.mark.asyncio
async def test_generate_audit_conflict_returns_409(
    client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession, monkeypatch,
):
    company = await _make_company(db_session, test_user, "sr-conf")
    _patch_sr(monkeypatch, _FakeSR(conflict=True))

    resp = await client.post(_gen_url(company.id), headers=auth_headers)

    assert resp.status_code == 409
    assert "cours" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_audit_422_without_sr_link(
    client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession, monkeypatch,
):
    company = await _make_company(db_session, test_user, None)  # pas de lien SR
    _patch_sr(monkeypatch, _FakeSR())

    resp = await client.post(_gen_url(company.id), headers=auth_headers)

    assert resp.status_code == 422
    assert "Startup Radar" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_audit_422_for_investor(
    client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession, monkeypatch,
):
    company = await _make_company(db_session, test_user, "inv:42")  # investisseur
    _patch_sr(monkeypatch, _FakeSR())

    resp = await client.post(_gen_url(company.id), headers=auth_headers)

    assert resp.status_code == 422
    assert "investisseurs" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_audit_forbidden_for_sales(
    client: AsyncClient, sales_headers: dict, sales_user: User, db_session: AsyncSession, monkeypatch,
):
    company = await _make_company(db_session, sales_user, "sr-sales")
    _patch_sr(monkeypatch, _FakeSR())

    resp = await client.post(_gen_url(company.id), headers=sales_headers)

    assert resp.status_code == 403  # manager+ requis


# ---------------------------------------------------------------------------
# GET /generate-status (proxy SR)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_status_idle(
    client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession, monkeypatch,
):
    company = await _make_company(db_session, test_user, "sr-idle")
    _patch_sr(monkeypatch, _FakeSR(status_payload=None))  # SR 404 -> None -> idle

    resp = await client.get(_status_url(company.id), headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["status"] == "idle"


@pytest.mark.asyncio
async def test_generate_status_running_proxied(
    client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession, monkeypatch,
):
    company = await _make_company(db_session, test_user, "sr-run")
    _patch_sr(monkeypatch, _FakeSR(status_payload={
        "status": "running", "step": "Analyse detaillee", "error": None,
    }))

    resp = await client.get(_status_url(company.id), headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert body["step"] == "Analyse detaillee"


@pytest.mark.asyncio
async def test_generate_status_failed_proxied(
    client: AsyncClient, auth_headers: dict, test_user: User, db_session: AsyncSession, monkeypatch,
):
    company = await _make_company(db_session, test_user, "sr-fail")
    _patch_sr(monkeypatch, _FakeSR(status_payload={
        "status": "failed", "step": "Scoring", "error": "LLM timeout",
    }))

    resp = await client.get(_status_url(company.id), headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["error"] == "LLM timeout"
