# =============================================================================
# FGA CRM - Lead Engine : routes outreach (draft, queue priorisee, funnel)
# =============================================================================
"""Regle metier : SEUL un signal mmf_gap peut etre drafte (l'outreach ne se
declenche jamais sur une levee). Le draft n'est JAMAIS envoye automatiquement
(garde-fou §2.4) : il est stocke sur le signal et passe par le composer."""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.lead_engine._common import get_signal_or_404, parse_uuid
from app.config import settings
from app.core.deps import get_current_manager
from app.db.session import get_db
from app.models.contact import Contact
from app.models.lead_engine import SIGNAL_TYPES, LeadSignal
from app.models.user import User
from app.schemas.lead_engine import (
    LeadDraftRequest,
    LeadDraftResponse,
    LeadFunnelResponse,
    LeadQueueItem,
    LeadQueueResponse,
    LeadSignalResponse,
    PlayFunnel,
)
from app.services.ai_workflows.client import AiWorkflowError
from app.services.ai_workflows.outreach import generate_outreach_draft

logger = logging.getLogger(__name__)

router = APIRouter()

# Volume borne par periode + org ; garde-fou dur contre un backfill anormal (DC1)
_FUNNEL_SCAN_CAP = 5000


async def _resolve_draft_contact(
    db: AsyncSession, signal: LeadSignal, user: User, contact_id: str | None
) -> Contact:
    """Contact cible du draft : celui demande, sinon le meilleur email de la societe."""
    if contact_id:
        contact = await db.get(Contact, parse_uuid(contact_id))
        if contact is None or contact.organization_id != user.organization_id:
            raise HTTPException(status_code=404, detail="Contact introuvable")
        if signal.company_id and contact.company_id != signal.company_id:
            raise HTTPException(
                status_code=422, detail="Ce contact n'appartient pas a la societe du signal",
            )
        if not contact.email:
            raise HTTPException(status_code=422, detail="Ce contact n'a pas d'email")
        return contact

    if signal.company_id is None:
        raise HTTPException(status_code=422, detail="Signal sans societe : contact_id requis")
    contact = (
        await db.execute(
            select(Contact)
            .where(
                Contact.organization_id == user.organization_id,
                Contact.company_id == signal.company_id,
                Contact.email.is_not(None),
            )
            # Emails verifies d'abord, puis les plus recents
            .order_by(
                case((Contact.email_status == "valid", 0), else_=1),
                Contact.created_at.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(
            status_code=422,
            detail="Aucun contact avec email pour cette societe — "
                   "lancez d'abord la recherche de decideurs.",
        )
    return contact


@router.post("/signals/{signal_id}/draft", response_model=LeadDraftResponse)
async def draft_outreach(
    signal_id: str,
    payload: LeadDraftRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_manager),
) -> LeadDraftResponse:
    """Generer le draft d'outreach d'un signal mmf_gap (jamais envoye auto)."""
    if not settings.ai_workflows_enabled or not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="Workflows IA desactives")

    signal = await get_signal_or_404(db, signal_id, user)
    # Regle metier : SEUL le MMF gap declenche un outreach (jamais une levee).
    if signal.signal_type != "mmf_gap":
        raise HTTPException(
            status_code=422,
            detail="L'outreach ne se declenche que sur un signal MMF gap "
                   "(une levee declenche un audit, pas un contact).",
        )

    contact = await _resolve_draft_contact(db, signal, user, payload.contact_id)

    try:
        output, meta = await generate_outreach_draft(db, signal, contact, user)
    except AiWorkflowError as exc:
        raise HTTPException(status_code=502, detail=f"Draft indisponible : {exc}") from exc

    generated_at = datetime.now(UTC).isoformat()
    # Reassignation complete (JSONB non trackee en mutation in-place)
    signal.payload_json = {
        **(signal.payload_json or {}),
        "draft": {
            "contact_id": str(contact.id),
            "contact_name": contact.full_name,
            "contact_email": contact.email,
            "subject": output.subject,
            "body": output.body,
            "angle_rationale": output.angle_rationale,
            "generated_at": generated_at,
            **meta,
        },
    }
    await db.commit()

    return LeadDraftResponse(
        signal_id=str(signal.id),
        contact_id=str(contact.id),
        contact_name=contact.full_name,
        contact_email=contact.email or "",
        subject=output.subject,
        body=output.body,
        angle_rationale=output.angle_rationale,
        generated_at=generated_at,
        meta=meta,
    )


@router.get("/queue", response_model=LeadQueueResponse)
async def get_queue(
    limit: int = Query(25, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_manager),
) -> LeadQueueResponse:
    """Leads a traiter : signaux mmf_gap `new`, gap le plus profond d'abord,
    fonds les plus frais ensuite (le croisement qu'on vend — §3.1)."""
    base = select(LeadSignal).where(
        LeadSignal.organization_id == user.organization_id,
        LeadSignal.signal_type == "mmf_gap",
        LeadSignal.status == "new",
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    score_expr = cast(LeadSignal.payload_json["audit_score"].as_string(), Integer)
    funding_expr = LeadSignal.payload_json["funding_date"].as_string()
    signals = (
        await db.execute(
            base.order_by(
                score_expr.asc().nulls_last(),
                funding_expr.desc().nulls_last(),
                LeadSignal.created_at.desc(),
            ).limit(limit)
        )
    ).scalars().all()

    # Decideurs joignables par societe (une seule requete groupee — DC6)
    company_ids = [s.company_id for s in signals if s.company_id]
    email_counts: dict[uuid.UUID, int] = {}
    if company_ids:
        rows = await db.execute(
            select(Contact.company_id, func.count())
            .where(
                Contact.organization_id == user.organization_id,
                Contact.company_id.in_(company_ids),
                Contact.email.is_not(None),
            )
            .group_by(Contact.company_id)
        )
        email_counts = {row[0]: row[1] for row in rows.all()}

    return LeadQueueResponse(
        items=[
            LeadQueueItem(
                signal=LeadSignalResponse.model_validate(s),
                contacts_with_email=email_counts.get(s.company_id, 0) if s.company_id else 0,
                has_draft="draft" in (s.payload_json or {}),
            )
            for s in signals
        ],
        total=total,
    )


@router.get("/funnel", response_model=LeadFunnelResponse)
async def get_funnel(
    period_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_manager),
) -> LeadFunnelResponse:
    """Compteurs du funnel par play sur la periode (detected/actioned/drafted/sent)."""
    since = datetime.now(UTC) - timedelta(days=period_days)
    rows = (
        await db.execute(
            select(LeadSignal.signal_type, LeadSignal.status, LeadSignal.payload_json)
            .where(
                LeadSignal.organization_id == user.organization_id,
                LeadSignal.created_at >= since,
            )
            .limit(_FUNNEL_SCAN_CAP)
        )
    ).all()

    funnels = {t: {"detected": 0, "actioned": 0, "drafted": 0, "sent": 0} for t in SIGNAL_TYPES}
    for signal_type, status, payload in rows:
        f = funnels.get(signal_type)
        if f is None:
            continue
        payload = payload or {}
        f["detected"] += 1
        if status == "actioned":
            f["actioned"] += 1
        if "draft" in payload:
            f["drafted"] += 1
        if (payload.get("action") or {}).get("kind") == "outreach":
            f["sent"] += 1

    return LeadFunnelResponse(
        p1_mmf_gap=PlayFunnel(**funnels["mmf_gap"]),
        p2_funding=PlayFunnel(**funnels["funding_detected"]),
        p3_inbound=PlayFunnel(**funnels["inbound_new"]),
        period_days=period_days,
    )
