# =============================================================================
# FGA CRM - Integrations API : Nomo-IA (new-subscription)
# =============================================================================

import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.user import User
from app.schemas.integration import (
    NomoNewSubscriptionRequest,
    NomoNewSubscriptionResponse,
)

from ._auth import require_nomo_key_user, resolve_integration_owner

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- POST /nomo-ia/new-subscription ----------

_PLAN_PRICING_TYPE: dict[str, str] = {
    "monthly": "monthly",
    "semi_annual": "biannual",
    "yearly": "annual",
}


@router.post(
    "/nomo-ia/new-subscription",
    response_model=NomoNewSubscriptionResponse,
    status_code=201,
)
async def nomo_new_subscription(
    payload: NomoNewSubscriptionRequest,
    key_user: User | None = Depends(require_nomo_key_user),
    db: AsyncSession = Depends(get_db),
) -> NomoNewSubscriptionResponse:
    """Enregistrer un nouveau client Nomo-IA dans le CRM.

    Cree (ou retrouve) la Company, cree le Contact et le Deal (stage=won).
    Appelee par Marketing Assistant apres checkout.session.completed.
    """
    # Isolation multi-tenant (DC18 — FIX #6) : owner + org resolus depuis la cle
    # API authentifiee (Bearer crm_xxx). Le fallback legacy (header partage, sans
    # org) retombe sur le premier admin actif. Les recherches d'idempotence sont
    # scopees a cette org (pas de dedup cross-org).
    owner, org_id = await resolve_integration_owner(db, key_user)

    # 1. Trouver ou creer la Company
    #    Priorite : domaine email (unique en DB) → nom case-insensitive → creation
    email_domain = payload.email.split("@")[1] if "@" in payload.email else None
    company: Company | None = None

    if email_domain:
        company = (await db.execute(
            select(Company).where(
                Company.domain == email_domain,
                Company.organization_id == org_id,
            )
        )).scalar_one_or_none()

    if not company:
        company = (await db.execute(
            select(Company).where(
                func.lower(Company.name) == payload.company_name.lower(),
                Company.organization_id == org_id,
            )
        )).scalar_one_or_none()

    if not company:
        company = Company(
            id=uuid.uuid4(),
            name=payload.company_name,
            domain=email_domain,
            phone=payload.phone,
            address_line=payload.address_line,
            postal_code=payload.postal_code,
            city=payload.city,
            country=payload.country or "France",
            lead_source="nomo-ia",
            owner_id=owner.id,
            organization_id=org_id,
        )
        db.add(company)
        await db.flush()
    elif email_domain and not company.domain:
        # Enrichir la company existante avec le domaine si elle n'en avait pas
        company.domain = email_domain

    # 2. Trouver ou creer le Contact (idempotence par email, scopee org)
    contact = (await db.execute(
        select(Contact).where(
            Contact.email == payload.email,
            Contact.organization_id == org_id,
        )
    )).scalar_one_or_none()

    if contact:
        # Relier a la company si pas encore fait
        if not contact.company_id:
            contact.company_id = company.id
    else:
        contact = Contact(
            id=uuid.uuid4(),
            first_name=payload.first_name,
            last_name=payload.last_name or "-",
            email=payload.email,
            phone=payload.phone,
            company_id=company.id,
            source="nomo-ia",
            status="qualified",
            is_decision_maker=True,
            owner_id=owner.id,
            organization_id=org_id,
        )
        db.add(contact)
        await db.flush()

    # 3. Creer le Deal (idempotence : verifier si un deal identique existe deja, scopee org)
    pricing_type = _PLAN_PRICING_TYPE.get(payload.billing_cycle, "monthly")
    deal_title = f"Nomo-IA — {payload.plan.capitalize()} — {payload.company_name}"
    existing_deal = (await db.execute(
        select(Deal).where(
            Deal.contact_id == contact.id,
            Deal.title == deal_title[:255],
            Deal.stage == "won",
            Deal.organization_id == org_id,
        )
    )).scalar_one_or_none()

    if existing_deal:
        deal = existing_deal
    else:
        deal = Deal(
            id=uuid.uuid4(),
            title=deal_title[:255],
            stage="won",
            amount=payload.amount_eur,
            currency="EUR",
            probability=100,
            pricing_type=pricing_type,
            recurring_amount=payload.amount_eur,
            commitment_months=None,
            company_id=company.id,
            contact_id=contact.id,
            description=f"Souscription Nomo-IA le {payload.subscription_date}. Plan : {payload.plan}.",
            owner_id=owner.id,
            organization_id=org_id,
        )
        db.add(deal)

    await db.commit()

    logger.info(
        "[Nomo-IA] Nouveau client cree: company=%s contact=%s deal=%s plan=%s",
        company.id, contact.id, deal.id, payload.plan,
    )

    return NomoNewSubscriptionResponse(
        company_id=str(company.id),
        contact_id=str(contact.id),
        deal_id=str(deal.id),
    )
