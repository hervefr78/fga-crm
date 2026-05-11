# =============================================================================
# FGA CRM - Integrations API (Startup Radar sync + audit avance + Nomo-IA)
# =============================================================================

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.rbac import check_entity_access
from app.db.session import get_db
from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.user import User
from app.schemas.integration import (
    CompanyAuditResponse,
    SyncResultResponse,
    SyncStatusResponse,
)
from app.services.startup_radar import StartupRadarClient, StartupRadarError
from app.services.startup_radar_sync import (
    full_sync,
    get_last_sync_result,
    sync_recent_startups,
)

logger = logging.getLogger(__name__)


# ---------- Schemas Nomo-IA ----------


class NomoNewSubscriptionRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field("", max_length=255)
    email: str = Field(..., max_length=255)
    phone: str | None = Field(None, max_length=50)
    address_line: str | None = Field(None, max_length=500)
    postal_code: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    plan: str = Field(..., max_length=100)
    amount_eur: float = Field(..., ge=0)
    billing_cycle: str = Field("monthly", max_length=20)
    subscription_date: str = Field(..., max_length=30)


class NomoNewSubscriptionResponse(BaseModel):
    company_id: str
    contact_id: str
    deal_id: str


# ---------- Schemas Plein Phare Digital ----------


class PleinPhareNewOrderRequest(BaseModel):
    """Webhook entrant : nouvelle commande "Rapport Complet" one-shot."""

    email: EmailStr
    first_name: str | None = Field(None, max_length=255)
    last_name: str | None = Field(None, max_length=255)
    company_name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=50)
    address_line: str | None = Field(None, max_length=500)
    postal_code: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=100)
    country: str | None = Field("France", max_length=100)
    amount_eur: float = Field(..., ge=0)
    currency: str = Field("EUR", max_length=3)
    audit_order_id: str = Field(..., min_length=1, max_length=64)
    audit_url: str | None = Field(None, max_length=2048)
    paid_at: datetime
    stripe_session_id: str | None = Field(None, max_length=255)


class PleinPhareCreatedFlags(BaseModel):
    company: bool
    contact: bool
    deal: bool


class PleinPhareNewOrderResponse(BaseModel):
    company_id: str
    contact_id: str
    deal_id: str
    created: PleinPhareCreatedFlags


class PleinPhareRefundRequest(BaseModel):
    audit_order_id: str = Field(..., min_length=1, max_length=64)
    refunded_at: datetime
    reason: str | None = Field(None, max_length=500)


class PleinPhareRefundResponse(BaseModel):
    deal_id: str
    old_stage: str
    new_stage: str


router = APIRouter()


# ---------- POST /nomo-ia/new-subscription ----------

_PLAN_PRICING_TYPE: dict[str, str] = {
    "monthly": "monthly",
    "semi_annual": "biannual",
    "yearly": "annual",
}


async def _require_nomo_api_key(x_nomo_api_key: str | None = Header(None)) -> None:
    if not settings.nomo_api_key:
        raise HTTPException(status_code=503, detail="Nomo-IA integration not configured")
    if x_nomo_api_key != settings.nomo_api_key:
        raise HTTPException(status_code=401, detail="Invalid Nomo-IA API key")


@router.post(
    "/nomo-ia/new-subscription",
    response_model=NomoNewSubscriptionResponse,
    status_code=201,
    dependencies=[Depends(_require_nomo_api_key)],
)
async def nomo_new_subscription(
    payload: NomoNewSubscriptionRequest,
    db: AsyncSession = Depends(get_db),
) -> NomoNewSubscriptionResponse:
    """Enregistrer un nouveau client Nomo-IA dans le CRM.

    Cree (ou retrouve) la Company, cree le Contact et le Deal (stage=won).
    Appelee par Marketing Assistant apres checkout.session.completed.
    """
    # Owner = premier admin (service call, pas d'utilisateur connecte)
    admin = (await db.execute(
        select(User).where(User.role == "admin", User.is_active.is_(True)).limit(1)
    )).scalar_one_or_none()
    if admin is None:
        raise HTTPException(status_code=503, detail="No admin user found in CRM")

    # 1. Trouver ou creer la Company
    #    Priorite : domaine email (unique en DB) → nom case-insensitive → creation
    email_domain = payload.email.split("@")[1] if "@" in payload.email else None
    company: Company | None = None

    if email_domain:
        company = (await db.execute(
            select(Company).where(Company.domain == email_domain)
        )).scalar_one_or_none()

    if not company:
        company = (await db.execute(
            select(Company).where(
                func.lower(Company.name) == payload.company_name.lower()
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
            owner_id=admin.id,
        )
        db.add(company)
        await db.flush()
    elif email_domain and not company.domain:
        # Enrichir la company existante avec le domaine si elle n'en avait pas
        company.domain = email_domain

    # 2. Trouver ou creer le Contact (idempotence par email)
    contact = (await db.execute(
        select(Contact).where(Contact.email == payload.email)
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
            owner_id=admin.id,
        )
        db.add(contact)
        await db.flush()

    # 3. Creer le Deal (idempotence : verifier si un deal identique existe deja)
    pricing_type = _PLAN_PRICING_TYPE.get(payload.billing_cycle, "monthly")
    deal_title = f"Nomo-IA — {payload.plan.capitalize()} — {payload.company_name}"
    existing_deal = (await db.execute(
        select(Deal).where(
            Deal.contact_id == contact.id,
            Deal.title == deal_title[:255],
            Deal.stage == "won",
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
            owner_id=admin.id,
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


# ---------- POST /plein-phare/new-order ----------


async def _require_plein_phare_api_key(
    x_pleinphare_api_key: str | None = Header(None, alias="X-PleinPhare-API-Key"),
) -> None:
    if not settings.plein_phare_api_key:
        raise HTTPException(
            status_code=503, detail="Plein Phare integration not configured"
        )
    if x_pleinphare_api_key != settings.plein_phare_api_key:
        raise HTTPException(status_code=401, detail="Invalid Plein Phare API key")


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
            select(Company).where(Company.domain == email_domain)
        )).scalar_one_or_none()

    if not company:
        company = (await db.execute(
            select(Company).where(
                func.lower(Company.name) == payload.company_name.lower()
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
        )
        db.add(company)
        await db.flush()
        created_company = True
    elif email_domain and not company.domain:
        # Enrichir la company existante avec le domaine si elle n'en avait pas
        company.domain = email_domain

    # 2. Trouver ou creer le Contact (idempotence par email)
    contact = (await db.execute(
        select(Contact).where(Contact.email == email_str)
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
        )
        db.add(contact)
        await db.flush()
        created_contact = True

    # 3. Creer le Deal (idempotence par audit_order_id via le titre)
    deal_title = _plein_phare_deal_title(payload.audit_order_id)
    existing_deal = (await db.execute(
        select(Deal).where(
            Deal.contact_id == contact.id,
            Deal.title == deal_title[:255],
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
    deal_title = _plein_phare_deal_title(payload.audit_order_id)
    deal = (await db.execute(
        select(Deal).where(Deal.title == deal_title[:255])
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


# ---------- POST /startup-radar/sync ----------


@router.post("/startup-radar/sync", response_model=SyncResultResponse, status_code=200)
async def sync_startup_radar(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lancer une synchronisation complete Startup Radar → CRM.

    Les entites creees appartiennent a l'utilisateur qui lance le sync.
    """
    try:
        result = await full_sync(db, current_user)
    except StartupRadarError as e:
        logger.error("[Integrations] Erreur sync SR: %s", e)
        raise HTTPException(status_code=503, detail=f"Erreur Startup Radar: {e}") from e

    return SyncResultResponse(
        companies_created=result.companies_created,
        companies_updated=result.companies_updated,
        contacts_created=result.contacts_created,
        contacts_updated=result.contacts_updated,
        investors_created=result.investors_created,
        investors_updated=result.investors_updated,
        audits_created=result.audits_created,
        funding_activities_created=result.funding_activities_created,
        qualification_tasks_created=result.qualification_tasks_created,
        errors=result.errors,
    )


# ---------- POST /startup-radar/sync-recent-funding ----------


@router.post(
    "/startup-radar/sync-recent-funding",
    response_model=SyncResultResponse,
    status_code=200,
)
async def sync_recent_funding(
    days_back: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SyncResultResponse:
    """Synchroniser uniquement les startups SR creees/modifiees recemment.

    Cible : ramener les nouvelles levees detectees par le pipeline SR
    multi-source (LesPepitesTech, Maddyness, Eldorado, L'Usine Digitale, BODACC)
    sans refaire une full sync (couteuse).

    Cree pour chaque startup avec amount > 0 :
    - Activity 'funding_detected' (idempotent par subject incluant montant+serie)
    - Task 'qualification' (idempotent : 1 task ouverte par company a la fois)

    Args:
        days_back: fenetre de remontee en jours (defaut 7, max 90).
    """
    # DC1 — borner days_back
    if days_back < 1 or days_back > 90:
        raise HTTPException(
            status_code=422,
            detail="days_back doit etre entre 1 et 90",
        )

    try:
        result = await sync_recent_startups(db, current_user, days_back=days_back)
    except StartupRadarError as e:
        logger.error("[Integrations] Erreur sync-recent-funding: %s", e)
        raise HTTPException(
            status_code=503, detail=f"Erreur Startup Radar: {e}",
        ) from e

    return SyncResultResponse(
        companies_created=result.companies_created,
        companies_updated=result.companies_updated,
        contacts_created=result.contacts_created,
        contacts_updated=result.contacts_updated,
        investors_created=result.investors_created,
        investors_updated=result.investors_updated,
        audits_created=result.audits_created,
        funding_activities_created=result.funding_activities_created,
        qualification_tasks_created=result.qualification_tasks_created,
        errors=result.errors,
    )


# ---------- GET /startup-radar/status ----------


@router.get("/startup-radar/status", response_model=SyncStatusResponse)
async def get_sync_status(
    current_user: User = Depends(get_current_user),
):
    """Retourner le statut de la derniere synchronisation."""
    last = get_last_sync_result()

    if last is None:
        return SyncStatusResponse(has_synced=False, last_result=None)

    return SyncStatusResponse(
        has_synced=True,
        last_result=SyncResultResponse(
            companies_created=last.companies_created,
            companies_updated=last.companies_updated,
            contacts_created=last.contacts_created,
            contacts_updated=last.contacts_updated,
            investors_created=last.investors_created,
            investors_updated=last.investors_updated,
            audits_created=last.audits_created,
            funding_activities_created=last.funding_activities_created,
            qualification_tasks_created=last.qualification_tasks_created,
            errors=last.errors,
        ),
    )


# ---------- POST /startup-radar/audit/{company_id} ----------


@router.post(
    "/startup-radar/audit/{company_id}",
    response_model=CompanyAuditResponse,
    status_code=200,
)
async def trigger_company_audit(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lancer un audit avance Startup Radar pour une entreprise.

    Recupere l'audit detaille + l'analyse messaging depuis SR,
    les stocke en Activity(type=audit), et retourne le resultat.
    Idempotent : ne recree pas un audit qui existe deja.
    """
    # 1. Valider company_id
    try:
        cid = uuid.UUID(company_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="company_id invalide")

    # 2. Charger la company
    stmt = select(Company).where(Company.id == cid)
    company = (await db.execute(stmt)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise non trouvee")

    # 3. Verifier startup_radar_id
    if not company.startup_radar_id:
        raise HTTPException(
            status_code=422,
            detail="Cette entreprise n'a pas de lien Startup Radar",
        )
    if company.startup_radar_id.startswith("inv:"):
        raise HTTPException(
            status_code=422,
            detail="Les audits ne sont pas disponibles pour les investisseurs",
        )

    # 4. RBAC
    check_entity_access(company, current_user)

    sr_id = company.startup_radar_id
    sr_client = StartupRadarClient()

    # 5. Auth SR
    try:
        await sr_client.authenticate()
    except StartupRadarError as e:
        logger.error("[Integrations] Erreur auth SR pour audit: %s", e)
        raise HTTPException(status_code=503, detail=f"Erreur auth Startup Radar: {e}") from e

    audits_created = 0
    audits_skipped = 0
    errors: list[str] = []

    # 6. Audit detaille
    try:
        audit = await sr_client.get_detailed_audit(sr_id)
        if audit and audit.get("status") == "completed" and audit.get("result"):
            subject = f"Audit detaille: {company.name}"
            async with db.begin_nested():
                existing = (
                    await db.execute(
                        select(Activity).where(
                            Activity.company_id == company.id,
                            Activity.type == "audit",
                            Activity.subject == subject,
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    audits_skipped += 1
                else:
                    audit_result = audit["result"]
                    exec_summary = audit_result.get("executive_summary", {})
                    metadata = {
                        "audit_type": "detailed",
                        "source": "startup_radar",
                        "total_score": exec_summary.get("total_score"),
                        "score_interpretation": exec_summary.get("score_interpretation"),
                        "key_findings": exec_summary.get("key_findings"),
                        "top_priority": exec_summary.get("top_priority"),
                        "scoring": audit_result.get("scoring", {}),
                        "gaps_count": exec_summary.get("gaps_count"),
                        "recommendations_count": exec_summary.get("recommendations_count"),
                    }
                    activity = Activity(
                        id=uuid.uuid4(),
                        type="audit",
                        subject=subject,
                        content=exec_summary.get("score_interpretation"),
                        metadata_=metadata,
                        company_id=company.id,
                        user_id=current_user.id,
                    )
                    db.add(activity)
                    audits_created += 1
        elif audit and audit.get("status") != "completed":
            errors.append(f"Audit detaille en cours (status: {audit.get('status', 'unknown')})")
    except StartupRadarError as e:
        errors.append(f"Audit detaille: {e}")
    except Exception as e:
        errors.append(f"Audit detaille DB: {e}")

    # 7. Analyse messaging
    try:
        analysis = await sr_client.get_analysis(sr_id)
        if analysis and analysis.get("positioning"):
            subject = f"Audit messaging: {company.name}"
            async with db.begin_nested():
                existing = (
                    await db.execute(
                        select(Activity).where(
                            Activity.company_id == company.id,
                            Activity.type == "audit",
                            Activity.subject == subject,
                        )
                    )
                ).scalar_one_or_none()

                if existing:
                    audits_skipped += 1
                else:
                    metadata = {
                        "audit_type": "messaging",
                        "source": "startup_radar",
                        "positioning": analysis.get("positioning"),
                        "value_proposition": analysis.get("value_proposition"),
                        "messaging_score": analysis.get("messaging_score"),
                        "differentiators": analysis.get("differentiators"),
                        "target_audience": analysis.get("target_audience"),
                        "strengths": analysis.get("strengths"),
                        "weaknesses": analysis.get("weaknesses"),
                        "recommendations": analysis.get("recommendations"),
                    }
                    activity = Activity(
                        id=uuid.uuid4(),
                        type="audit",
                        subject=subject,
                        content=analysis.get("value_proposition"),
                        metadata_=metadata,
                        company_id=company.id,
                        user_id=current_user.id,
                    )
                    db.add(activity)
                    audits_created += 1
    except StartupRadarError as e:
        errors.append(f"Analyse messaging: {e}")
    except Exception as e:
        errors.append(f"Analyse messaging DB: {e}")

    # 8. Commit
    if audits_created > 0:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            errors.append(f"Commit: {e}")
            audits_created = 0

    logger.info(
        "[Integrations] Audit %s: %d crees, %d existants, %d erreurs",
        company.name, audits_created, audits_skipped, len(errors),
    )

    return CompanyAuditResponse(
        audits_created=audits_created,
        audits_skipped=audits_skipped,
        errors=errors,
    )
