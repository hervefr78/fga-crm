"""Tests Feature B / P1 : update_contact_email (update contact existant + backfill
domaine societe + flags Icypeas + isolation org + anti-collision domaine)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.contact import Contact
from app.models.organization import Organization
from app.services.enrichment.crm_writer import update_contact_email


async def _setup(db: AsyncSession, org_id, *, company_domain=None):
    company = Company(name="Acme", organization_id=org_id, domain=company_domain)
    db.add(company)
    await db.flush()
    contact = Contact(
        first_name="A", last_name="B", organization_id=org_id, company_id=company.id, email=None
    )
    db.add(contact)
    await db.flush()
    return contact, company


@pytest.mark.asyncio
async def test_update_sets_email_flag_and_backfills_domain(db_session: AsyncSession, test_org):
    contact, company = await _setup(db_session, test_org.id)
    cid = await update_contact_email(
        db_session, contact_id=contact.id, email="a@acme.fr", email_status="valid",
        organization_id=test_org.id,
    )
    assert cid == contact.id
    await db_session.refresh(contact)
    await db_session.refresh(company)
    assert contact.email == "a@acme.fr"
    assert contact.email_status == "valid"
    assert contact.email_verified_by_icypeas is True
    assert company.domain == "acme.fr"  # backfill depuis l'email
    assert company.domain_verified_by_icypeas is True


@pytest.mark.asyncio
async def test_update_keeps_existing_company_domain(db_session: AsyncSession, test_org):
    contact, company = await _setup(db_session, test_org.id, company_domain="existing.fr")
    await update_contact_email(
        db_session, contact_id=contact.id, email="a@acme.fr", email_status="valid",
        organization_id=test_org.id,
    )
    await db_session.refresh(company)
    assert company.domain == "existing.fr"  # pas ecrase
    assert company.domain_verified_by_icypeas is False


@pytest.mark.asyncio
async def test_update_cross_org_is_noop(db_session: AsyncSession, test_org):
    contact, _ = await _setup(db_session, test_org.id)
    other = Organization(name="B", slug=f"b-{uuid.uuid4().hex[:8]}", is_active=True)
    db_session.add(other)
    await db_session.flush()

    res = await update_contact_email(
        db_session, contact_id=contact.id, email="x@y.fr", email_status="valid",
        organization_id=other.id,
    )
    assert res is None  # cross-org -> no-op
    await db_session.refresh(contact)
    assert contact.email is None  # inchange


@pytest.mark.asyncio
async def test_update_domain_collision_skips_backfill(db_session: AsyncSession, test_org):
    # une autre societe de l'org a deja le domaine acme.fr
    db_session.add(Company(name="Other", organization_id=test_org.id, domain="acme.fr"))
    await db_session.flush()
    contact, company = await _setup(db_session, test_org.id)  # company sans domaine

    await update_contact_email(
        db_session, contact_id=contact.id, email="a@acme.fr", email_status="valid",
        organization_id=test_org.id,
    )
    await db_session.refresh(company)
    assert company.domain is None  # backfill evite (collision org+domain)
    await db_session.refresh(contact)
    assert contact.email == "a@acme.fr"  # le contact est quand meme mis a jour
