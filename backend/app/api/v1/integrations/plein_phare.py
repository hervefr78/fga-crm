# =============================================================================
# FGA CRM - Integrations API : Plein Phare Digital (new-order + refund)
# =============================================================================

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.user import User
from app.schemas.integration import (
    PleinPhareCreatedFlags,
    PleinPhareNewOrderRequest,
    PleinPhareNewOrderResponse,
    PleinPhareRefundRequest,
    PleinPhareRefundResponse,
)

from ._auth import _require_plein_phare_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- POST /plein-phare/new-order ----------


def _plein_phare_deal_title(audit_order_id: str) -> str:
    return f"Plein Phare — Rapport Complet — {audit_order_id[:8]}"


@router.post(
    "/plein-phare/new-order",
    response_model=PleinPhareNewOrderResponse,
    status_code=201,
    dependencies=[Depends(_require_plein_phare_api_key)],
)
async def plein_phare_new_order(
    payload: PleinPhareNewOrderRequest,
    db: AsyncSession = Depends(get_db),
) -> PleinPhareNewOrderResponse:
    """Enregistrer une nouvelle commande Plein Phare Digital dans le CRM.

    Cree (ou retrouve) la Company, le Contact, et cree le Deal one-shot
    (stage=won). Idempotent par `audit_order_id` : un meme order ne cree
    jamais deux Deals.
    """
    # Owner = premier admin actif (service call, pas d'utilisateur connecte)
    admin = (await db.execute(
        select(User).where(User.role == "admin", User.is_active.is_(True)).limit(1)
    )).scalar_one_or_none()
    if admin is None:
        raise HTTPException(status_code=503, detail="No admin user found in CRM")

    # Isolation multi-tenant : toutes les entites creees appartiennent a l'org
    # de l'admin resolu (service call). Idempotence scopee a cette org.
    org_id = admin.organization_id

    created_company = False
    created_contact = False
    created_deal = False

    # 1. Trouver ou creer la Company
    #    Priorite : domaine email (unique en DB) → nom case-insensitive → creation
    email_str = str(payload.email)
    email_domain = email_str.split("@")[1] if "@" in email_str else None
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
            lead_source="plein-phare",
            owner_id=admin.id,
            organization_id=org_id,
        )
        db.add(company)
        await db.flush()
        created_company = True
    elif email_domain and not company.domain:
        # Enrichir la company existante avec le domaine si elle n'en avait pas
        company.domain = email_domain

    # 2. Trouver ou creer le Contact (idempotence par email, scopee org)
    contact = (await db.execute(
        select(Contact).where(
            Contact.email == email_str,
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
            first_name=payload.first_name or "-",
            last_name=payload.last_name or "-",
            email=email_str,
            phone=payload.phone,
            company_id=company.id,
            source="plein-phare",
            status="qualified",
            is_decision_maker=True,
            owner_id=admin.id,
            organization_id=org_id,
        )
        db.add(contact)
        await db.flush()
        created_contact = True

    # 3. Creer le Deal (idempotence par audit_order_id via le titre, scopee org)
    deal_title = _plein_phare_deal_title(payload.audit_order_id)
    existing_deal = (await db.execute(
        select(Deal).where(
            Deal.contact_id == contact.id,
            Deal.title == deal_title[:255],
            Deal.organization_id == org_id,
        )
    )).scalar_one_or_none()

    if existing_deal:
        deal = existing_deal
    else:
        description = (
            f"Commande Rapport Complet le {payload.paid_at.isoformat()}. "
            f"URL audit : {payload.audit_url or '-'}. "
            f"Stripe session: {payload.stripe_session_id or '-'}."
        )
        deal = Deal(
            id=uuid.uuid4(),
            title=deal_title[:255],
            stage="won",
            amount=payload.amount_eur,
            currency=payload.currency or "EUR",
            probability=100,
            pricing_type="one_shot",
            recurring_amount=None,
            commitment_months=None,
            actual_close_date=payload.paid_at.date(),
            company_id=company.id,
            contact_id=contact.id,
            description=description[:5000],
            owner_id=admin.id,
            organization_id=org_id,
        )
        db.add(deal)
        await db.flush()
        created_deal = True

    await db.commit()

    logger.info(
        "[Plein Phare] Nouveau client cree: company=%s contact=%s deal=%s "
        "audit_order=%s created=%s",
        company.id, contact.id, deal.id, payload.audit_order_id,
        {"company": created_company, "contact": created_contact, "deal": created_deal},
    )

    return PleinPhareNewOrderResponse(
        company_id=str(company.id),
        contact_id=str(contact.id),
        deal_id=str(deal.id),
        created=PleinPhareCreatedFlags(
            company=created_company,
            contact=created_contact,
            deal=created_deal,
        ),
    )


# ---------- POST /plein-phare/refund ----------


@router.post(
    "/plein-phare/refund",
    response_model=PleinPhareRefundResponse,
    status_code=200,
    dependencies=[Depends(_require_plein_phare_api_key)],
)
async def plein_phare_refund(
    payload: PleinPhareRefundRequest,
    db: AsyncSession = Depends(get_db),
) -> PleinPhareRefundResponse:
    """Marquer une commande Plein Phare comme remboursee (stage=lost)."""
    # Isolation multi-tenant : scoper la recherche du deal a l'org de l'admin
    # (service call, pas de user humain) pour ne pas rembourser un deal cross-org.
    admin = (await db.execute(
        select(User).where(User.role == "admin", User.is_active.is_(True)).limit(1)
    )).scalar_one_or_none()
    if admin is None:
        raise HTTPException(status_code=503, detail="No admin user found in CRM")
    org_id = admin.organization_id

    deal_title = _plein_phare_deal_title(payload.audit_order_id)
    deal = (await db.execute(
        select(Deal).where(
            Deal.title == deal_title[:255],
            Deal.organization_id == org_id,
        )
    )).scalar_one_or_none()

    if deal is None:
        logger.warning(
            "[Plein Phare] Refund recu pour audit_order=%s — deal introuvable",
            payload.audit_order_id,
        )
        raise HTTPException(status_code=404, detail="deal not found")

    old_stage = deal.stage
    deal.stage = "lost"
    refund_note = (
        f"\n[REFUND {payload.refunded_at.isoformat()}] {payload.reason or ''}"
    ).rstrip()
    deal.description = ((deal.description or "") + refund_note)[:5000]

    await db.commit()

    logger.info(
        "[Plein Phare] Refund applique: deal=%s audit_order=%s old_stage=%s",
        deal.id, payload.audit_order_id, old_stage,
    )

    return PleinPhareRefundResponse(
        deal_id=str(deal.id),
        old_stage=old_stage,
        new_stage="lost",
    )
