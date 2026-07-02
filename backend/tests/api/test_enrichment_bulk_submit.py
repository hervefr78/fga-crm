"""Tests W3 : mode bulk de l'orchestrateur (batch/icp -> soumission async Icypeas)
+ reconciliation des bulks bloques sans callback."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.contact import Contact
from app.models.enrichment import EnrichmentBulk, EnrichmentBulkItem, EnrichmentJob
from app.services.enrichment import orchestrator
from app.services.enrichment.adapters.icypeas import IcypeasClient
from app.services.enrichment.adapters.mock import MockPeopleSource
from app.services.enrichment.bulk_callback import reconcile_stuck_bulks


@pytest.mark.asyncio
async def test_batch_mode_submits_bulk_without_creating_contacts(
    db_session: AsyncSession, test_org, monkeypatch
):
    # Icypeas reel + URL webhook -> branche bulk (W3)
    monkeypatch.setattr(settings, "icypeas_api_key", "k")
    monkeypatch.setattr(
        settings, "icypeas_webhook_url",
        "https://crm.example/api/v1/integrations/icypeas/webhook",
    )

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"success": True, "file": "BULKFILE1"})

    client = IcypeasClient("k", transport=httpx.MockTransport(handler))
    # Injecte le client MockTransport + un people source mock (pas de HTTP reel)
    monkeypatch.setattr(orchestrator, "get_bulk_client", lambda: client)
    monkeypatch.setattr(orchestrator, "get_people_sources", lambda: [MockPeopleSource()])

    job = EnrichmentJob(
        mode="batch", status="queued",
        target_json={"kind": "batch", "sirens": ["123456789"]},
        organization_id=test_org.id,
    )
    db_session.add(job)
    await db_session.commit()

    await orchestrator.run_enrichment_job(db_session, job)

    # Job en attente du callback, pas termine
    assert job.status == "awaiting_results"

    bulk = (await db_session.execute(select(EnrichmentBulk))).scalars().first()
    assert bulk is not None
    assert bulk.file == "BULKFILE1"
    assert bulk.status == "awaiting_results"
    assert bulk.total >= 1

    items = (await db_session.execute(select(EnrichmentBulkItem))).scalars().all()
    assert len(items) == bulk.total
    assert all(i.status == "pending" for i in items)
    assert all(i.organization_id == test_org.id for i in items)  # isolation
    assert all("person" in i.context_json and "company" in i.context_json for i in items)

    # Aucun contact cree a ce stade : le callback (W2) s'en charge
    contacts = (
        await db_session.execute(select(Contact).where(Contact.source == "enrichment"))
    ).scalars().all()
    assert contacts == []

    # Payload bulk conforme : task + externalIds + webhook + includeResults
    body = captured["body"]
    assert body["task"] == "email-search"
    assert body["custom"]["webhookUrlBulkDone"].endswith("/webhook")
    assert body["custom"]["includeResultsInWebhook"] is True
    assert len(body["custom"]["externalIds"]) == bulk.total


@pytest.mark.asyncio
async def test_batch_mode_falls_back_inline_without_webhook_url(
    db_session: AsyncSession, test_org, monkeypatch
):
    # Cle presente mais pas d'URL webhook -> pipeline inline (mock), pas de bulk
    from app.services.enrichment.adapters.mock import (
        MockCompanySource,
        MockEmailFinder,
        MockEmailVerifier,
    )

    monkeypatch.setattr(settings, "icypeas_api_key", "k")
    monkeypatch.setattr(settings, "icypeas_webhook_url", None)
    monkeypatch.setattr(orchestrator, "get_company_source", lambda: MockCompanySource())
    monkeypatch.setattr(orchestrator, "get_people_sources", lambda: [MockPeopleSource()])
    monkeypatch.setattr(orchestrator, "get_email_finders", lambda: [MockEmailFinder()])
    monkeypatch.setattr(orchestrator, "get_email_verifiers", lambda: [MockEmailVerifier()])

    job = EnrichmentJob(
        mode="batch", status="queued",
        target_json={"kind": "batch", "sirens": ["123456789"]},
        organization_id=test_org.id,
    )
    db_session.add(job)
    await db_session.commit()

    await orchestrator.run_enrichment_job(db_session, job)

    assert job.status == "done"  # pipeline inline synchrone termine le job
    bulks = (await db_session.execute(select(EnrichmentBulk))).scalars().all()
    assert bulks == []  # aucune soumission bulk


@pytest.mark.asyncio
async def test_reconcile_marks_stuck_bulk_and_fails_job(db_session: AsyncSession, test_org):
    job = EnrichmentJob(mode="batch", status="awaiting_results", target_json={},
                        organization_id=test_org.id)
    db_session.add(job)
    await db_session.flush()
    old = datetime.now(UTC) - timedelta(hours=48)
    bulk = EnrichmentBulk(
        file="STUCK", task="email-search", status="awaiting_results", total=3,
        organization_id=test_org.id, job_id=job.id, created_at=old,
    )
    db_session.add(bulk)
    await db_session.commit()

    n = await reconcile_stuck_bulks(db_session, timeout_hours=24)
    assert n == 1

    refreshed_bulk = await db_session.get(EnrichmentBulk, bulk.id)
    refreshed_job = await db_session.get(EnrichmentJob, job.id)
    assert refreshed_bulk.status == "error"
    assert refreshed_bulk.error is not None
    assert refreshed_job.status == "failed"


@pytest.mark.asyncio
async def test_reconcile_ignores_recent_bulk(db_session: AsyncSession, test_org):
    job = EnrichmentJob(mode="batch", status="awaiting_results", target_json={},
                        organization_id=test_org.id)
    db_session.add(job)
    await db_session.flush()
    bulk = EnrichmentBulk(
        file="RECENT", task="email-search", status="awaiting_results", total=1,
        organization_id=test_org.id, job_id=job.id,  # created_at = maintenant
    )
    db_session.add(bulk)
    await db_session.commit()

    n = await reconcile_stuck_bulks(db_session, timeout_hours=24)
    assert n == 0
    refreshed = await db_session.get(EnrichmentBulk, bulk.id)
    assert refreshed.status == "awaiting_results"  # intact
