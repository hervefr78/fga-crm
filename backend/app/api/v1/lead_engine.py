# =============================================================================
# FGA CRM - API Lead Engine (Signal Inbox)
# =============================================================================
"""Endpoints du module Lead Engine (docs/LEAD_ENGINE_VISION.md §3.2) :

- GET   /lead-engine/signals            : inbox paginee + KPI (manager+)
- PATCH /lead-engine/signals/{id}       : transition new -> actioned|ignored, ignored -> new
- POST  /lead-engine/scan               : scan manuel de l'org (demo/test sans attendre le beat)

RBAC : manager+ (comme GEO/Trends/Enrichissement). L'action metier (audit SR,
recherche de decideurs) reste sur les endpoints existants — orchestres cote
client ; le PATCH ne fait que tracer la transition (payload_json.action).
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_manager
from app.db.session import get_db
from app.models.lead_engine import (
    SIGNAL_STATUSES,
    SIGNAL_TRANSITIONS,
    SIGNAL_TYPES,
    LeadSignal,
)
from app.models.user import User
from app.schemas.lead_engine import (
    LeadScanResponse,
    LeadSignalListResponse,
    LeadSignalResponse,
    LeadSignalStats,
    LeadSignalUpdateRequest,
)
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
