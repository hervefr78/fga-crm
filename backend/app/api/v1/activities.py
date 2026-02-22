# =============================================================================
# FGA CRM - Activities Routes
# =============================================================================

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import apply_ownership_filter, check_entity_access
from app.db.session import get_db
from app.models.activity import Activity
from app.models.user import User
from app.schemas.activity import (
    ActivityCreate,
    ActivityListResponse,
    ActivityResponse,
    ActivityUpdate,
)

router = APIRouter()


def _activity_to_response(a: Activity) -> ActivityResponse:
    """Convertir un modele Activity en schema de reponse (DC8 — centralise)."""
    return ActivityResponse(
        id=str(a.id),
        type=a.type,
        subject=a.subject,
        content=a.content,
        metadata_=a.metadata_,
        contact_id=str(a.contact_id) if a.contact_id else None,
        company_id=str(a.company_id) if a.company_id else None,
        deal_id=str(a.deal_id) if a.deal_id else None,
        user_id=str(a.user_id),
        created_at=a.created_at.isoformat(),
    )


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    """Convertir un string en UUID avec gestion d'erreur propre."""
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field_name} invalide")


@router.get("", response_model=ActivityListResponse)
async def list_activities(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    type: str | None = None,
    contact_id: str | None = None,
    company_id: str | None = None,
    deal_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Activity)
    query = apply_ownership_filter(query, Activity, user, owner_field="user_id")

    # Filtres
    if search:
        query = query.where(Activity.subject.ilike(f"%{search}%"))
    if type:
        query = query.where(Activity.type == type)
    if contact_id:
        query = query.where(Activity.contact_id == _parse_uuid(contact_id, "contact_id"))
    if company_id:
        query = query.where(Activity.company_id == _parse_uuid(company_id, "company_id"))
    if deal_id:
        query = query.where(Activity.deal_id == _parse_uuid(deal_id, "deal_id"))

    # Comptage
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Tri : les plus recentes d'abord
    query = query.order_by(Activity.created_at.desc()).offset((page - 1) * size).limit(size)

    result = await db.execute(query)
    activities = result.scalars().all()

    return ActivityListResponse(
        items=[_activity_to_response(a) for a in activities],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if total > 0 else 0,
    )


@router.post("", response_model=ActivityResponse, status_code=201)
async def create_activity(
    data: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    activity_data = data.model_dump()

    # Convertir les FK string → UUID
    for key in ("contact_id", "company_id", "deal_id"):
        if activity_data.get(key):
            activity_data[key] = _parse_uuid(activity_data[key], key)

    # user_id auto-set depuis l'utilisateur authentifie
    activity = Activity(**activity_data, user_id=user.id)
    db.add(activity)
    await db.flush()
    await db.refresh(activity)

    return _activity_to_response(activity)


@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity(
    activity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activite non trouvee")
    check_entity_access(activity, user, owner_field="user_id")

    return _activity_to_response(activity)


@router.put("/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    activity_id: uuid.UUID,
    data: ActivityUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activite non trouvee")
    check_entity_access(activity, user, owner_field="user_id")

    update_data = data.model_dump(exclude_unset=True)

    # Convertir les FK string → UUID
    for key in ("contact_id", "company_id", "deal_id"):
        if key in update_data and update_data[key]:
            update_data[key] = _parse_uuid(update_data[key], key)

    for field, value in update_data.items():
        setattr(activity, field, value)

    await db.flush()
    await db.refresh(activity)
    return _activity_to_response(activity)


@router.delete("/{activity_id}", status_code=204)
async def delete_activity(
    activity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    activity = result.scalar_one_or_none()
    if not activity:
        raise HTTPException(status_code=404, detail="Activite non trouvee")
    check_entity_access(activity, user, owner_field="user_id")

    await db.delete(activity)
