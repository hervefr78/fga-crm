"""Test E2E de l'orchestrateur d'enrichissement (providers mock, sans reseau)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.contact import Contact
from app.models.enrichment import (
    EnrichmentEmailVerification,
    EnrichmentJob,
    EnrichmentProvenance,
)
from app.services.enrichment import freshness, orchestrator
from app.services.enrichment.orchestrator import run_enrichment_job


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch: pytest.MonkeyPatch):
    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(freshness, "touch", _noop)


async def test_run_enrichment_job_company_mode(db_session: AsyncSession):
    job = EnrichmentJob(
        mode="company", status="queued",
        target_json={"kind": "company", "siren": "123456789"},
    )
    db_session.add(job)
    await db_session.commit()

    await run_enrichment_job(db_session, job)

    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "done"
    stats = refreshed.stats_json
    assert stats["companies"] == 1
    assert stats["people_found"] == 3          # CTO/CPO/CMO (mock, 1 par role)
    assert stats["emails_found"] >= 1
    assert stats["valid"] >= 1

    # Contacts CRM crees (source enrichment)
    contacts = (
        await db_session.execute(select(Contact).where(Contact.source == "enrichment"))
    ).scalars().all()
    assert len(contacts) >= 1
    assert all(c.is_decision_maker for c in contacts)  # CTO/CPO/CMO
    assert all(c.title for c in contacts)

    # Verifications + provenance tracees
    n_verif = (
        await db_session.execute(select(func.count()).select_from(EnrichmentEmailVerification))
    ).scalar()
    n_prov = (
        await db_session.execute(select(func.count()).select_from(EnrichmentProvenance))
    ).scalar()
    assert n_verif >= 1
    assert n_prov >= 2   # name + email par contact


async def test_run_enrichment_job_idempotent(db_session: AsyncSession, monkeypatch):
    called = {"n": 0}
    orig = orchestrator._resolve_companies

    async def _spy(*a, **k):
        called["n"] += 1
        return await orig(*a, **k)

    monkeypatch.setattr(orchestrator, "_resolve_companies", _spy)
    job = EnrichmentJob(mode="company", status="done", target_json={"kind": "company", "siren": "1"})
    db_session.add(job)
    await db_session.commit()
    await run_enrichment_job(db_session, job)  # etat terminal -> no-op
    assert called["n"] == 0


async def test_rgpd_rejects_non_pro_emails(db_session: AsyncSession, monkeypatch):
    # Force le finder a renvoyer un email perso -> doit etre rejete (aucun contact).
    from app.services.enrichment import factory
    from app.services.enrichment.ports import EmailCandidate

    class _PersoFinder:
        name = "mock"
        cost_per_hit = 1.0

        async def find(self, person, domain):
            return EmailCandidate(email="perso@gmail.com", confidence=0.9, status="valid", source="mock")

    monkeypatch.setattr(factory, "get_email_finders", lambda: [_PersoFinder()])
    # re-importer la ref dans l'orchestrateur (il appelle get_email_finders au runtime)
    monkeypatch.setattr(orchestrator, "get_email_finders", lambda: [_PersoFinder()])

    job = EnrichmentJob(mode="company", status="queued", target_json={"kind": "company", "siren": "999"})
    db_session.add(job)
    await db_session.commit()
    await run_enrichment_job(db_session, job)

    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "done"
    # emails trouves mais tous perso -> 0 valid, 0 contact
    assert refreshed.stats_json["valid"] == 0
    contacts = (await db_session.execute(select(func.count()).select_from(Contact))).scalar()
    assert contacts == 0
