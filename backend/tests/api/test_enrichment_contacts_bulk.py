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
from app.services.enrichment.modes import contacts as contacts_mode


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

    # C4 : _submit_bulk_contacts vit desormais dans modes.contacts -> patch a cet endroit
    monkeypatch.setattr(contacts_mode, "get_bulk_client",
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


@pytest.mark.asyncio
async def test_reverify_submits_search_and_verify_bulks(db_session: AsyncSession, test_org, monkeypatch):
    monkeypatch.setattr(settings, "icypeas_api_key", "k")
    monkeypatch.setattr(
        settings, "icypeas_webhook_url",
        "https://crm.example/api/v1/integrations/icypeas/webhook",
    )
    bodies: list[dict] = []
    files = iter(["SEARCH1", "VERIFY1"])

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"success": True, "file": next(files)})

    # C4 : _submit_bulk_contacts vit desormais dans modes.contacts -> patch a cet endroit
    monkeypatch.setattr(contacts_mode, "get_bulk_client",
                        lambda: IcypeasClient("k", transport=httpx.MockTransport(handler)))

    co1 = Company(name="Acme", domain="acme.fr", organization_id=test_org.id)
    co2 = Company(name="Beta", domain="beta.fr", organization_id=test_org.id)
    db_session.add_all([co1, co2])
    await db_session.flush()
    c_missing = Contact(first_name="Julie", last_name="Martin", organization_id=test_org.id,
                        company_id=co1.id, email=None)
    c_filled = Contact(first_name="Marc", last_name="Bernard", organization_id=test_org.id,
                       company_id=co2.id, email="marc@beta.fr")
    db_session.add_all([c_missing, c_filled])
    await db_session.flush()
    job = EnrichmentJob(mode="contacts", status="queued",
                        target_json={"kind": "contacts",
                                     "contact_ids": [str(c_missing.id), str(c_filled.id)],
                                     "reverify": True},
                        organization_id=test_org.id)
    db_session.add(job)
    await db_session.commit()

    await orchestrator.run_enrichment_job(db_session, job)

    assert job.status == "awaiting_results"
    bulks = (await db_session.execute(select(EnrichmentBulk))).scalars().all()
    assert {b.task for b in bulks} == {"email-search", "email-verification"}
    # 1er body = search ([first,last,domainOrCompany]), 2e = verify ([email])
    tasks_sent = {b["task"]: b["data"] for b in bodies}
    assert tasks_sent["email-search"] == [["Julie", "Martin", "acme.fr"]]
    assert tasks_sent["email-verification"] == [["marc@beta.fr"]]


@pytest.mark.asyncio
async def test_webhook_verify_updates_status_skipping_rgpd(db_session: AsyncSession, test_org):
    # Email PERSO deja en base : le reverify (email-verification) ne doit PAS le
    # rejeter au filtre RGPD, juste rafraichir son statut de deliverabilite.
    contact = Contact(first_name="J", last_name="M", email="j@gmail.com",
                      organization_id=test_org.id)
    db_session.add(contact)
    await db_session.flush()
    job = EnrichmentJob(mode="contacts", status="awaiting_results", target_json={},
                        organization_id=test_org.id)
    db_session.add(job)
    await db_session.flush()
    bulk = EnrichmentBulk(file="V1", task="email-verification", status="awaiting_results",
                          total=1, organization_id=test_org.id, job_id=job.id)
    db_session.add(bulk)
    await db_session.flush()
    db_session.add(EnrichmentBulkItem(
        bulk_id=bulk.id, external_id="0", organization_id=test_org.id, status="pending",
        context_json={"contact_id": str(contact.id), "person": {"first_name": "J", "last_name": "M"}},
    ))
    await db_session.commit()

    data = {"file": "V1", "results": [
        {"results": {"emails": [{"email": "j@gmail.com", "certainty": "undeliverable"}]},
         "status": "DEBITED", "userData": {"externalId": "0"}},
    ]}
    await process_bulk_callback(db_session, data)

    await db_session.refresh(contact)
    assert contact.email == "j@gmail.com"
    assert contact.email_status == "invalid"  # undeliverable, malgre gmail (pas de RGPD block)
    assert contact.email_verified_by_icypeas is True


@pytest.mark.asyncio
async def test_multi_bulk_job_done_only_when_all_bulks_done(db_session: AsyncSession, test_org):
    job = EnrichmentJob(mode="contacts", status="awaiting_results", target_json={},
                        organization_id=test_org.id)
    db_session.add(job)
    await db_session.flush()
    b_search = EnrichmentBulk(file="S", task="email-search", status="awaiting_results", total=1,
                              organization_id=test_org.id, job_id=job.id)
    b_verify = EnrichmentBulk(file="V", task="email-verification", status="awaiting_results", total=1,
                              organization_id=test_org.id, job_id=job.id)
    db_session.add_all([b_search, b_verify])
    await db_session.flush()
    db_session.add(EnrichmentBulkItem(bulk_id=b_search.id, external_id="0", organization_id=test_org.id,
                                      status="pending", context_json={}))
    db_session.add(EnrichmentBulkItem(bulk_id=b_verify.id, external_id="0", organization_id=test_org.id,
                                      status="pending", context_json={}))
    await db_session.commit()

    # 1er callback (search, non trouve) -> job PAS encore done (verify en attente)
    await process_bulk_callback(db_session, {"file": "S", "results": [
        {"results": {}, "status": "NOT_FOUND", "userData": {"externalId": "0"}}]})
    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "awaiting_results"

    # 2e callback (verify) -> tous les bulks done -> job done
    await process_bulk_callback(db_session, {"file": "V", "results": [
        {"results": {}, "status": "NOT_FOUND", "userData": {"externalId": "0"}}]})
    refreshed = await db_session.get(EnrichmentJob, job.id)
    assert refreshed.status == "done"


async def _seed_verify_item(db, org_id, file_id, contact, ctx_extra=None):
    job = EnrichmentJob(mode="contacts", status="awaiting_results", target_json={}, organization_id=org_id)
    db.add(job)
    await db.flush()
    bulk = EnrichmentBulk(file=file_id, task="email-verification", status="awaiting_results",
                          total=1, organization_id=org_id, job_id=job.id)
    db.add(bulk)
    await db.flush()
    ctx = {"contact_id": str(contact.id), "email": contact.email,
           "person": {"first_name": contact.first_name, "last_name": contact.last_name}}
    if ctx_extra:
        ctx.update(ctx_extra)
    db.add(EnrichmentBulkItem(bulk_id=bulk.id, external_id="0", organization_id=org_id,
                              status="pending", context_json=ctx))
    await db.commit()


@pytest.mark.asyncio
async def test_reverify_notfound_marks_contact_invalid(db_session: AsyncSession, test_org):
    # #7/#8 : un email 'valid' devenu injoignable (NOT_FOUND) -> contact 'invalid'
    contact = Contact(first_name="J", last_name="M", email="dead@old.com", email_status="valid",
                      organization_id=test_org.id)
    db_session.add(contact)
    await db_session.flush()
    await _seed_verify_item(db_session, test_org.id, "VN", contact)

    await process_bulk_callback(db_session, {"file": "VN", "results": [
        {"results": {"emails": []}, "status": "NOT_FOUND", "userData": {"externalId": "0"}}]})

    await db_session.refresh(contact)
    assert contact.email == "dead@old.com"  # email inchange
    assert contact.email_status == "invalid"  # etait valid -> maintenant invalid
    assert contact.email_verified_by_icypeas is True


@pytest.mark.asyncio
async def test_reverify_suppressed_email_not_marked_deliverable(db_session: AsyncSession, test_org):
    # #12 : la suppression RGPD est verifiee meme en reverify
    from app.models.enrichment import EnrichmentSuppression
    contact = Contact(first_name="J", last_name="M", email="opt@out.com", email_status="valid",
                      organization_id=test_org.id)
    db_session.add(contact)
    db_session.add(EnrichmentSuppression(organization_id=test_org.id, email="opt@out.com", reason="opt-out"))
    await db_session.flush()
    await _seed_verify_item(db_session, test_org.id, "VS", contact)

    await process_bulk_callback(db_session, {"file": "VS", "results": [
        {"results": {"emails": [{"email": "opt@out.com", "certainty": "ultra_sure"}]},
         "status": "DEBITED", "userData": {"externalId": "0"}}]})

    await db_session.refresh(contact)
    assert contact.email_verified_by_icypeas is False  # supprime -> pas de MAJ deliverable


@pytest.mark.asyncio
async def test_callback_on_error_bulk_is_noop(db_session: AsyncSession, test_org):
    # #9 : callback tardif sur un bulk 'error' (timeout reconcile) -> no-op
    job = EnrichmentJob(mode="batch", status="failed", target_json={}, organization_id=test_org.id)
    db_session.add(job)
    await db_session.flush()
    bulk = EnrichmentBulk(file="ERR", task="email-search", status="error", total=1,
                          organization_id=test_org.id, job_id=job.id)
    db_session.add(bulk)
    await db_session.flush()
    db_session.add(EnrichmentBulkItem(bulk_id=bulk.id, external_id="0", organization_id=test_org.id,
                                      status="pending", context_json={"company": {"name": "X"}, "person": {}}))
    await db_session.commit()

    res = await process_bulk_callback(db_session, {"file": "ERR", "results": [
        {"results": {"emails": [{"email": "a@acme.fr", "certainty": "ultra_sure"}]},
         "status": "DEBITED", "userData": {"externalId": "0"}}]})
    assert res.get("already_done") is True
    contacts = (await db_session.execute(select(Contact).where(Contact.source == "enrichment"))).scalars().all()
    assert contacts == []  # aucun contact recree
