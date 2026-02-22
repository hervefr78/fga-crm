# =============================================================================
# FGA CRM - Contacts Routes
# =============================================================================

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.contact import Contact
from app.models.user import User
from app.schemas.contact import (
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactUpdate,
)

router = APIRouter()


def _contact_to_response(c: Contact) -> ContactResponse:
    """Convertir un modele Contact en schema de reponse."""
    return ContactResponse(
        id=str(c.id),
        first_name=c.first_name,
        last_name=c.last_name,
        full_name=c.full_name,
        email=c.email,
        email_status=c.email_status,
        phone=c.phone,
        title=c.title,
        job_level=c.job_level,
        department=c.department,
        is_decision_maker=c.is_decision_maker,
        linkedin_url=c.linkedin_url,
        status=c.status,
        lead_score=c.lead_score or 0,
        source=c.source,
        company_id=str(c.company_id) if c.company_id else None,
        owner_id=str(c.owner_id) if c.owner_id else None,
        created_at=c.created_at.isoformat(),
    )


@router.get("", response_model=ContactListResponse)
async def list_contacts(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None, max_length=255),
    status: Optional[str] = None,
    job_level: Optional[str] = None,
    company_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = select(Contact)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (Contact.first_name.ilike(search_filter))
            | (Contact.last_name.ilike(search_filter))
            | (Contact.email.ilike(search_filter))
        )
    if status:
        query = query.where(Contact.status == status)
    if job_level:
        query = query.where(Contact.job_level == job_level)
    if company_id:
        try:
            query = query.where(Contact.company_id == uuid.UUID(company_id))
        except ValueError:
            raise HTTPException(status_code=422, detail="company_id invalide")

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Contact.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    contacts = result.scalars().all()

    return ContactListResponse(
        items=[_contact_to_response(c) for c in contacts],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


@router.post("", response_model=ContactResponse, status_code=201)
async def create_contact(
    data: ContactCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contact_data = data.model_dump()

    # Convertir company_id string → UUID
    if contact_data.get("company_id"):
        try:
            contact_data["company_id"] = uuid.UUID(contact_data["company_id"])
        except ValueError:
            raise HTTPException(status_code=422, detail="company_id invalide")

    contact = Contact(**contact_data, owner_id=user.id)
    db.add(contact)
    await db.flush()
    await db.refresh(contact)

    return _contact_to_response(contact)


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouve")

    return _contact_to_response(contact)


@router.put("/{contact_id}", response_model=ContactResponse)
async def update_contact(
    contact_id: uuid.UUID,
    data: ContactUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouve")

    update_data = data.model_dump(exclude_unset=True)

    # Convertir company_id string → UUID
    if "company_id" in update_data and update_data["company_id"]:
        try:
            update_data["company_id"] = uuid.UUID(update_data["company_id"])
        except ValueError:
            raise HTTPException(status_code=422, detail="company_id invalide")

    for field, value in update_data.items():
        setattr(contact, field, value)

    await db.flush()
    await db.refresh(contact)
    return _contact_to_response(contact)


@router.delete("/{contact_id}", status_code=204)
async def delete_contact(
    contact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(select(Contact).where(Contact.id == contact_id))
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouve")

    await db.delete(contact)
