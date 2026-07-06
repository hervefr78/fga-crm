# =============================================================================
# FGA CRM - Trends Routes (signal de demande de marche)
# =============================================================================
"""Endpoints du module Trends.

RBAC (cf. doc 03) :
- Lecture + lancement de rapport : admin + manager
- Health (config providers) : admin uniquement
- Les sales n'ont pas acces au module.

Modes :
- quick : execution inline (mock instantane), rapport disponible immediatement
- deep  : execution asynchrone via Celery, l'UI poll GET /jobs/{id}
"""

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.rbac import apply_tenant_filter, check_tenant_access
from app.db.session import get_db
from app.models.trends import TrendCategory, TrendJob, TrendReport
from app.models.user import User
from app.schemas.trends import (
    MAX_SEED_TERMS,
    TrendCategoryResponse,
    TrendHealthResponse,
    TrendJobProgress,
    TrendJobResponse,
    TrendRecommendations,
    TrendReportCreateRequest,
    TrendReportMeta,
    TrendReportResponse,
    TrendSignals,
)
from app.services.trends import cache, orchestrator
from app.services.trends.provider import get_trends_provider

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# RBAC helpers
# ---------------------------------------------------------------------------

def _require_trends_access(user: User = Depends(get_current_user)) -> User:
    if user.role == "sales":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Module Trends : acces reserve admin et manager",
        )
    return user


def _require_trends_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Module Trends : action reservee aux admins",
        )
    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail=f"{field_name} invalide")


def _slugify(value: str) -> str:
    """Slug ASCII d'un sujet libre : sert de category_slug + clef de cache. Borne (DC1)."""
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower().strip()).strip("-")
    return slug[:60] or "sujet"


def _job_to_response(job: TrendJob, *, cache_hit: bool = False) -> TrendJobResponse:
    return TrendJobResponse(
        job_id=job.id,
        mode=job.mode,
        status=job.status,
        provider_primary=job.provider_primary,
        provider_effective=job.provider_effective,
        cache_hit=cache_hit,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error=job.error,
        progress=TrendJobProgress(steps_total=job.steps_total, steps_done=job.steps_done),
        created_at=job.created_at,
    )


def _report_to_response(job: TrendJob, report: TrendReport | None) -> TrendReportResponse:
    if report is None:
        return TrendReportResponse(
            job_id=job.id, status=job.status, summary_md=None,
            opportunity_score=None, signals=None, meta=None,
        )
    insights = report.insights_json or {}
    signals = insights.get("signals")
    meta = insights.get("meta")
    recommendations = insights.get("recommendations")
    return TrendReportResponse(
        job_id=job.id,
        status=job.status,
        summary_md=report.summary_md,
        opportunity_score=float(report.opportunity_score) if report.opportunity_score is not None else None,
        signals=TrendSignals.model_validate(signals) if signals else None,
        meta=TrendReportMeta.model_validate(meta) if meta else None,
        recommendations=(
            TrendRecommendations.model_validate(recommendations) if recommendations else None
        ),
    )


async def _seed_categories_if_empty(db: AsyncSession) -> None:
    """Peuple trend_categories depuis le provider si la table est vide.

    Auto-seeding : le selecteur UI a besoin de categories avec un id stable pour
    creer un job. Idempotent (ne fait rien si des categories existent deja).
    """
    existing = (await db.execute(select(TrendCategory.id).limit(1))).first()
    if existing is not None:
        return
    provider = get_trends_provider()
    try:
        items = await provider.list_categories()
    except Exception as exc:  # noqa: BLE001 — seeding best-effort
        logger.warning("[Trends] seeding categories echoue : %s", exc)
        return
    for order, cat in enumerate(items):
        db.add(TrendCategory(
            provider=provider.name,
            provider_category_id=cat.provider_category_id,
            slug=cat.slug,
            label=cat.label,
            parent_slug=cat.parent_slug,
            display_order=order,
        ))
    await db.commit()


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@router.get("/categories", response_model=list[TrendCategoryResponse])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(_require_trends_access),
) -> list[TrendCategoryResponse]:
    await _seed_categories_if_empty(db)
    rows = (
        await db.execute(
            select(TrendCategory)
            .where(TrendCategory.active.is_(True))
            .order_by(TrendCategory.display_order, TrendCategory.label)
        )
    ).scalars().all()
    return [TrendCategoryResponse.model_validate(c) for c in rows]


# ---------------------------------------------------------------------------
# Creation de rapport (job)
# ---------------------------------------------------------------------------

@router.post("/reports", response_model=TrendJobResponse)
async def create_report(
    payload: TrendReportCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_trends_access),
) -> TrendJobResponse:
    # 1. Cible : categorie du referentiel OU sujet libre (XOR garanti par le schema).
    free_query = payload.normalized_query()
    if free_query is not None:
        # Sujet libre (one-shot, non persiste) : pas de category_id. Le provider
        # utilise seed_terms[0] comme requete -> le sujet passe en tete des seeds.
        category_id_param: str | None = None
        category_slug = _slugify(free_query)
        category_label = free_query
        category_key = f"q:{category_slug}"
        seeds = [free_query, *payload.normalized_seeds()][:MAX_SEED_TERMS]
    else:
        category = await db.get(TrendCategory, payload.category_id)
        if category is None:
            raise HTTPException(status_code=404, detail="Categorie introuvable")
        category_id_param = str(payload.category_id)
        category_slug = category.slug
        category_label = category.label
        category_key = category_id_param
        seeds = payload.normalized_seeds()

    # Objectif : oriente les recommandations LLM (mode Profond) -> entre dans le hash.
    objective_val = payload.objective.value if payload.objective else None
    request_hash = cache.compute_request_hash(
        mode=payload.mode.value,
        category_id=category_key,  # id de categorie, ou "q:<slug>" pour un sujet libre
        country=payload.country,
        language=payload.language,
        timeframe=payload.timeframe.value,
        seed_terms=seeds,
        objective=objective_val,
    )

    # 2. Dedup : un job identique recemment complete -> on le retourne (cache_hit)
    if not payload.refresh:
        ttl_cutoff = datetime.now(UTC) - timedelta(
            seconds=settings.trends_cache_ttl_quick_seconds
        )
        # Dedup restreint a l'org du user (isolation multi-tenant).
        dedup_query = apply_tenant_filter(select(TrendJob), TrendJob, user).where(
            TrendJob.request_hash == request_hash,
            TrendJob.status == "completed",
            TrendJob.created_at >= ttl_cutoff,
        )
        recent = (
            await db.execute(
                dedup_query.order_by(TrendJob.created_at.desc()).limit(1)
            )
        ).scalar_one_or_none()
        if recent is not None:
            return _job_to_response(recent, cache_hit=True)

    # 3. Creation du job
    provider = get_trends_provider()
    job = TrendJob(
        organization_id=user.organization_id,
        created_by=user.id,
        mode=payload.mode.value,
        provider_primary=provider.name,
        status="queued",
        request_hash=request_hash,
        params_json={
            "request_hash": request_hash,
            "category_id": category_id_param,  # None pour un sujet libre
            "category_slug": category_slug,
            "category_label": category_label,
            "country": payload.country,
            "language": payload.language,
            "timeframe": payload.timeframe.value,
            "seed_terms": seeds,
            "objective": objective_val,
            "refresh": payload.refresh,
        },
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # 4. Execution : quick inline, deep via Celery
    if payload.mode.value == "quick":
        await orchestrator.run_job(db, job)
        await db.refresh(job)
    else:
        from app.tasks.trends import trends_run_job_task
        trends_run_job_task.delay(str(job.id))

    return _job_to_response(job, cache_hit=False)


# ---------------------------------------------------------------------------
# Statut de job
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}", response_model=TrendJobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_trends_access),
) -> TrendJobResponse:
    job = await db.get(TrendJob, _parse_uuid(job_id, "job_id"))
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable")
    check_tenant_access(job, user)
    return _job_to_response(job)


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

@router.get("/reports/latest", response_model=TrendReportResponse)
async def get_latest_report(
    category_id: str = Query(...),
    country: str = Query("FR", max_length=8),
    language: str = Query("fr", max_length=8),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_trends_access),
) -> TrendReportResponse:
    cat_uuid = _parse_uuid(category_id, "category_id")
    # Dernier job complete pour cette categorie (+ pays/langue), tous timeframes.
    latest_query = apply_tenant_filter(select(TrendJob), TrendJob, user).where(
        TrendJob.status == "completed",
        TrendJob.params_json["category_id"].astext == str(cat_uuid),
        TrendJob.params_json["country"].astext == country,
        TrendJob.params_json["language"].astext == language,
    )
    job = (
        await db.execute(
            latest_query.order_by(TrendJob.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Aucun rapport disponible")
    report = (
        await db.execute(select(TrendReport).where(TrendReport.job_id == job.id))
    ).scalar_one_or_none()
    return _report_to_response(job, report)


@router.get("/reports/{job_id}", response_model=TrendReportResponse)
async def get_report(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_trends_access),
) -> TrendReportResponse:
    job = await db.get(TrendJob, _parse_uuid(job_id, "job_id"))
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable")
    check_tenant_access(job, user)
    report = (
        await db.execute(select(TrendReport).where(TrendReport.job_id == job.id))
    ).scalar_one_or_none()
    return _report_to_response(job, report)


# ---------------------------------------------------------------------------
# Health (admin)
# ---------------------------------------------------------------------------

@router.get("/health", response_model=TrendHealthResponse)
async def get_health(
    _user: User = Depends(_require_trends_admin),
) -> TrendHealthResponse:
    provider = get_trends_provider()
    result = await provider.healthcheck()
    return TrendHealthResponse(
        provider=result.provider,
        status=result.status,
        latency_ms=result.latency_ms,
        error=result.error,
    )
