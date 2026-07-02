# =============================================================================
# FGA CRM - Enrichissement Routes (feature Compass)
# =============================================================================
"""Endpoints d'enrichissement d'emails B2B. RBAC admin + manager (les sales n'y
ont pas acces). 2 modes : company | batch | icp. Jobs async (Celery)."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import apply_tenant_filter, check_tenant_access
from app.db.session import get_db
from app.models.enrichment import EnrichmentJob
from app.models.user import User
from app.schemas.enrichment import (
    EnrichmentJobCreateRequest,
    EnrichmentJobListResponse,
    EnrichmentJobResponse,
    EnrichmentMode,
)
from app.services.enrichment.credit_ledger import reserve_daily_credits

logger = logging.getLogger(__name__)

router = APIRouter()

_CREDITS_PER_TARGET = 5  # estimation grossiere pour le garde-fou quota


def _require_enrichment_access(user: User = Depends(get_current_user)) -> User:
    if user.role == "sales":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Enrichissement : acces reserve admin et manager",
        )
    return user


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="job_id invalide")


def _validate_target(payload: EnrichmentJobCreateRequest) -> None:
    if payload.mode == EnrichmentMode.company and not payload.siren:
        raise HTTPException(422, "mode company : siren requis")
    if payload.mode == EnrichmentMode.batch and not payload.sirens:
        raise HTTPException(422, "mode batch : liste de sirens requise")
    if payload.mode == EnrichmentMode.icp and payload.icp_filter is None:
        raise HTTPException(422, "mode icp : icp_filter requis")


def _estimate_credits(payload: EnrichmentJobCreateRequest) -> int:
    if payload.mode == EnrichmentMode.company:
        return _CREDITS_PER_TARGET
    if payload.mode == EnrichmentMode.batch:
        return len(payload.sirens) * _CREDITS_PER_TARGET
    limit = payload.icp_filter.limit if payload.icp_filter else 50
    return limit * _CREDITS_PER_TARGET


async def _create_and_enqueue(
    db: AsyncSession, user: User, payload: EnrichmentJobCreateRequest
) -> EnrichmentJob:
    org_id = user.organization_id  # source de verite serveur (DC18)
    if not await reserve_daily_credits(str(org_id) if org_id else None, _estimate_credits(payload)):
        raise HTTPException(
            status_code=429, detail="Quota journalier d'enrichissement depasse",
            headers={"Retry-After": "3600"},
        )
    job = EnrichmentJob(
        organization_id=org_id,
        created_by=user.id,
        mode=payload.mode.value,
        target_json=payload.to_target(),
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    from app.tasks.enrichment import enrichment_run_job_task
    enrichment_run_job_task.delay(str(job.id))
    return job


@router.post("/jobs", response_model=EnrichmentJobResponse)
async def create_job(
    payload: EnrichmentJobCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_enrichment_access),
) -> EnrichmentJobResponse:
    _validate_target(payload)
    job = await _create_and_enqueue(db, user, payload)
    return EnrichmentJobResponse.model_validate(job)


@router.get("/jobs", response_model=EnrichmentJobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_enrichment_access),
) -> EnrichmentJobListResponse:
    base = apply_tenant_filter(select(EnrichmentJob), EnrichmentJob, user)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(EnrichmentJob.created_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()
    return EnrichmentJobListResponse(
        items=[EnrichmentJobResponse.model_validate(j) for j in rows],
        total=total, page=page, size=size,
    )


@router.get("/jobs/{job_id}", response_model=EnrichmentJobResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_enrichment_access),
) -> EnrichmentJobResponse:
    job = await db.get(EnrichmentJob, _parse_uuid(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job introuvable")
    check_tenant_access(job, user)
    return EnrichmentJobResponse.model_validate(job)


@router.post("/companies/{siren}/enrich", response_model=EnrichmentJobResponse)
async def enrich_company(
    siren: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_enrichment_access),
) -> EnrichmentJobResponse:
    """Raccourci Mode A : enrichir les decideurs d'une societe (depuis sa fiche)."""
    payload = EnrichmentJobCreateRequest(mode=EnrichmentMode.company, siren=siren[:9])
    _validate_target(payload)
    job = await _create_and_enqueue(db, user, payload)
    return EnrichmentJobResponse.model_validate(job)
