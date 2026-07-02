"""Contraintes UNIQUE multi-tenant (fix bug hunt #1/#2) : domain et startup_radar_id
doivent etre uniques PAR organisation, pas globalement."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.contact import Contact
from app.models.organization import Organization


async def _org(db: AsyncSession) -> Organization:
    org = Organization(name="Org", slug=f"org-{uuid.uuid4().hex[:8]}", is_active=True)
    db.add(org)
    await db.flush()
    return org


@pytest.mark.asyncio
async def test_same_domain_allowed_across_orgs(db_session: AsyncSession):
    a, b = await _org(db_session), await _org(db_session)
    db_session.add(Company(name="Acme A", domain="acme.fr", organization_id=a.id))
    db_session.add(Company(name="Acme B", domain="acme.fr", organization_id=b.id))
    await db_session.commit()  # composite (org, domain) -> OK cross-org


@pytest.mark.asyncio
async def test_same_domain_blocked_within_org(db_session: AsyncSession):
    a = await _org(db_session)
    db_session.add(Company(name="Acme 1", domain="dup.fr", organization_id=a.id))
    await db_session.flush()
    db_session.add(Company(name="Acme 2", domain="dup.fr", organization_id=a.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_same_startup_radar_id_allowed_across_orgs(db_session: AsyncSession):
    a, b = await _org(db_session), await _org(db_session)
    db_session.add(Company(name="C A", startup_radar_id="SR-42", organization_id=a.id))
    db_session.add(Company(name="C B", startup_radar_id="SR-42", organization_id=b.id))
    db_session.add(Contact(first_name="X", last_name="A", startup_radar_id="SR-99", organization_id=a.id))
    db_session.add(Contact(first_name="Y", last_name="B", startup_radar_id="SR-99", organization_id=b.id))
    await db_session.commit()  # composite (org, startup_radar_id) -> OK cross-org


@pytest.mark.asyncio
async def test_same_startup_radar_id_blocked_within_org(db_session: AsyncSession):
    a = await _org(db_session)
    db_session.add(Company(name="C1", startup_radar_id="SR-1", organization_id=a.id))
    await db_session.flush()
    db_session.add(Company(name="C2", startup_radar_id="SR-1", organization_id=a.id))
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_null_domain_multiple_allowed_same_org(db_session: AsyncSession):
    # domain NULL -> distincts : plusieurs societes sans domaine dans la meme org
    a = await _org(db_session)
    db_session.add(Company(name="No domain 1", domain=None, organization_id=a.id))
    db_session.add(Company(name="No domain 2", domain=None, organization_id=a.id))
    await db_session.commit()
