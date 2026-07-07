"""Tests W2 : traitement du callback webhook Icypeas (bulk) + endpoint HMAC."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.contact import Contact
from app.models.enrichment import EnrichmentBulk, EnrichmentBulkItem, EnrichmentJob
from app.services.enrichment.bulk_callback import process_bulk_callback

_WEBHOOK_PATH = "/api/v1/integrations/icypeas/webhook"


def _callback_data(file_id: str) -> dict:
    return {
        "file": file_id, "total": 2, "type": "email-search", "done": 2, "found": 2,
        "results": [
            {"results": {"firstname": "Herve", "lastname": "Dhelin",
                         "emails": [{"email": "herve@fast-growth.fr", "certainty": "ultra_sure"}]},
             "status": "DEBITED", "userData": {"externalId": "ext-1"}},
            {"results": {"firstname": "Michel", "lastname": "Test",
                         "emails": [{"email": "michel@fast-growth.fr", "certainty": "ultra_sure"}]},
             "status": "DEBITED", "userData": {"externalId": "ext-2"}},
        ],
    }


async def _seed_bulk(db: AsyncSession, org_id, file_id: str) -> EnrichmentJob:
    job = EnrichmentJob(mode="batch", status="awaiting_results", target_json={}, organization_id=org_id)
    db.add(job)
    await db.flush()
    bulk = EnrichmentBulk(
        file=file_id, task="email-search", status="awaiting_results", total=2,
        organization_id=org_id, job_id=job.id,
    )
    db.add(bulk)
    await db.flush()
    for ext, fn, ln in [("ext-1", "Herve", "Dhelin"), ("ext-2", "Michel", "Test")]:
        db.add(EnrichmentBulkItem(
            bulk_id=bulk.id, external_id=ext, organization_id=org_id, status="pending",
            context_json={"company": {"siren": "123", "name": "FGA", "domain": "fast-growth.fr"},
                          "person": {"first_name": fn, "last_name": ln, "title_raw": "CTO", "role": "CTO"}},
        ))
    await db.commit()
    return job


@pytest.mark.asyncio
async def test_process_bulk_callback_creates_contacts_and_finishes_job(
    db_session: AsyncSession, test_org
):
    job = await _seed_bulk(db_session, test_org.id, "FILE1")

    res = await process_bulk_callback(db_session, _callback_data("FILE1"))
    assert res["found"] == 2
    assert res["done"] == 2

    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "done"  # job clos par le dernier callback
    # Stats rafraichies au fan-in avec le REEL des items (sinon le dashboard
    # affiche les compteurs figes a la soumission : emails_found=0).
    assert refreshed.stats_json["emails_found"] == 2
    assert refreshed.stats_json["valid"] == 2  # ultra_sure -> valid

    contacts = (
        await db_session.execute(select(Contact).where(Contact.source == "enrichment"))
    ).scalars().all()
    assert {c.email for c in contacts} == {"herve@fast-growth.fr", "michel@fast-growth.fr"}
    assert all(c.organization_id == test_org.id for c in contacts)  # isolation


@pytest.mark.asyncio
async def test_process_bulk_callback_idempotent(db_session: AsyncSession, test_org):
    await _seed_bulk(db_session, test_org.id, "FILE2")
    await process_bulk_callback(db_session, _callback_data("FILE2"))
    # 2e livraison -> deja done, aucun doublon
    res2 = await process_bulk_callback(db_session, _callback_data("FILE2"))
    assert res2.get("already_done") is True
    n = (await db_session.execute(select(Contact).where(Contact.source == "enrichment"))).scalars().all()
    assert len(n) == 2


@pytest.mark.asyncio
async def test_process_bulk_callback_unknown_file(db_session: AsyncSession):
    res = await process_bulk_callback(db_session, {"file": "NOPE", "results": []})
    assert res == {"matched": False}


@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature(client: AsyncClient):
    # secret non configure en test -> verify echoue -> 401
    r = await client.post(_WEBHOOK_PATH, json={"signature": "x", "timestamp": "t", "data": {}})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_webhook_accepts_valid_signature(client: AsyncClient, monkeypatch):
    monkeypatch.setattr(settings, "icypeas_api_secret", "s3cr3t")
    # timestamp frais (la fenetre anti-rejeu rejette un timestamp trop ancien)
    ts = datetime.now(UTC).isoformat()
    sig = hmac.new(b"s3cr3t", f"{_WEBHOOK_PATH}{ts}".lower().encode(), hashlib.sha1).hexdigest()
    r = await client.post(_WEBHOOK_PATH, json={"signature": sig, "timestamp": ts, "data": {"file": "X", "results": []}})
    assert r.status_code == 200
    assert r.json()["received"] is True


@pytest.mark.asyncio
async def test_webhook_rejects_stale_timestamp(client: AsyncClient, monkeypatch):
    # #2 : signature valide mais timestamp ancien (rejeu) -> 401
    monkeypatch.setattr(settings, "icypeas_api_secret", "s3cr3t")
    ts = "2020-01-01T00:00:00.000Z"
    sig = hmac.new(b"s3cr3t", f"{_WEBHOOK_PATH}{ts}".lower().encode(), hashlib.sha1).hexdigest()
    r = await client.post(_WEBHOOK_PATH, json={"signature": sig, "timestamp": ts, "data": {}})
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# FIX #12 — garde anti-rejeu single-use (nonce Redis) sur (timestamp, signature)
# ---------------------------------------------------------------------------

class _FakeNonceRedis:
    """Fake client Redis async (SET NX en memoire) — le repo n'a pas de Redis en test."""

    def __init__(self, *, fail: bool = False):
        self._store: set[str] = set()
        self._fail = fail

    async def set(self, key, value, nx=False, ex=None):
        if self._fail:
            raise RuntimeError("redis down")
        if nx and key in self._store:
            return None
        self._store.add(key)
        return True


@pytest.mark.asyncio
async def test_webhook_rejects_replayed_signature(client: AsyncClient, monkeypatch):
    """FIX #12 : un meme (timestamp, signature) valide rejoue -> 1re passe (200),
    2e refusee (401) via le nonce Redis single-use."""
    from app.api.v1 import enrichment_webhook

    monkeypatch.setattr(settings, "icypeas_api_secret", "s3cr3t")
    fake = _FakeNonceRedis()
    monkeypatch.setattr(enrichment_webhook, "_get_nonce_client", lambda: fake)

    ts = datetime.now(UTC).isoformat()
    sig = hmac.new(b"s3cr3t", f"{_WEBHOOK_PATH}{ts}".lower().encode(), hashlib.sha1).hexdigest()
    body = {"signature": sig, "timestamp": ts, "data": {"file": "X", "results": []}}

    r1 = await client.post(_WEBHOOK_PATH, json=body)
    assert r1.status_code == 200

    r2 = await client.post(_WEBHOOK_PATH, json=body)
    assert r2.status_code == 401
    assert "ejeu" in r2.json()["detail"]  # "Rejeu détecté"


@pytest.mark.asyncio
async def test_webhook_replay_guard_fails_open_on_redis_error(client: AsyncClient, monkeypatch):
    """FIX #12 : Redis indisponible -> le garde anti-rejeu fail-open (200) ;
    signature + fraicheur du timestamp restent la defense."""
    from app.api.v1 import enrichment_webhook

    monkeypatch.setattr(settings, "icypeas_api_secret", "s3cr3t")
    fake = _FakeNonceRedis(fail=True)
    monkeypatch.setattr(enrichment_webhook, "_get_nonce_client", lambda: fake)

    ts = datetime.now(UTC).isoformat()
    sig = hmac.new(b"s3cr3t", f"{_WEBHOOK_PATH}{ts}".lower().encode(), hashlib.sha1).hexdigest()
    body = {"signature": sig, "timestamp": ts, "data": {"file": "X", "results": []}}

    r = await client.post(_WEBHOOK_PATH, json=body)
    assert r.status_code == 200
