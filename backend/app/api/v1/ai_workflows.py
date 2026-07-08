# =============================================================================
# FGA CRM - Routes Workflows IA (scoring)
# =============================================================================
"""Endpoints des workflows IA natifs (spec workflows-ia). Routes absolues
(pattern du router ai.py) : /deals/{id}/score.

RBAC : tous les roles authentifies, avec l'ownership habituel (un sales ne
score que SES deals — check_entity_access). Isolation multi-tenant systematique
(check_tenant_access). Kill switch global : settings.ai_workflows_enabled."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.rbac import check_entity_access, check_tenant_access
from app.db.session import get_db
from app.models.deal import Deal
from app.models.user import User
from app.schemas.ai_workflows import DealScoreResponse
from app.services.ai_workflows.client import AiWorkflowError
from app.services.ai_workflows.scoring import score_deal

router = APIRouter()


def _score_response(deal: Deal, *, cached: bool) -> DealScoreResponse:
    meta = deal.ai_score_meta or {}
    return DealScoreResponse(
        deal_id=str(deal.id),
        score=deal.ai_score or 0,
        tier=deal.ai_tier or "C",
        rationale=deal.ai_score_rationale or "",
        missing_signals=list(deal.ai_score_missing or []),
        recommended_product=meta.get("recommended_product"),
        scored_at=deal.ai_scored_at.isoformat() if deal.ai_scored_at else "",
        cached=cached,
        meta={
            "model": meta.get("model"),
            "prompt_version": meta.get("prompt_version"),
            "fit_points": meta.get("fit_points"),
            "intent_points": meta.get("intent_points"),
            "message_points": meta.get("message_points"),
        },
    )


@router.post("/deals/{deal_id}/score", response_model=DealScoreResponse)
async def score_deal_endpoint(
    deal_id: uuid.UUID,
    force_rescore: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DealScoreResponse:
    """Score un deal (fit + intent + opportunite message) et persiste le resultat.

    Un score de moins de settings.ai_score_ttl_days jours est retourne tel quel
    (cached=True) sans appel LLM, sauf force_rescore=True.
    """
    if not settings.ai_workflows_enabled:
        raise HTTPException(status_code=503, detail="Workflows IA desactives")

    deal = await db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="Deal non trouve")
    check_tenant_access(deal, user)
    check_entity_access(deal, user)

    # Cache : score recent -> pas de re-depense LLM.
    if not force_rescore and deal.ai_scored_at is not None:
        scored_at = deal.ai_scored_at
        if scored_at.tzinfo is None:  # SQLite tests : datetimes naives
            scored_at = scored_at.replace(tzinfo=UTC)
        ttl = timedelta(days=settings.ai_score_ttl_days)
        if datetime.now(UTC) - scored_at < ttl:
            return _score_response(deal, cached=True)

    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI non configure")

    try:
        await score_deal(db, deal)
    except AiWorkflowError as exc:
        raise HTTPException(status_code=502, detail=f"Scoring IA indisponible : {exc}")

    return _score_response(deal, cached=False)
