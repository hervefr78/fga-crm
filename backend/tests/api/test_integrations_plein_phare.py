# =============================================================================
# FGA CRM - Tests API Integrations Plein Phare Digital
# =============================================================================

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.user import User

# ---------------------------------------------------------------------------
# Constantes & helpers
# ---------------------------------------------------------------------------

PLEIN_PHARE_KEY = "test-plein-phare-key"
NEW_ORDER_URL = "/api/v1/integrations/plein-phare/new-order"
REFUND_URL = "/api/v1/integrations/plein-phare/refund"


@pytest.fixture
def configured_api_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Configure une cle API Plein Phare valide pour les tests."""
    monkeypatch.setattr(settings, "plein_phare_api_key", PLEIN_PHARE_KEY)
    return PLEIN_PHARE_KEY


@pytest.fixture
def unset_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force la cle API serveur a vide pour tester le 503."""
    monkeypatch.setattr(settings, "plein_phare_api_key", "")


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession, test_org) -> User:
    """Cree un utilisateur admin actif (requis comme owner par l'endpoint)."""
    from app.core.security import hash_password

    user = User(
        id=uuid.uuid4(),
        email="admin-pp@fga.fr",
        hashed_password=hash_password("Admin1234!"),
        full_name="Admin PP",
        role="admin",
        is_active=True,
        organization_id=test_org.id,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _new_order_payload(**overrides) -> dict:
    """Payload minimal valide pour /plein-phare/new-order."""
    base = {
        "email": f"client-{uuid.uuid4().hex[:6]}@example.fr",
        "first_name": "Jean",
        "last_name": "Dupont",
        "company_name": "Dupont SARL",
        "phone": "+33611223344",
        "address_line": "1 rue de la Paix",
        "postal_code": "75002",
        "city": "Paris",
        "country": "France",
        "amount_eur": 299.0,
        "currency": "EUR",
        "audit_order_id": str(uuid.uuid4()),
        "audit_url": "https://example.fr",
        "paid_at": datetime(2026, 5, 6, 12, 0, 0, tzinfo=UTC).isoformat(),
        "stripe_session_id": "cs_test_abc123",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Auth — API key
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_server_key_returns_503(
    client: AsyncClient, unset_api_key: None, admin_user: User
):
    """Si la cle serveur est vide → 503 (integration non configuree)."""
    resp = await client.post(
        NEW_ORDER_URL,
        json=_new_order_payload(),
        headers={"X-PleinPhare-API-Key": "anything"},
    )
    assert resp.status_code == 503, resp.text
    assert "not configured" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_wrong_api_key_returns_401(
    client: AsyncClient, configured_api_key: str, admin_user: User
):
    """Si la cle fournie ne correspond pas → 401."""
    resp = await client.post(
        NEW_ORDER_URL,
        json=_new_order_payload(),
        headers={"X-PleinPhare-API-Key": "wrong-key"},
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_missing_header_returns_401(
    client: AsyncClient, configured_api_key: str, admin_user: User
):
    """Pas de header → 401 (None != cle valide)."""
    resp = await client.post(NEW_ORDER_URL, json=_new_order_payload())
    assert resp.status_code == 401, resp.text


# ---------------------------------------------------------------------------
# new-order — creation initiale
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_first_call_creates_all_three(
    client: AsyncClient,
    configured_api_key: str,
    admin_user: User,
    db_session: AsyncSession,
):
    """Premier POST avec un nouvel email → company, contact, deal tous crees."""
    payload = _new_order_payload(
        email="alice@nouvelle-acme.fr",
        company_name="Nouvelle Acme",
    )
    resp = await client.post(
        NEW_ORDER_URL,
        json=payload,
        headers={"X-PleinPhare-API-Key": PLEIN_PHARE_KEY},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert data["created"] == {"company": True, "contact": True, "deal": True}
    assert data["company_id"]
    assert data["contact_id"]
    assert data["deal_id"]

    # Verification DB
    company = (await db_session.execute(
        select(Company).where(Company.id == uuid.UUID(data["company_id"]))
    )).scalar_one()
    assert company.name == "Nouvelle Acme"
    assert company.domain == "nouvelle-acme.fr"
    assert company.lead_source == "plein-phare"
    assert company.owner_id == admin_user.id

    contact = (await db_session.execute(
        select(Contact).where(Contact.id == uuid.UUID(data["contact_id"]))
    )).scalar_one()
    assert contact.email == "alice@nouvelle-acme.fr"
    assert contact.source == "plein-phare"
    assert contact.status == "qualified"
    assert contact.is_decision_maker is True
    assert contact.company_id == company.id

    deal = (await db_session.execute(
        select(Deal).where(Deal.id == uuid.UUID(data["deal_id"]))
    )).scalar_one()
    assert deal.stage == "won"
    assert deal.pricing_type == "one_shot"
    assert deal.amount == 299.0
    assert deal.recurring_amount is None
    assert deal.commitment_months is None
    assert deal.probability == 100
    assert deal.contact_id == contact.id
    assert deal.company_id == company.id
    assert payload["audit_order_id"][:8] in deal.title


# ---------------------------------------------------------------------------
# new-order — idempotence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotent_same_audit_order_id(
    client: AsyncClient,
    configured_api_key: str,
    admin_user: User,
    db_session: AsyncSession,
):
    """Deux POST avec le meme audit_order_id → 1 seul Deal en DB."""
    payload = _new_order_payload(
        email="bob@idem-corp.fr",
        company_name="Idem Corp",
        audit_order_id=str(uuid.uuid4()),
    )

    resp1 = await client.post(
        NEW_ORDER_URL,
        json=payload,
        headers={"X-PleinPhare-API-Key": PLEIN_PHARE_KEY},
    )
    assert resp1.status_code == 201, resp1.text
    data1 = resp1.json()
    assert data1["created"]["deal"] is True

    resp2 = await client.post(
        NEW_ORDER_URL,
        json=payload,
        headers={"X-PleinPhare-API-Key": PLEIN_PHARE_KEY},
    )
    assert resp2.status_code == 201, resp2.text
    data2 = resp2.json()

    # Deuxieme appel : tout est reutilise
    assert data2["created"] == {"company": False, "contact": False, "deal": False}
    assert data2["deal_id"] == data1["deal_id"]
    assert data2["company_id"] == data1["company_id"]
    assert data2["contact_id"] == data1["contact_id"]

    # Verification DB : un seul Deal pour cet audit_order_id
    deals = (await db_session.execute(
        select(Deal).where(
            Deal.title == f"Plein Phare — Rapport Complet — {payload['audit_order_id'][:8]}"
        )
    )).scalars().all()
    assert len(deals) == 1


# ---------------------------------------------------------------------------
# new-order — dedup Company / Contact
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_existing_company_reused_by_domain(
    client: AsyncClient,
    configured_api_key: str,
    admin_user: User,
    db_session: AsyncSession,
):
    """Une Company avec domain=acme.fr existe deja → reutilisee, non recreee."""
    existing = Company(
        id=uuid.uuid4(),
        name="Acme Pre-existante",
        domain="acme.fr",
        lead_source="manual",
        owner_id=admin_user.id,
        organization_id=admin_user.organization_id,
    )
    db_session.add(existing)
    await db_session.commit()

    resp = await client.post(
        NEW_ORDER_URL,
        json=_new_order_payload(
            email="someone@acme.fr",
            company_name="Acme Pre-existante",
        ),
        headers={"X-PleinPhare-API-Key": PLEIN_PHARE_KEY},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["created"]["company"] is False
    assert data["company_id"] == str(existing.id)

    # Une seule Company avec ce domaine
    companies = (await db_session.execute(
        select(Company).where(Company.domain == "acme.fr")
    )).scalars().all()
    assert len(companies) == 1


@pytest.mark.asyncio
async def test_existing_contact_reused_by_email(
    client: AsyncClient,
    configured_api_key: str,
    admin_user: User,
    db_session: AsyncSession,
):
    """Un Contact avec email=foo@bar.fr existe deja → reutilise."""
    company = Company(
        id=uuid.uuid4(),
        name="Bar SA",
        domain="bar.fr",
        owner_id=admin_user.id,
        organization_id=admin_user.organization_id,
    )
    db_session.add(company)
    await db_session.flush()

    existing_contact = Contact(
        id=uuid.uuid4(),
        first_name="Foo",
        last_name="Bar",
        email="foo@bar.fr",
        company_id=company.id,
        owner_id=admin_user.id,
        organization_id=admin_user.organization_id,
    )
    db_session.add(existing_contact)
    await db_session.commit()

    resp = await client.post(
        NEW_ORDER_URL,
        json=_new_order_payload(
            email="foo@bar.fr",
            company_name="Bar SA",
        ),
        headers={"X-PleinPhare-API-Key": PLEIN_PHARE_KEY},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["created"]["contact"] is False
    assert data["contact_id"] == str(existing_contact.id)

    # Un seul Contact avec cet email
    contacts = (await db_session.execute(
        select(Contact).where(Contact.email == "foo@bar.fr")
    )).scalars().all()
    assert len(contacts) == 1


# ---------------------------------------------------------------------------
# refund
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refund_flips_deal_to_lost(
    client: AsyncClient,
    configured_api_key: str,
    admin_user: User,
    db_session: AsyncSession,
):
    """POST /refund sur un audit_order_id existant → deal stage='lost'."""
    # 1. Creer un order
    audit_order_id = str(uuid.uuid4())
    create_resp = await client.post(
        NEW_ORDER_URL,
        json=_new_order_payload(
            email="refund@example.fr",
            company_name="Refund Co",
            audit_order_id=audit_order_id,
        ),
        headers={"X-PleinPhare-API-Key": PLEIN_PHARE_KEY},
    )
    assert create_resp.status_code == 201, create_resp.text
    deal_id = create_resp.json()["deal_id"]

    # 2. Refund
    refund_resp = await client.post(
        REFUND_URL,
        json={
            "audit_order_id": audit_order_id,
            "refunded_at": datetime(2026, 5, 7, 10, 0, 0, tzinfo=UTC).isoformat(),
            "reason": "Client mecontent",
        },
        headers={"X-PleinPhare-API-Key": PLEIN_PHARE_KEY},
    )
    assert refund_resp.status_code == 200, refund_resp.text
    data = refund_resp.json()
    assert data["deal_id"] == deal_id
    assert data["old_stage"] == "won"
    assert data["new_stage"] == "lost"

    # Verification DB
    deal = (await db_session.execute(
        select(Deal).where(Deal.id == uuid.UUID(deal_id))
    )).scalar_one()
    assert deal.stage == "lost"
    assert "REFUND" in (deal.description or "")
    assert "Client mecontent" in (deal.description or "")


@pytest.mark.asyncio
async def test_refund_unknown_order_returns_404(
    client: AsyncClient,
    configured_api_key: str,
    admin_user: User,
):
    """Refund sur un audit_order_id inconnu → 404."""
    resp = await client.post(
        REFUND_URL,
        json={
            "audit_order_id": str(uuid.uuid4()),
            "refunded_at": datetime(2026, 5, 7, tzinfo=UTC).isoformat(),
            "reason": None,
        },
        headers={"X-PleinPhare-API-Key": PLEIN_PHARE_KEY},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["detail"] == "deal not found"
