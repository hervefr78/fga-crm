# =============================================================================
# FGA CRM - Workflow IA 3 : Sales Insights (synthese hebdo du pipeline)
# =============================================================================
"""Synthese du pipeline en langage naturel : sante vs periode precedente, deals
stagnants (seuils par stage REEL), patterns de perte, 3 actions prioritaires.

Les agregats sont calcules ici (org-scopes) et sont la SEULE source de chiffres
du LLM (regle : aucun chiffre hors agregats, < 5 deals = le dire). La synthese
est persistee (table ai_insights) : la plus recente < 24 h est servie en cache.

RBAC : manager+ uniquement (vue pipeline de l'organisation entiere — un sales
ne voit que ses deals ailleurs, lui exposer les agregats org violerait
l'ownership)."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.activity import Activity
from app.models.ai_workflow import AiInsight
from app.models.deal import PIPELINE_STAGES, Deal
from app.schemas.ai_workflows import INSIGHTS_PROMPT_VERSION, InsightsOutput
from app.services.ai_workflows.client import AiWorkflowError, call_openai_structured
from app.services.ai_workflows.runs import record_run

logger = logging.getLogger(__name__)

# Cache : une synthese generee il y a moins de N heures est servie telle quelle.
INSIGHTS_CACHE_HOURS = 24

# Seuils de stagnation par stage REEL (jours sans activite) — DC5/DC10 : les
# stages 'lead'/'qualified' de la spec n'existent pas dans FGA.
STALE_THRESHOLDS: dict[str, int] = {
    "new": 14,
    "contacted": 10,
    "meeting": 10,
    "proposal": 7,
    "negotiation": 7,
}

_MAX_STALE_LISTED = 15   # deals stagnants detailles dans le contexte (DC1)
_MAX_LOST_LISTED = 10    # deals perdus detailles (avec loss_reason)

INSIGHTS_SYSTEM_PROMPT = """\
Tu es l'analyste pipeline de FGA CRM. A partir des agregats fournis (JAMAIS
d'autres chiffres), produis une synthese hebdomadaire en francais.

Contexte metier : Fast Growth Advisors vend des audits de clarte du message
(999 EUR), un accompagnement fondateur (499 EUR) et de l'advisory (30-150K EUR)
a des startups B2B francaises. Stages du pipeline : new, contacted, meeting,
proposal, negotiation (puis won / lost).

Regles absolues :
- Chaque chiffre cite doit exister dans les agregats fournis. Aucun calcul
  derive non verifiable, aucune extrapolation.
- Si un agregat est vide ou trop petit pour conclure (moins de 5 deals),
  dis-le dans data_caveats au lieu de forcer un pattern.
- loss_patterns : null si aucun pattern detectable.
- top_actions : 3 actions maximum, concretes et actionnables.
- Ton factuel, pas de superlatifs, pas de phrases de transition creuses.
"""


async def _stage_counts(
    db: AsyncSession, org_id, since: datetime | None = None, until: datetime | None = None,
) -> dict:
    """count + montant par stage (org-scope), optionnellement sur une fenetre."""
    query = (
        select(Deal.stage, func.count(Deal.id), func.coalesce(func.sum(Deal.amount), 0.0))
        .where(Deal.organization_id == org_id)
        .group_by(Deal.stage)
    )
    if since is not None:
        query = query.where(Deal.created_at >= since)
    if until is not None:
        query = query.where(Deal.created_at < until)
    rows = (await db.execute(query)).all()
    return {stage: {"count": c, "amount_eur": float(a)} for stage, c, a in rows}


async def _product_counts(db: AsyncSession, org_id) -> dict:
    rows = (
        await db.execute(
            select(Deal.product, func.count(Deal.id))
            .where(Deal.organization_id == org_id, Deal.product.is_not(None))
            .group_by(Deal.product)
        )
    ).all()
    return dict(rows)


async def _stale_deals(db: AsyncSession, org_id) -> list[dict]:
    """Deals actifs dont la derniere activite (ou maj) depasse le seuil du stage."""
    last_activity = (
        select(Activity.deal_id, func.max(Activity.created_at).label("last_at"))
        .where(Activity.deal_id.is_not(None))
        .group_by(Activity.deal_id)
        .subquery()
    )
    rows = (
        await db.execute(
            select(Deal, last_activity.c.last_at)
            .outerjoin(last_activity, last_activity.c.deal_id == Deal.id)
            .where(
                Deal.organization_id == org_id,
                Deal.stage.in_(PIPELINE_STAGES),
            )
        )
    ).all()

    now = datetime.now(UTC)
    stale: list[dict] = []
    for deal, last_at in rows:
        threshold = STALE_THRESHOLDS.get(deal.stage)
        if threshold is None:
            continue
        reference = last_at or deal.updated_at or deal.created_at
        if reference is None:
            continue
        if reference.tzinfo is None:  # SQLite tests : datetimes naives
            reference = reference.replace(tzinfo=UTC)
        idle_days = (now - reference).days
        if idle_days >= threshold:
            stale.append({
                "title": deal.title[:120],
                "stage": deal.stage,
                "amount_eur": deal.amount,
                "idle_days": idle_days,
                "threshold_days": threshold,
            })
    stale.sort(key=lambda d: d["idle_days"], reverse=True)
    return stale


async def _lost_deals(db: AsyncSession, org_id, since: datetime) -> list[dict]:
    rows = (
        await db.execute(
            select(Deal)
            .where(
                Deal.organization_id == org_id,
                Deal.stage == "lost",
                Deal.updated_at >= since,
            )
            .order_by(Deal.updated_at.desc())
            .limit(_MAX_LOST_LISTED)
        )
    ).scalars().all()
    return [
        {"title": d.title[:120], "amount_eur": d.amount, "loss_reason": d.loss_reason}
        for d in rows
    ]


async def collect_aggregates(db: AsyncSession, org_id, period_days: int) -> dict:
    """Assemble les agregats org-scopes (seule source de chiffres du LLM)."""
    now = datetime.now(UTC)
    period_start = now - timedelta(days=period_days)
    prev_start = now - timedelta(days=2 * period_days)

    stale = await _stale_deals(db, org_id)
    return {
        "periode_jours": period_days,
        "pipeline_par_stage": await _stage_counts(db, org_id),
        "nouveaux_deals_periode": await _stage_counts(db, org_id, since=period_start),
        "nouveaux_deals_periode_precedente": await _stage_counts(
            db, org_id, since=prev_start, until=period_start
        ),
        "deals_par_produit": await _product_counts(db, org_id),
        "deals_stagnants": stale[:_MAX_STALE_LISTED],
        "deals_stagnants_total": len(stale),
        "deals_perdus_periode": await _lost_deals(db, org_id, period_start),
        "date_du_jour": now.date().isoformat(),
    }


async def get_weekly_insights(
    db: AsyncSession, org_id, *, period_days: int = 7, refresh: bool = False,
) -> tuple[AiInsight, bool]:
    """Retourne (synthese, cached). Genere via LLM si aucune synthese < 24 h."""
    if not refresh:
        cutoff = datetime.now(UTC) - timedelta(hours=INSIGHTS_CACHE_HOURS)
        recent = (
            await db.execute(
                select(AiInsight)
                .where(
                    AiInsight.organization_id == org_id,
                    AiInsight.period_days == period_days,
                    AiInsight.generated_at >= cutoff,
                )
                .order_by(AiInsight.generated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if recent is not None:
            return recent, True

    aggregates = await collect_aggregates(db, org_id, period_days)
    try:
        output, usage = await call_openai_structured(
            InsightsOutput,
            system=INSIGHTS_SYSTEM_PROMPT,
            user=json.dumps(aggregates, ensure_ascii=False),
            name="weekly_insights",
        )
    except AiWorkflowError as exc:
        record_run(
            db, organization_id=org_id, workflow="insights", target_type="pipeline",
            prompt_version=INSIGHTS_PROMPT_VERSION, model=settings.ai_workflows_model,
            status=exc.kind, error=str(exc),
        )
        await db.commit()
        raise

    insight = AiInsight(
        organization_id=org_id,
        period_days=period_days,
        payload_json={
            **output.model_dump(),
            "model": settings.ai_workflows_model,
            "prompt_version": INSIGHTS_PROMPT_VERSION,
        },
    )
    db.add(insight)
    record_run(
        db, organization_id=org_id, workflow="insights", target_type="pipeline",
        prompt_version=INSIGHTS_PROMPT_VERSION, model=settings.ai_workflows_model,
        status="ok", input_tokens=usage.get("input_tokens"),
        output_tokens=usage.get("output_tokens"),
    )
    await db.commit()
    await db.refresh(insight)
    return insight, False
