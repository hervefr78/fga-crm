# =============================================================================
# FGA CRM - Email Routes (envoi + liste des emails envoyes)
# =============================================================================

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.deps import get_current_user
from app.core.rbac import apply_ownership_filter, check_entity_access
from app.db.session import get_db
from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.email_template import EmailTemplate
from app.models.user import User
from app.schemas.email import EmailSendRequest, EmailSendResponse
from app.services.email import (
    EmailSendError,
    build_variables_dict,
    send_email,
    substitute_variables,
)

router = APIRouter()


def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    """Convertir un string en UUID avec gestion d'erreur propre."""
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"{field_name} invalide")


# ---------- Envoi d'email ----------


@router.post("/send", response_model=EmailSendResponse, status_code=201)
async def send_email_endpoint(
    data: EmailSendRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Envoyer un email a un contact ou une adresse email."""
    # Charger le contact si specifie (avec sa company pour les variables)
    contact: Contact | None = None
    company: Company | None = None

    if data.contact_id:
        contact_uuid = _parse_uuid(data.contact_id, "contact_id")
        result = await db.execute(
            select(Contact)
            .options(selectinload(Contact.company))
            .where(Contact.id == contact_uuid)
        )
        contact = result.scalar_one_or_none()
        if not contact:
            raise HTTPException(status_code=404, detail="Contact non trouve")
        check_entity_access(contact, user)

        if contact.company:
            company = contact.company

    # Charger la company separement si specifie sans contact
    if data.company_id and not company:
        company_uuid = _parse_uuid(data.company_id, "company_id")
        result = await db.execute(select(Company).where(Company.id == company_uuid))
        company = result.scalar_one_or_none()
        if not company:
            raise HTTPException(status_code=404, detail="Entreprise non trouvee")
        check_entity_access(company, user)

    # Construire les variables de substitution
    variables_dict = build_variables_dict(contact, company, user)

    # Appliquer le template si specifie
    subject = data.subject
    body = data.body
    template_name: str | None = None

    if data.template_id:
        template_uuid = _parse_uuid(data.template_id, "template_id")
        result = await db.execute(select(EmailTemplate).where(EmailTemplate.id == template_uuid))
        template = result.scalar_one_or_none()
        if template:
            template_name = template.name

    # Substituer les variables dans subject et body
    subject = substitute_variables(subject, variables_dict)
    body = substitute_variables(body, variables_dict)

    # Envoyer l'email via SMTP
    from_email = settings.ovh_email_user
    try:
        message_id = await send_email(
            to_email=data.to_email,
            subject=subject,
            body=body,
            from_email=from_email,
            from_name=user.full_name,
        )
    except EmailSendError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Erreur d'envoi email. {e}",
        )

    # Creer l'Activity (log de l'email envoye)
    now = datetime.now(UTC)
    metadata = {
        "to_email": data.to_email,
        "from_email": from_email or "",
        "template_id": data.template_id,
        "template_name": template_name,
        "smtp_message_id": message_id,
    }

    activity = Activity(
        type="email",
        subject=subject,
        content=body,
        metadata_=metadata,
        contact_id=_parse_uuid(data.contact_id, "contact_id") if data.contact_id else None,
        company_id=_parse_uuid(data.company_id, "company_id") if data.company_id else None,
        deal_id=_parse_uuid(data.deal_id, "deal_id") if data.deal_id else None,
        user_id=user.id,
    )
    db.add(activity)
    await db.flush()
    await db.refresh(activity)

    return EmailSendResponse(
        success=True,
        activity_id=str(activity.id),
        message_id=message_id,
        sent_at=now.isoformat(),
    )


# ---------- Liste des emails envoyes ----------


@router.get("")
async def list_sent_emails(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    contact_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Lister les emails envoyes (Activity type='email')."""
    query = select(Activity).where(Activity.type == "email")
    query = apply_ownership_filter(query, Activity, user, owner_field="user_id")

    if search:
        query = query.where(Activity.subject.ilike(f"%{search}%"))
    if contact_id:
        query = query.where(Activity.contact_id == _parse_uuid(contact_id, "contact_id"))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(Activity.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    activities = result.scalars().all()

    return {
        "items": [
            {
                "id": str(a.id),
                "subject": a.subject,
                "content": a.content,
                "to_email": (a.metadata_ or {}).get("to_email", ""),
                "from_email": (a.metadata_ or {}).get("from_email", ""),
                "template_name": (a.metadata_ or {}).get("template_name"),
                "contact_id": str(a.contact_id) if a.contact_id else None,
                "company_id": str(a.company_id) if a.company_id else None,
                "deal_id": str(a.deal_id) if a.deal_id else None,
                "user_id": str(a.user_id),
                "created_at": a.created_at.isoformat(),
            }
            for a in activities
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size if total > 0 else 0,
    }
