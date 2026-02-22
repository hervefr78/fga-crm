# =============================================================================
# FGA CRM - Deals Routes
# =============================================================================

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import apply_ownership_filter, check_entity_access
from app.db.session import get_db
from app.models.deal import Deal
from app.models.user import User
from app.schemas.deal import (
    DealCreate,
    DealListResponse,
    DealResponse,
    DealStageUpdate,
    DealUpdate,
)

router = APIRouter()


def _deal_to_response(d: Deal) -> DealResponse:
    """Convertir un modele Deal en schema de reponse (DC8 — centralise)."""
    return DealResponse(
        id=str(d.id),
        title=d.title,
        stage=d.stage,
        amount=d.amount,
        currency=d.currency,
        probability=d.probability or 0,
        priority=d.priority,
        expected_close_date=d.expected_close_date.isoformat() if d.expected_close_date else None,
        company_id=str(d.company_id) if d.company_id else None,
        contact_id=str(d.contact_id) if d.contact_id else None,
        owner_id=str(d.owner_id) if d.owner_id else None,
        description=d.description,
        created_at=d.created_at.isoformat(),
    )


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    """Convertir un string en UUID avec gestion d'erreur propre."""
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field_name} invalide")


@router.get("", response_model=DealListResponse)
async def list_deals(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    stage: str | None = None,
    search: str | None = Query(None, max_length=255),
    contact_id: str | None = None,
    company_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Deal)
    query = apply_ownership_filter(query, Deal, user)
    if stage:
        query = query.where(Deal.stage == stage)
    if search:
        query = query.where(Deal.title.ilike(f"%{search}%"))
    if contact_id:
        query = query.where(Deal.contact_id == _parse_uuid(contact_id, "contact_id"))
    if company_id:
        query = query.where(Deal.company_id == _parse_uuid(company_id, "company_id"))

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

    deal = Deal(**deal_data, owner_id=user.id)
    db.add(deal)
    await db.flush()
    await db.refresh(deal)

    return _deal_to_response(deal)


@router.get("/{deal_id}", response_model=DealResponse)
async def get_deal(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
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
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal non trouve")
    check_entity_access(deal, user)

    update_data = data.model_dump(exclude_unset=True)

    # Convertir les FK string → UUID
    for key in ("company_id", "contact_id"):
        if key in update_data and update_data[key]:
            update_data[key] = _parse_uuid(update_data[key], key)

    # Detecter changement de stage pour le timestamp
    if "stage" in update_data and update_data["stage"] != deal.stage:
        update_data["stage_changed_at"] = datetime.now(UTC)

    for field, value in update_data.items():
        setattr(deal, field, value)

    await db.flush()
    await db.refresh(deal)
    return _deal_to_response(deal)


@router.patch("/{deal_id}/stage", response_model=DealResponse)
async def update_deal_stage(
    deal_id: uuid.UUID,
    data: DealStageUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal non trouve")
    check_entity_access(deal, user)

    deal.stage = data.stage
    deal.stage_changed_at = datetime.now(UTC)

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
