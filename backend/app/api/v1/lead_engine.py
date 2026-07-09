# =============================================================================
# FGA CRM - API Lead Engine (Signal Inbox)
# =============================================================================
"""Endpoints du module Lead Engine (docs/LEAD_ENGINE_VISION.md §3) :

- GET   /lead-engine/signals            : inbox paginee + KPI (manager+)
- PATCH /lead-engine/signals/{id}       : transitions DC5 (payload_json.action trace)
- POST  /lead-engine/signals/{id}/draft : draft outreach-v1 (mmf_gap uniquement)
- GET   /lead-engine/queue              : leads priorises (gap x fraicheur des fonds)
- GET   /lead-engine/funnel             : compteurs par play (P1/P2/P3)
- POST  /lead-engine/scan               : scan manuel de l'org (sans attendre le beat)

RBAC : manager+ (comme GEO/Trends/Enrichissement). Les actions audit/enrich/
qualify restent sur les endpoints existants — orchestrees cote client. Le draft
outreach n'est JAMAIS envoye automatiquement (validation humaine, composer).
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Integer, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_manager
from app.db.session import get_db
from app.models.contact import Contact
from app.models.lead_engine import (
    SIGNAL_STATUSES,
    SIGNAL_TRANSITIONS,
    SIGNAL_TYPES,
    LeadSignal,
)
from app.models.user import User
from app.schemas.lead_engine import (
    LeadDraftRequest,
    LeadDraftResponse,
    LeadFunnelResponse,
    LeadQueueItem,
    LeadQueueResponse,
    LeadScanResponse,
    LeadSignalListResponse,
    LeadSignalResponse,
    LeadSignalStats,
    LeadSignalUpdateRequest,
    PlayFunnel,
)
from app.services.ai_workflows.client import AiWorkflowError
from app.services.ai_workflows.outreach import generate_outreach_draft
from app.services.lead_engine.detector import scan_org

logger = logging.getLogger(__name__)

router = APIRouter()

# Sets de validation des filtres (DC1 : filtre invalide -> ignore)
_STATUS_SET = set(SIGNAL_STATUSES)
_TYPE_SET = set(SIGNAL_TYPES)


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="Identifiant invalide") from None


async def _compute_stats(db: AsyncSession, org_id: uuid.UUID) -> LeadSignalStats:
    """KPI de l'inbox : backlog `new` par type + actions des 7 derniers jours."""
    since_7d = datetime.now(UTC) - timedelta(days=7)

    new_rows = (
        await db.execute(
            select(LeadSignal.signal_type, func.count())
            .where(LeadSignal.organization_id == org_id, LeadSignal.status == "new")
            .group_by(LeadSignal.signal_type)
        )
    ).all()
    new_by_type = {row[0]: row[1] for row in new_rows}

    async def _count_since(status: str) -> int:
        return (
            await db.execute(
                select(func.count()).where(
                    LeadSignal.organization_id == org_id,
                    LeadSignal.status == status,
                    LeadSignal.updated_at >= since_7d,
                )
            )
        ).scalar() or 0

    return LeadSignalStats(
        new_total=sum(new_by_type.values()),
        new_funding=new_by_type.get("funding_detected", 0),
        new_mmf=new_by_type.get("mmf_gap", 0),
        actioned_7d=await _count_since("actioned"),
        ignored_7d=await _count_since("ignored"),
    )


@router.get("/signals", response_model=LeadSignalListResponse)
async def list_signals(
    status: str | None = Query(None),
    signal_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_manager),
) -> LeadSignalListResponse:
    """Signal Inbox : flux chronologique des signaux de l'org (filtrable)."""
    base = select(LeadSignal).where(LeadSignal.organization_id == user.organization_id)
    if status in _STATUS_SET:
        base = base.where(LeadSignal.status == status)
    if signal_type in _TYPE_SET:
        base = base.where(LeadSignal.signal_type == signal_type)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(LeadSignal.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    return LeadSignalListResponse(
        items=[LeadSignalResponse.model_validate(s) for s in rows],
        total=total,
        page=page,
        size=size,
        stats=await _compute_stats(db, user.organization_id),
    )


@router.patch("/signals/{signal_id}", response_model=LeadSignalResponse)
async def update_signal(
    signal_id: str,
    payload: LeadSignalUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_manager),
) -> LeadSignalResponse:
    """Transition de statut d'un signal (DC5 : transitions explicites)."""
    signal = await db.get(LeadSignal, _parse_uuid(signal_id))
    # 404 (pas 403) si cross-org : ne pas divulguer l'existence du signal.
    if signal is None or signal.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Signal introuvable")

    if payload.status not in SIGNAL_TRANSITIONS.get(signal.status, []):
        raise HTTPException(
            status_code=422,
            detail=f"Transition invalide : {signal.status} -> {payload.status}",
        )

    signal.status = payload.status
    if payload.status == "actioned" and payload.action_kind:
        # Reassignation complete (pas de mutation in-place : JSONB non trackee)
        signal.payload_json = {
            **(signal.payload_json or {}),
            "action": {
                "kind": payload.action_kind,
                "at": datetime.now(UTC).isoformat(),
                "by": str(user.id),
            },
        }
    await db.commit()
    await db.refresh(signal)
    return LeadSignalResponse.model_validate(signal)


@router.post("/scan", response_model=LeadScanResponse)
async def run_scan(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_manager),
) -> LeadScanResponse:
    """Scan manuel de l'org courante (sans attendre le beat horaire)."""
    if not settings.lead_engine_enabled:
        raise HTTPException(status_code=503, detail="Lead Engine desactive")
    created = await scan_org(db, user.organization_id)
    logger.info("[LeadEngine] Scan manuel org %s par %s : %s",
                user.organization_id, user.id, created)
    return LeadScanResponse(created=created)


# ---------------------------------------------------------------------------
# Draft d'outreach (workflow outreach-v1)
# ---------------------------------------------------------------------------

async def _resolve_draft_contact(
    db: AsyncSession, signal: LeadSignal, user: User, contact_id: str | None
) -> Contact:
    """Contact cible du draft : celui demande, sinon le meilleur email de la societe."""
    if contact_id:
        contact = await db.get(Contact, _parse_uuid(contact_id))
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
    """Generer le draft d'outreach d'un signal mmf_gap (jamais envoye auto).

    Le draft est stocke sur le signal (payload_json.draft) et doit etre valide
    puis envoye par l'humain via le composer email (garde-fou §2.4).
    """
    if not settings.ai_workflows_enabled or not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="Workflows IA desactives")

    signal = await db.get(LeadSignal, _parse_uuid(signal_id))
    if signal is None or signal.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Signal introuvable")
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


# ---------------------------------------------------------------------------
# Queue priorisee (ecran 1) : profondeur du gap x fraicheur des fonds
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Funnel par play (mesure — §2.3)
# ---------------------------------------------------------------------------

# Volume borne par periode + org ; garde-fou dur contre un backfill anormal (DC1)
_FUNNEL_SCAN_CAP = 5000


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
