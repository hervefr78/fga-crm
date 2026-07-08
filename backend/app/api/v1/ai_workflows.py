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
from app.core.deps import get_current_manager, get_current_user
from app.core.rbac import check_entity_access, check_tenant_access
from app.db.session import get_db
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.user import User
from app.schemas.ai_workflows import (
    ContactQualifyRequest,
    ContactQualifyResponse,
    DealScoreResponse,
    InsightsResponse,
)
from app.services.ai_workflows.client import AiWorkflowError
from app.services.ai_workflows.insights import get_weekly_insights
from app.services.ai_workflows.qualification import qualify_contact
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


@router.post("/contacts/{contact_id}/qualify", response_model=ContactQualifyResponse)
async def qualify_contact_endpoint(
    contact_id: uuid.UUID,
    payload: ContactQualifyRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ContactQualifyResponse:
    """Qualifie un contact selon SPICED et recommande un routage.

    fast_track cree automatiquement un deal (stage 'new', produit suggere,
    owner = declencheur). Jamais de disqualification automatique. Pas de cache :
    re-qualifier est une action explicite (cout negligeable).
    """
    if not settings.ai_workflows_enabled:
        raise HTTPException(status_code=503, detail="Workflows IA desactives")

    contact = await db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact non trouve")
    check_tenant_access(contact, user)
    check_entity_access(contact, user)

    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI non configure")

    submission = payload.submission_text if payload else None
    try:
        output, deal = await qualify_contact(db, contact, user, submission)
    except AiWorkflowError as exc:
        raise HTTPException(status_code=502, detail=f"Qualification IA indisponible : {exc}")

    qual = contact.ai_qualification or {}
    return ContactQualifyResponse(
        contact_id=str(contact.id),
        routing=output.routing,
        routing_rationale=output.routing_rationale,
        spiced=output.spiced.model_dump(),
        suggested_product=output.suggested_product,
        next_action=output.next_action,
        qualified_at=contact.ai_qualified_at.isoformat() if contact.ai_qualified_at else "",
        deal_created_id=str(deal.id) if deal is not None else None,
        meta={
            "model": qual.get("model"),
            "prompt_version": qual.get("prompt_version"),
        },
    )


@router.get("/insights/weekly", response_model=InsightsResponse)
async def weekly_insights_endpoint(
    period_days: int = Query(7, ge=1, le=90),
    refresh: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_manager),
) -> InsightsResponse:
    """Synthese hebdo du pipeline (manager+ : vue org entiere).

    La synthese la plus recente (< 24 h, meme periode) est servie du cache ;
    refresh=true force une regeneration.
    """
    if not settings.ai_workflows_enabled:
        raise HTTPException(status_code=503, detail="Workflows IA desactives")
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="OpenAI non configure")

    try:
        insight, cached = await get_weekly_insights(
            db, user.organization_id, period_days=period_days, refresh=refresh,
        )
    except AiWorkflowError as exc:
        raise HTTPException(status_code=502, detail=f"Insights IA indisponibles : {exc}")

    p = insight.payload_json or {}
    return InsightsResponse(
        headline=p.get("headline", ""),
        pipeline_health=p.get("pipeline_health", ""),
        stale_deals_summary=p.get("stale_deals_summary", ""),
        loss_patterns=p.get("loss_patterns"),
        top_actions=list(p.get("top_actions") or []),
        data_caveats=list(p.get("data_caveats") or []),
        period_days=insight.period_days,
        generated_at=insight.generated_at.isoformat() if insight.generated_at else "",
        cached=cached,
        meta={"model": p.get("model"), "prompt_version": p.get("prompt_version")},
    )
