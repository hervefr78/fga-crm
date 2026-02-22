# =============================================================================
# FGA CRM - Email Templates Routes (CRUD)
# =============================================================================

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import apply_ownership_filter, check_entity_access
from app.db.session import get_db
from app.models.email_template import EmailTemplate
from app.models.user import User
from app.schemas.email import (
    EmailTemplateCreate,
    EmailTemplateListResponse,
    EmailTemplateResponse,
    EmailTemplateUpdate,
)
from app.services.email import extract_variables

router = APIRouter()


def _template_to_response(t: EmailTemplate) -> EmailTemplateResponse:
    """Convertir un modele EmailTemplate en schema de reponse (DC8 — centralise)."""
    return EmailTemplateResponse(
        id=str(t.id),
        name=t.name,
        subject=t.subject,
        body=t.body,
        variables=t.variables or [],
        owner_id=str(t.owner_id),
        created_at=t.created_at.isoformat(),
    )


@router.get("", response_model=EmailTemplateListResponse)
async def list_email_templates(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lister les templates email (pagine, searchable)."""
    query = select(EmailTemplate)
    query = apply_ownership_filter(query, EmailTemplate, user)

    if search:
        query = query.where(EmailTemplate.name.ilike(f"%{search}%"))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(EmailTemplate.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    templates = result.scalars().all()

    return EmailTemplateListResponse(
        items=[_template_to_response(t) for t in templates],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if total > 0 else 0,
    )


@router.post("", response_model=EmailTemplateResponse, status_code=201)
async def create_email_template(
    data: EmailTemplateCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Creer un template email. Les variables sont auto-extraites."""
    # Auto-extraire les variables depuis subject + body
    all_text = f"{data.subject} {data.body}"
    variables = extract_variables(all_text)

    template = EmailTemplate(
        name=data.name,
        subject=data.subject,
        body=data.body,
        variables=variables,
        owner_id=user.id,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)

    return _template_to_response(template)


@router.get("/{template_id}", response_model=EmailTemplateResponse)
async def get_email_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Detail d'un template email."""
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template non trouve")
    check_entity_access(template, user)

    return _template_to_response(template)


@router.put("/{template_id}", response_model=EmailTemplateResponse)
async def update_email_template(
    template_id: uuid.UUID,
    data: EmailTemplateUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Modifier un template email."""
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template non trouve")
    check_entity_access(template, user)

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    # Re-extraire les variables si subject ou body a change
    if "subject" in update_data or "body" in update_data:
        all_text = f"{template.subject} {template.body}"
        template.variables = extract_variables(all_text)

    await db.flush()
    await db.refresh(template)
    return _template_to_response(template)


@router.delete("/{template_id}", status_code=204)
async def delete_email_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Supprimer un template email."""
    result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_id))
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Template non trouve")
    check_entity_access(template, user)

    await db.delete(template)
