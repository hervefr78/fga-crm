"""Tests Feature B / P2 : mode 'contacts' de l'orchestrateur (inline) — trouve
l'email manquant + update, re-verification optionnelle, skip si deja rempli."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.contact import Contact
from app.models.enrichment import EnrichmentJob
from app.services.enrichment import orchestrator
from app.services.enrichment.ports import EmailCandidate, VerificationResult


class _AlwaysFinder:
    name = "fake-finder"
    cost_per_hit = 1.0

    async def find(self, person, domain_or_company):
        return EmailCandidate(
            email=f"{person.first_name}.{person.last_name}@{domain_or_company}".lower(),
            confidence=0.9, status="valid", source="fake",
        )


class _AlwaysVerifier:
    name = "fake-verifier"
    cost_per_check = 1.0

    async def verify(self, email):
        return VerificationResult(email=email, status="valid", confidence=0.95, source="fake")


def _wire(monkeypatch):
    monkeypatch.setattr(orchestrator, "get_email_finders", lambda: [_AlwaysFinder()])
    monkeypatch.setattr(orchestrator, "get_email_verifiers", lambda: [_AlwaysVerifier()])


async def _contact(db, org_id, *, email=None, domain="acme.fr"):
    company = Company(name="Acme", domain=domain, organization_id=org_id)
    db.add(company)
    await db.flush()
    contact = Contact(
        first_name="Julie", last_name="Martin", organization_id=org_id,
        company_id=company.id, email=email,
    )
    db.add(contact)
    await db.flush()
    return contact


async def _run(db, org_id, target):
    job = EnrichmentJob(mode="contacts", status="queued", target_json=target, organization_id=org_id)
    db.add(job)
    await db.commit()
    await orchestrator.run_enrichment_job(db, job)
    return job


@pytest.mark.asyncio
async def test_contacts_finds_missing_email_and_updates(db_session: AsyncSession, test_org, monkeypatch):
    _wire(monkeypatch)
    contact = await _contact(db_session, test_org.id, email=None)
    await db_session.commit()

    job = await _run(db_session, test_org.id, {"kind": "contacts", "contact_ids": [str(contact.id)]})
    assert job.status == "done"
    assert job.stats_json["updated"] == 1

    await db_session.refresh(contact)
    assert contact.email == "julie.martin@acme.fr"
    assert contact.email_status == "valid"
    assert contact.email_verified_by_icypeas is True


@pytest.mark.asyncio
async def test_contacts_skips_existing_email_without_reverify(db_session: AsyncSession, test_org, monkeypatch):
    _wire(monkeypatch)
    contact = await _contact(db_session, test_org.id, email="deja@acme.fr")
    await db_session.commit()

    job = await _run(db_session, test_org.id, {"kind": "contacts", "contact_ids": [str(contact.id)]})
    assert job.stats_json["skipped_has_email"] == 1
    assert job.stats_json["updated"] == 0
    await db_session.refresh(contact)
    assert contact.email == "deja@acme.fr"  # inchange
    assert contact.email_verified_by_icypeas is False


@pytest.mark.asyncio
async def test_contacts_reverify_existing_email(db_session: AsyncSession, test_org, monkeypatch):
    _wire(monkeypatch)
    contact = await _contact(db_session, test_org.id, email="deja@acme.fr")
    await db_session.commit()

    job = await _run(
        db_session, test_org.id,
        {"kind": "contacts", "contact_ids": [str(contact.id)], "reverify": True},
    )
    assert job.stats_json["updated"] == 1
    await db_session.refresh(contact)
    assert contact.email == "deja@acme.fr"  # meme email, re-verifie
    assert contact.email_status == "valid"
    assert contact.email_verified_by_icypeas is True


@pytest.mark.asyncio
async def test_contacts_all_missing_email_scope(db_session: AsyncSession, test_org, monkeypatch):
    _wire(monkeypatch)
    await _contact(db_session, test_org.id, email=None, domain="acme.fr")
    await _contact(db_session, test_org.id, email="a@beta.fr", domain="beta.fr")  # deja rempli -> ignore
    await db_session.commit()

    job = await _run(db_session, test_org.id, {"kind": "contacts", "all_missing_email": True})
    assert job.stats_json["updated"] == 1  # seul celui sans email
