# =============================================================================
# FGA CRM - Deals Routes
# =============================================================================

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.deal import Deal
from app.models.user import User

router = APIRouter()


class DealCreate(BaseModel):
    title: str
    stage: str = "new"
    amount: Optional[float] = None
    currency: str = "EUR"
    probability: int = 0
    priority: str = "medium"
    expected_close_date: Optional[str] = None
    company_id: Optional[str] = None
    contact_id: Optional[str] = None
    description: Optional[str] = None


class DealResponse(BaseModel):
    id: str
    title: str
    stage: str
    amount: Optional[float]
    currency: str
    probability: int
    priority: str
    expected_close_date: Optional[str]
    company_id: Optional[str]
    contact_id: Optional[str]
    owner_id: Optional[str]
    description: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class DealListResponse(BaseModel):
    items: list[DealResponse]
    total: int
    page: int
    size: int
    pages: int


@router.get("", response_model=DealListResponse)
async def list_deals(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    stage: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Deal)
    if stage:
        query = query.where(Deal.stage == stage)
    if search:
        query = query.where(Deal.title.ilike(f"%{search}%"))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Deal.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    deals = result.scalars().all()

    return DealListResponse(
        items=[
            DealResponse(
                id=str(d.id), title=d.title, stage=d.stage, amount=d.amount,
                currency=d.currency, probability=d.probability, priority=d.priority,
                expected_close_date=d.expected_close_date.isoformat() if d.expected_close_date else None,
                company_id=str(d.company_id) if d.company_id else None,
                contact_id=str(d.contact_id) if d.contact_id else None,
                owner_id=str(d.owner_id) if d.owner_id else None,
                description=d.description, created_at=d.created_at.isoformat(),
            )
            for d in deals
        ],
        total=total, page=page, size=size, pages=(total + size - 1) // size,
    )


@router.post("", response_model=DealResponse, status_code=201)
async def create_deal(
    data: DealCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    deal_data = data.model_dump()
    for key in ("company_id", "contact_id"):
        if deal_data.get(key):
            deal_data[key] = uuid.UUID(deal_data[key])

    deal = Deal(**deal_data, owner_id=user.id)
    db.add(deal)
    await db.flush()
    await db.refresh(deal)

    return DealResponse(
        id=str(deal.id), title=deal.title, stage=deal.stage, amount=deal.amount,
        currency=deal.currency, probability=deal.probability, priority=deal.priority,
        expected_close_date=deal.expected_close_date.isoformat() if deal.expected_close_date else None,
        company_id=str(deal.company_id) if deal.company_id else None,
        contact_id=str(deal.contact_id) if deal.contact_id else None,
        owner_id=str(deal.owner_id) if deal.owner_id else None,
        description=deal.description, created_at=deal.created_at.isoformat(),
    )


@router.patch("/{deal_id}/stage")
async def update_deal_stage(
    deal_id: uuid.UUID,
    stage: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    deal.stage = stage
    return {"status": "updated", "stage": stage}
