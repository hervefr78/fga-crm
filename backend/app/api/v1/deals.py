# =============================================================================
# FGA CRM - Deals Routes
# =============================================================================

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.core.rbac import apply_ownership_filter, check_entity_access
from app.db.session import get_db
from app.models.deal import (
    DEAL_CATEGORIES,
    PERIOD_TO_MONTHS,
    PIPELINE_STAGES,
    PRICING_TYPES,
    Deal,
)
from app.models.user import User
from app.schemas.deal import (
    DealCreate,
    DealListResponse,
    DealResponse,
    DealsStatsResponse,
    DealStageUpdate,
    DealUpdate,
)

router = APIRouter()

# Stages consideres comme "fermes" (won/lost) — declenche l'auto-set actual_close_date
CLOSED_STAGES: set[str] = {"won", "lost"}

# Options selectinload partagees pour eviter N+1 sur les relations exposees
# dans DealResponse (owner.full_name, company.name) — DC6 + DC8.
# IMPORTANT : toute query qui sera passee a _deal_to_response doit appliquer
# ces options sinon le helper declenchera un lazy load synchrone (erreur en async).
DEAL_RESPONSE_LOADERS = (
    selectinload(Deal.owner),
    selectinload(Deal.company),
)


def _deal_to_response(d: Deal) -> DealResponse:
    """Convertir un modele Deal en schema de reponse (DC8 — centralise).

    Pre-condition : `d.owner` et `d.company` doivent avoir ete charges en amont
    (selectinload via DEAL_RESPONSE_LOADERS). Sinon SQLAlchemy declenche un lazy
    load synchrone qui leve MissingGreenlet en contexte async.
    """
    return DealResponse(
        id=str(d.id),
        title=d.title,
        stage=d.stage,
        amount=d.amount,
        currency=d.currency,
        probability=d.probability or 0,
        priority=d.priority,
        expected_close_date=d.expected_close_date.isoformat() if d.expected_close_date else None,
        actual_close_date=d.actual_close_date.isoformat() if d.actual_close_date else None,
        position=d.position,
        company_id=str(d.company_id) if d.company_id else None,
        contact_id=str(d.contact_id) if d.contact_id else None,
        owner_id=str(d.owner_id) if d.owner_id else None,
        description=d.description,
        created_at=d.created_at.isoformat(),
        loss_reason=d.loss_reason,
        owner_name=d.owner.full_name if d.owner else None,
        company_name=d.company.name if d.company else None,
        pricing_type=d.pricing_type,
        recurring_amount=d.recurring_amount,
        commitment_months=d.commitment_months,
    )


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    """Convertir un string en UUID avec gestion d'erreur propre."""
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field_name} invalide")


def _parse_iso_date(value: str, field_name: str) -> date:
    """Convertir un string ISO YYYY-MM-DD en date avec erreur propre (DC2)."""
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field_name} doit etre une date ISO YYYY-MM-DD")


def _apply_deal_filters(
    query: Select,
    *,
    stage: str | None,
    category: str | None,
    search: str | None,
    contact_id: str | None,
    company_id: str | None,
    close_date_from: str | None,
    close_date_to: str | None,
    pricing_type: str | None,
    owner_id: str | None,
) -> Select:
    """Appliquer les filtres communs list/stats (DC8 — centralise).

    Regle : si `stage` ET `category` sont fournis, `stage` prime (filtre plus precis).
    """
    if stage:
        query = query.where(Deal.stage == stage)
    elif category:
        # category deja validee par regex Pydantic — guard defensif (DC10)
        stages = DEAL_CATEGORIES.get(category)
        if stages:
            query = query.where(Deal.stage.in_(stages))

    if search:
        query = query.where(Deal.title.ilike(f"%{search}%"))
    if contact_id:
        query = query.where(Deal.contact_id == _parse_uuid(contact_id, "contact_id"))
    if company_id:
        query = query.where(Deal.company_id == _parse_uuid(company_id, "company_id"))
    if owner_id:
        query = query.where(Deal.owner_id == _parse_uuid(owner_id, "owner_id"))

    if close_date_from:
        query = query.where(
            Deal.actual_close_date >= _parse_iso_date(close_date_from, "close_date_from")
        )
    if close_date_to:
        query = query.where(
            Deal.actual_close_date <= _parse_iso_date(close_date_to, "close_date_to")
        )

    if pricing_type:
        # Validation contre les valeurs autorisees (DC1 — bornee a la liste connue)
        if pricing_type not in PRICING_TYPES:
            raise HTTPException(
                status_code=422,
                detail=f"pricing_type invalide. Valeurs autorisees : {', '.join(PRICING_TYPES)}",
            )
        query = query.where(Deal.pricing_type == pricing_type)

    return query


def _maybe_auto_set_close_date(deal: Deal, new_stage: str | None) -> None:
    """Auto-set/reset actual_close_date au passage en won/lost / retour pipeline.

    - won/lost : set a today() si pas deja defini (idempotent — on n'ecrase pas une
      valeur saisie manuellement)
    - retour vers pipeline (new/contacted/...) : reset a None
    - autres transitions : aucun effet
    """
    if new_stage is None:
        return

    if new_stage in CLOSED_STAGES and deal.actual_close_date is None:
        deal.actual_close_date = date.today()
        return

    if new_stage in PIPELINE_STAGES and deal.actual_close_date is not None:
        deal.actual_close_date = None


@router.get("", response_model=DealListResponse)
async def list_deals(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=200),
    stage: str | None = None,
    category: str | None = Query(None, pattern="^(pipeline|signed|lost)$"),
    search: str | None = Query(None, max_length=255),
    contact_id: str | None = Query(None, max_length=36),
    company_id: str | None = Query(None, max_length=36),
    close_date_from: str | None = Query(None, max_length=10),
    close_date_to: str | None = Query(None, max_length=10),
    pricing_type: str | None = Query(None, max_length=20),
    owner_id: str | None = Query(None, max_length=36),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # selectinload owner/company pour exposer owner_name/company_name sans N+1 (DC6)
    query = select(Deal).options(*DEAL_RESPONSE_LOADERS)
    query = apply_ownership_filter(query, Deal, user)
    query = _apply_deal_filters(
        query,
        stage=stage,
        category=category,
        search=search,
        contact_id=contact_id,
        company_id=company_id,
        close_date_from=close_date_from,
        close_date_to=close_date_to,
        pricing_type=pricing_type,
        owner_id=owner_id,
    )

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Deal.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    deals = result.scalars().all()

    return DealListResponse(
        items=[_deal_to_response(d) for d in deals],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


# IMPORTANT: declare /stats AVANT /{deal_id} pour que FastAPI ne tente pas
# de parser "stats" comme un UUID.
@router.get("/stats", response_model=DealsStatsResponse)
async def get_deals_stats(
    stage: str | None = None,
    category: str | None = Query(None, pattern="^(pipeline|signed|lost)$"),
    search: str | None = Query(None, max_length=255),
    contact_id: str | None = Query(None, max_length=36),
    company_id: str | None = Query(None, max_length=36),
    close_date_from: str | None = Query(None, max_length=10),
    close_date_to: str | None = Query(None, max_length=10),
    pricing_type: str | None = Query(None, max_length=20),
    owner_id: str | None = Query(None, max_length=36),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stats agregees sur le meme set de filtres que list_deals.

    Strategie : 1 query select-minimal (pricing_type, amount, recurring_amount)
    puis normalisation MRR en Python (DC6 + DC2 — pas de calcul complexe en SQL).
    """
    # Select minimal — DC6 : pas de relations, pas de blobs
    query = select(Deal.pricing_type, Deal.amount, Deal.recurring_amount)
    query = apply_ownership_filter(query, Deal, user)
    query = _apply_deal_filters(
        query,
        stage=stage,
        category=category,
        search=search,
        contact_id=contact_id,
        company_id=company_id,
        close_date_from=close_date_from,
        close_date_to=close_date_to,
        pricing_type=pricing_type,
        owner_id=owner_id,
    )

    rows = (await db.execute(query)).all()

    count = len(rows)
    total_amount = 0.0
    one_shot_amount = 0.0
    mrr = 0.0
    recurring_count = 0

    for ptype, amount, rec_amount in rows:
        amount_val = float(amount or 0.0)
        total_amount += amount_val

        if ptype == "one_shot":
            one_shot_amount += amount_val
            continue

        # Recurrent : compter et calculer le MRR si recurring_amount present
        recurring_count += 1
        months = PERIOD_TO_MONTHS.get(ptype)
        if months and rec_amount is not None:
            mrr += float(rec_amount) / months

    return DealsStatsResponse(
        count=count,
        total_amount=total_amount,
        one_shot_amount=one_shot_amount,
        mrr=mrr,
        arr=mrr * 12,
        recurring_count=recurring_count,
    )


@router.post("", response_model=DealResponse, status_code=201)
async def create_deal(
    data: DealCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    deal_data = data.model_dump()

    # Convertir les FK string → UUID
    for key in ("company_id", "contact_id"):
        if deal_data.get(key):
            deal_data[key] = _parse_uuid(deal_data[key], key)

    # Convertir expected_close_date string → date
    if deal_data.get("expected_close_date"):
        deal_data["expected_close_date"] = date.fromisoformat(deal_data["expected_close_date"])

    deal = Deal(**deal_data, owner_id=user.id)

    # Auto-set actual_close_date si creation directe en won/lost (cas rare mais possible)
    if deal.stage in CLOSED_STAGES and deal.actual_close_date is None:
        deal.actual_close_date = date.today()

    db.add(deal)
    await db.flush()

    # Recharger avec owner/company (selectinload) pour populer owner_name/company_name (DC6)
    result = await db.execute(
        select(Deal).options(*DEAL_RESPONSE_LOADERS).where(Deal.id == deal.id)
    )
    deal = result.scalar_one()

    return _deal_to_response(deal)


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Deal).options(*DEAL_RESPONSE_LOADERS).where(Deal.id == deal_id)
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal non trouve")
    check_entity_access(deal, user)

    return _deal_to_response(deal)


@router.put("/{deal_id}", response_model=DealResponse)
async def update_deal(
    deal_id: uuid.UUID,
    data: DealUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # selectinload owner/company pour pouvoir retourner _deal_to_response sans lazy load
    result = await db.execute(
        select(Deal).options(*DEAL_RESPONSE_LOADERS).where(Deal.id == deal_id)
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal non trouve")
    check_entity_access(deal, user)

    update_data = data.model_dump(exclude_unset=True)

    # Convertir les FK string → UUID
    for key in ("company_id", "contact_id"):
        if key in update_data and update_data[key]:
            update_data[key] = _parse_uuid(update_data[key], key)

    # Convertir expected_close_date string → date
    if update_data.get("expected_close_date"):
        update_data["expected_close_date"] = date.fromisoformat(update_data["expected_close_date"])

    # Detecter changement de stage pour le timestamp
    new_stage: str | None = None
    if "stage" in update_data and update_data["stage"] != deal.stage:
        update_data["stage_changed_at"] = datetime.now(UTC)
        new_stage = update_data["stage"]

    # Validation cross-field : si l'etat final est recurrent, recurring_amount
    # doit etre defini (DC2 — sinon le deal est silencieusement ignore au MRR).
    # On compose l'etat final en preferant la valeur du PATCH a celle de l'entite.
    final_pricing = update_data.get("pricing_type", deal.pricing_type)
    final_recurring = update_data.get("recurring_amount", deal.recurring_amount)
    if final_pricing != "one_shot" and final_recurring is None:
        raise HTTPException(
            status_code=422,
            detail="recurring_amount est obligatoire pour un pricing recurrent",
        )

    for field, value in update_data.items():
        setattr(deal, field, value)

    # Auto-set/reset actual_close_date selon la transition de stage (idempotent)
    _maybe_auto_set_close_date(deal, new_stage)

    await db.flush()
    # Re-query avec selectinload : si company_id a change, la relation chargee
    # initialement pointe vers l'ancienne company. Le re-fetch garantit
    # que owner_name/company_name refletent l'etat post-update (DC6).
    result = await db.execute(
        select(Deal).options(*DEAL_RESPONSE_LOADERS).where(Deal.id == deal.id)
    )
    deal = result.scalar_one()
    return _deal_to_response(deal)


@router.patch("/{deal_id}/stage", response_model=DealResponse)
async def update_deal_stage(
    deal_id: uuid.UUID,
    data: DealStageUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Deal).options(*DEAL_RESPONSE_LOADERS).where(Deal.id == deal_id)
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal non trouve")
    check_entity_access(deal, user)

    previous_stage = deal.stage
    deal.stage = data.stage
    deal.stage_changed_at = datetime.now(UTC)

    # Auto-set/reset actual_close_date uniquement si le stage a effectivement change
    # (evite un reset intempestif sur une re-soumission won → won)
    if data.stage != previous_stage:
        _maybe_auto_set_close_date(deal, data.stage)

    await db.flush()
    await db.refresh(deal)
    return _deal_to_response(deal)


@router.delete("/{deal_id}", status_code=204)
async def delete_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal non trouve")
    check_entity_access(deal, user)

    await db.delete(deal)
