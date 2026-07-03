"""Tests Feature B / P3 : mode contacts en bulk (contexte porte contact_id) +
webhook qui MET A JOUR le contact existant (au lieu de creer)."""

from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company
from app.models.contact import Contact
from app.models.enrichment import EnrichmentBulk, EnrichmentBulkItem, EnrichmentJob
from app.services.enrichment import orchestrator
from app.services.enrichment.adapters.icypeas import IcypeasClient
from app.services.enrichment.bulk_callback import process_bulk_callback


@pytest.mark.asyncio
async def test_contacts_bulk_submit_carries_contact_id(db_session: AsyncSession, test_org, monkeypatch):
    monkeypatch.setattr(settings, "icypeas_api_key", "k")
    monkeypatch.setattr(
        settings, "icypeas_webhook_url",
        "https://crm.example/api/v1/integrations/icypeas/webhook",
    )
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"success": True, "file": "CBULK1"})

    monkeypatch.setattr(orchestrator, "get_bulk_client",
                        lambda: IcypeasClient("k", transport=httpx.MockTransport(handler)))

    company = Company(name="Acme", domain="acme.fr", organization_id=test_org.id)
    db_session.add(company)
    await db_session.flush()
    contact = Contact(first_name="Julie", last_name="Martin", organization_id=test_org.id,
                      company_id=company.id, email=None)
    db_session.add(contact)
    await db_session.flush()
    job = EnrichmentJob(mode="contacts", status="queued",
                        target_json={"kind": "contacts", "contact_ids": [str(contact.id)]},
                        organization_id=test_org.id)
    db_session.add(job)
    await db_session.commit()

    await orchestrator.run_enrichment_job(db_session, job)

    assert job.status == "awaiting_results"  # bulk soumis, attend le webhook
    items = (await db_session.execute(select(EnrichmentBulkItem))).scalars().all()
    assert len(items) == 1
    assert items[0].context_json["contact_id"] == str(contact.id)  # mode update
    assert captured["body"]["data"][0] == ["Julie", "Martin", "acme.fr"]


@pytest.mark.asyncio
async def test_webhook_updates_existing_contact_not_create(db_session: AsyncSession, test_org):
    company = Company(name="Acme", domain=None, organization_id=test_org.id)
    db_session.add(company)
    await db_session.flush()
    contact = Contact(first_name="Julie", last_name="Martin", organization_id=test_org.id,
                      company_id=company.id, email=None)
    db_session.add(contact)
    await db_session.flush()
    job = EnrichmentJob(mode="contacts", status="awaiting_results", target_json={},
                        organization_id=test_org.id)
    db_session.add(job)
    await db_session.flush()
    bulk = EnrichmentBulk(file="CB2", task="email-search", status="awaiting_results", total=1,
                          organization_id=test_org.id, job_id=job.id)
    db_session.add(bulk)
    await db_session.flush()
    db_session.add(EnrichmentBulkItem(
        bulk_id=bulk.id, external_id="0", organization_id=test_org.id, status="pending",
        context_json={"contact_id": str(contact.id), "company": {"name": "Acme", "domain": None},
                      "person": {"first_name": "Julie", "last_name": "Martin"}},
    ))
    await db_session.commit()

    data = {"file": "CB2", "results": [
        {"results": {"emails": [{"email": "julie.martin@acme.fr", "certainty": "ultra_sure"}]},
         "status": "DEBITED", "userData": {"externalId": "0"}},
    ]}
    res = await process_bulk_callback(db_session, data)
    assert res["found"] == 1

    await db_session.refresh(contact)
    await db_session.refresh(company)
    assert contact.email == "julie.martin@acme.fr"
    assert contact.email_verified_by_icypeas is True
    assert company.domain == "acme.fr"  # backfill depuis l'email Icypeas
    assert company.domain_verified_by_icypeas is True

    # aucun NOUVEAU contact cree (update, pas create)
    all_contacts = (await db_session.execute(select(Contact))).scalars().all()
    assert len(all_contacts) == 1
