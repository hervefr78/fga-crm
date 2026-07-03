# =============================================================================
# FGA CRM - Tests API Integrations Nomo-IA (isolation multi-tenant — FIX #6)
# =============================================================================
"""Verrouille le FIX #6 : le webhook Nomo-IA ecrit dans l'org de la CLE API
authentifiee (Bearer crm_xxx), et non plus dans l'org du premier admin global.

Setup : org A avec un admin cree EN PREMIER (ce que l'ancien code aurait choisi),
org B avec un service account + une cle API. Un POST authentifie avec la cle de B
doit creer Company/Contact/Deal dans l'org B.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.organization import Organization
from app.models.user import User
from app.services.api_keys import create_api_key

NEW_SUBSCRIPTION_URL = "/api/v1/integrations/nomo-ia/new-subscription"


def _subscription_payload(**overrides) -> dict:
    """Payload minimal valide pour /nomo-ia/new-subscription."""
    base = {
        "company_name": "Beta Corp",
        "first_name": "Bruno",
        "last_name": "Bernard",
        "email": f"client-{uuid.uuid4().hex[:6]}@beta-corp.fr",
        "phone": "+33600000000",
        "plan": "pro",
        "amount_eur": 99.0,
        "billing_cycle": "monthly",
        "subscription_date": "2026-06-01",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Fixtures : org A (admin cree en premier) + org B (service account + cle API)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def admin_a(db_session: AsyncSession, test_org: Organization) -> User:
    """Admin de l'org A, cree EN PREMIER (piege : ancien code = premier admin global)."""
    from app.core.security import hash_password

    user = User(
        id=uuid.uuid4(),
        email="admin-a-nomo@fga.fr",
        hashed_password=hash_password("Admin1234!"),
        full_name="Admin A",
        role="admin",
        is_active=True,
        organization_id=test_org.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def org_b(db_session: AsyncSession) -> Organization:
    org = Organization(
        id=uuid.uuid4(),
        name="Org B Nomo",
        slug=f"orgb-nomo-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest_asyncio.fixture
async def service_user_b(db_session: AsyncSession, org_b: Organization) -> User:
    """Service account rattache a l'org B (proprietaire de la cle API)."""
    user = User(
        id=uuid.uuid4(),
        email="nomo-b@crm.internal",
        hashed_password="$2b$12$disabled",
        full_name="Nomo Service B",
        role="service",
        is_active=True,
        is_service=True,
        organization_id=org_b.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def api_key_b(
    db_session: AsyncSession, service_user_b: User
) -> str:
    """Cle API valide (Bearer crm_xxx) pour le service account de l'org B."""
    _, raw_key = await create_api_key(
        db=db_session,
        user_id=service_user_b.id,
        name="nomo-key-b",
        scopes=["write:contacts"],
    )
    await db_session.commit()
    return raw_key


# ---------------------------------------------------------------------------
# FIX #6 : les ecritures suivent l'org de la cle API, pas l'org du premier admin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bearer_key_writes_into_key_org_not_first_admin_org(
    client: AsyncClient,
    admin_a: User,
    org_b: Organization,
    service_user_b: User,
    api_key_b: str,
    db_session: AsyncSession,
):
    """POST avec Bearer <cle de B> → Company/Contact/Deal dans l'org B (pas l'org A).

    Sans le fix, l'endpoint ignorait la cle et taguait l'org du premier admin
    global (org A) : fuite cross-org.
    """
    payload = _subscription_payload(
        email="alice@beta-corp.fr", company_name="Beta Corp"
    )
    resp = await client.post(
        NEW_SUBSCRIPTION_URL,
        json=payload,
        headers={"Authorization": f"Bearer {api_key_b}"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    company = (await db_session.execute(
        select(Company).where(Company.id == uuid.UUID(data["company_id"]))
    )).scalar_one()
    contact = (await db_session.execute(
        select(Contact).where(Contact.id == uuid.UUID(data["contact_id"]))
    )).scalar_one()
    deal = (await db_session.execute(
        select(Deal).where(Deal.id == uuid.UUID(data["deal_id"]))
    )).scalar_one()

    # Cœur du FIX #6 : org de la cle (B), PAS org du premier admin (A).
    assert company.organization_id == org_b.id
    assert contact.organization_id == org_b.id
    assert deal.organization_id == org_b.id
    assert company.organization_id != admin_a.organization_id

    # Owner = le service account de la cle (org B).
    assert company.owner_id == service_user_b.id
    assert contact.owner_id == service_user_b.id
    assert deal.owner_id == service_user_b.id


@pytest.mark.asyncio
async def test_invalid_bearer_key_returns_401(
    client: AsyncClient, admin_a: User
):
    """Une cle crm_xxx inconnue → 401 (jamais de fallback silencieux)."""
    resp = await client.post(
        NEW_SUBSCRIPTION_URL,
        json=_subscription_payload(),
        headers={"Authorization": "Bearer crm_" + "0" * 64},
    )
    assert resp.status_code == 401, resp.text
