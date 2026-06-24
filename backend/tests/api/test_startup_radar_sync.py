# =============================================================================
# FGA CRM - Tests full sync Startup Radar en tache de fond (2026-06)
# =============================================================================
"""Tests de l'orchestration full sync SR -> CRM :
- POST /integrations/startup-radar/sync : enqueue 202 + single-flight 409
- GET  /integrations/startup-radar/status : lecture du statut Redis (idle /
  running / completed / failed)
- Task Celery full_sync_task : ecrit le statut final + libere le verrou

Redis et Celery sont mockes (les tests tournent sur SQLite sans broker).
"""

import pytest
from httpx import AsyncClient

import app.tasks.startup_radar_full_sync as sr_task
from app.models.user import User

SYNC_URL = "/api/v1/integrations/startup-radar/sync"
STATUS_URL = "/api/v1/integrations/startup-radar/status"


class _FakeTask:
    """Faux Celery task : capture les appels .delay sans broker."""

    def __init__(self):
        self.calls: list[tuple] = []

    def delay(self, *args):
        self.calls.append(args)


def _full_result_dict(**overrides) -> dict:
    """SyncResult serialise (toutes les cles, defaut 0/[])."""
    base = {
        "companies_created": 0,
        "companies_updated": 0,
        "contacts_created": 0,
        "contacts_updated": 0,
        "investors_created": 0,
        "investors_updated": 0,
        "audits_created": 0,
        "funding_activities_created": 0,
        "qualification_tasks_created": 0,
        "errors": [],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# POST /sync — enqueue 202
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_enqueues_and_returns_202(
    client: AsyncClient, auth_headers: dict, test_user: User, monkeypatch,
):
    """Le sync pose le verrou, le statut running, enqueue la task et renvoie 202."""
    fake_task = _FakeTask()
    status_writes: list[dict] = []

    async def fake_acquire(job_id):  # noqa: ARG001
        return True

    async def fake_set(payload):
        status_writes.append(payload)

    monkeypatch.setattr("app.services.sync_status.try_acquire_lock", fake_acquire)
    monkeypatch.setattr("app.services.sync_status.set_status_async", fake_set)
    monkeypatch.setattr("app.api.v1.integrations.full_sync_task", fake_task)

    resp = await client.post(SYNC_URL, headers=auth_headers)

    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "running"
    assert body["job_id"]
    assert body["started_at"]

    # La task a ete enqueue avec (user_id, job_id, started_at) — owner = le clickeur
    assert fake_task.calls == [
        (str(test_user.id), body["job_id"], body["started_at"]),
    ]
    # Le statut 'running' a ete ecrit immediatement
    assert status_writes and status_writes[-1]["status"] == "running"


@pytest.mark.asyncio
async def test_sync_conflict_returns_409_when_locked(
    client: AsyncClient, auth_headers: dict, monkeypatch,
):
    """Si une sync tourne deja (verrou non acquis) -> 409, pas d'enqueue."""
    fake_task = _FakeTask()

    async def fake_acquire(job_id):  # noqa: ARG001
        return False

    monkeypatch.setattr("app.services.sync_status.try_acquire_lock", fake_acquire)
    monkeypatch.setattr("app.api.v1.integrations.full_sync_task", fake_task)

    resp = await client.post(SYNC_URL, headers=auth_headers)

    assert resp.status_code == 409
    assert "cours" in resp.json()["detail"].lower()
    assert fake_task.calls == []  # pas d'enqueue en doublon


@pytest.mark.asyncio
async def test_sync_requires_auth(client: AsyncClient):
    """Sans token -> refus (401/403)."""
    resp = await client.post(SYNC_URL)
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# GET /status — lecture du statut Redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_status_idle_when_never_synced(
    client: AsyncClient, auth_headers: dict, monkeypatch,
):
    async def fake_get():
        return None

    monkeypatch.setattr("app.services.sync_status.get_status", fake_get)

    resp = await client.get(STATUS_URL, headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "idle"
    assert body["has_synced"] is False
    assert body["last_result"] is None


@pytest.mark.asyncio
async def test_status_running(client: AsyncClient, auth_headers: dict, monkeypatch):
    async def fake_get():
        return {
            "job_id": "job-1",
            "status": "running",
            "started_at": "2026-06-24T10:00:00+00:00",
            "finished_at": None,
            "result": None,
            "error": None,
        }

    async def fake_locked():
        return True  # verrou actif → la sync tourne vraiment

    monkeypatch.setattr("app.services.sync_status.get_status", fake_get)
    monkeypatch.setattr("app.services.sync_status.is_locked", fake_locked)

    resp = await client.get(STATUS_URL, headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "running"
    assert body["has_synced"] is False
    assert body["last_result"] is None
    assert body["started_at"] == "2026-06-24T10:00:00+00:00"


@pytest.mark.asyncio
async def test_status_running_but_unlocked_reported_failed(
    client: AsyncClient, auth_headers: dict, monkeypatch,
):
    """Job zombie : statut 'running' mais verrou disparu (worker mort) → failed."""
    async def fake_get():
        return {
            "job_id": "job-zombie",
            "status": "running",
            "started_at": "2026-06-24T10:00:00+00:00",
            "finished_at": None,
            "result": None,
            "error": None,
        }

    async def fake_locked():
        return False  # plus de verrou → worker mort

    monkeypatch.setattr("app.services.sync_status.get_status", fake_get)
    monkeypatch.setattr("app.services.sync_status.is_locked", fake_locked)

    resp = await client.get(STATUS_URL, headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["has_synced"] is False
    assert "interrompue" in body["error"].lower()


@pytest.mark.asyncio
async def test_sync_forbidden_for_sales(client: AsyncClient, sales_headers: dict, monkeypatch):
    """Un role 'sales' ne peut PAS lancer la full sync (manager+ requis) → 403."""
    fake_task = _FakeTask()

    async def fake_acquire(job_id):  # noqa: ARG001
        return True

    monkeypatch.setattr("app.services.sync_status.try_acquire_lock", fake_acquire)
    monkeypatch.setattr("app.api.v1.integrations.full_sync_task", fake_task)

    resp = await client.post(SYNC_URL, headers=sales_headers)

    assert resp.status_code == 403
    assert fake_task.calls == []  # pas d'enqueue


@pytest.mark.asyncio
async def test_status_forbidden_for_sales(client: AsyncClient, sales_headers: dict):
    """Un role 'sales' ne peut PAS lire le statut (contient noms + erreurs internes)."""
    resp = await client.get(STATUS_URL, headers=sales_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_status_completed_exposes_result(
    client: AsyncClient, auth_headers: dict, monkeypatch,
):
    async def fake_get():
        return {
            "job_id": "job-2",
            "status": "completed",
            "started_at": "2026-06-24T10:00:00+00:00",
            "finished_at": "2026-06-24T10:05:00+00:00",
            "result": _full_result_dict(companies_created=12, contacts_created=4, errors=["x"]),
            "error": None,
        }

    monkeypatch.setattr("app.services.sync_status.get_status", fake_get)

    resp = await client.get(STATUS_URL, headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["has_synced"] is True
    assert body["last_result"]["companies_created"] == 12
    assert body["last_result"]["contacts_created"] == 4
    assert body["last_result"]["errors"] == ["x"]
    assert body["finished_at"] == "2026-06-24T10:05:00+00:00"


@pytest.mark.asyncio
async def test_status_failed_exposes_error(
    client: AsyncClient, auth_headers: dict, monkeypatch,
):
    async def fake_get():
        return {
            "job_id": "job-3",
            "status": "failed",
            "started_at": "2026-06-24T10:00:00+00:00",
            "finished_at": "2026-06-24T10:01:00+00:00",
            "result": None,
            "error": "Boom: SR injoignable",
        }

    monkeypatch.setattr("app.services.sync_status.get_status", fake_get)

    resp = await client.get(STATUS_URL, headers=auth_headers)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert body["has_synced"] is False
    assert body["error"] == "Boom: SR injoignable"
    assert body["last_result"] is None


# ---------------------------------------------------------------------------
# Task Celery full_sync_task — statut final + liberation du verrou
# ---------------------------------------------------------------------------


def test_full_sync_task_writes_completed_and_releases_lock(monkeypatch):
    """Succes : statut completed avec le resultat + verrou libere."""
    writes: list[dict] = []
    released: list[bool] = []

    async def fake_run(user_id):  # noqa: ARG001
        return _full_result_dict(companies_created=3, contacts_created=2)

    monkeypatch.setattr(sr_task, "_run_full_sync", fake_run)
    monkeypatch.setattr(sr_task, "set_status_sync", lambda p: writes.append(p))
    monkeypatch.setattr(sr_task, "release_lock_sync", lambda job_id: released.append(job_id))

    result = sr_task.full_sync_task(
        "11111111-1111-1111-1111-111111111111", "job-ok", "2026-06-24T10:00:00+00:00",
    )

    assert result["companies_created"] == 3
    assert writes[-1]["status"] == "completed"
    assert writes[-1]["result"]["companies_created"] == 3
    assert writes[-1]["started_at"] == "2026-06-24T10:00:00+00:00"
    assert writes[-1]["finished_at"] is not None
    assert released == ["job-ok"]  # verrou libere AVEC le job_id (compare-and-delete)


def test_full_sync_task_writes_failed_and_releases_lock(monkeypatch):
    """Echec (exception) : statut failed avec le message + verrou libere + re-raise."""
    writes: list[dict] = []
    released: list[bool] = []

    async def fake_run(user_id):  # noqa: ARG001
        raise RuntimeError("explosion sync")

    monkeypatch.setattr(sr_task, "_run_full_sync", fake_run)
    monkeypatch.setattr(sr_task, "set_status_sync", lambda p: writes.append(p))
    monkeypatch.setattr(sr_task, "release_lock_sync", lambda job_id: released.append(job_id))

    with pytest.raises(RuntimeError, match="explosion sync"):
        sr_task.full_sync_task(
            "11111111-1111-1111-1111-111111111111", "job-ko", "2026-06-24T10:00:00+00:00",
        )

    assert writes[-1]["status"] == "failed"
    assert "explosion sync" in writes[-1]["error"]
    assert released == ["job-ko"]  # verrou libere (avec job_id) meme en cas d'echec


# ---------------------------------------------------------------------------
# Cap des erreurs stockees (DC1)
# ---------------------------------------------------------------------------


def test_cap_errors_truncates_long_list():
    """Plus de MAX_STORED_ERRORS → tronque + ligne de comptage."""
    result = _full_result_dict(errors=[f"err{i}" for i in range(120)])
    capped = sr_task._cap_errors(result)
    assert len(capped["errors"]) == sr_task.MAX_STORED_ERRORS + 1
    assert "70 autres erreurs" in capped["errors"][-1]


def test_cap_errors_keeps_short_list():
    """En dessous du cap → liste inchangee."""
    capped = sr_task._cap_errors(_full_result_dict(errors=["a", "b"]))
    assert capped["errors"] == ["a", "b"]
