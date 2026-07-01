# =============================================================================
# FGA CRM - GEO Audit-visibility Routes (integration Startup Radar)
# =============================================================================
"""Endpoints service-a-service de mesure de visibilite GEO a la demande.

Auth : cle service `crm_...` (scope `geo:audit`). SR fabrique les prompts, le CRM
mesure sur Perplexity via une marque ephemere et renvoie le resultat agrege.
Cf. docs/integrations/SR-GEO-visibility-API-contract.md.
"""

import logging
import os
import uuid
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import require_service_scope
from app.db.session import get_db
from app.models.geo import GeoAuditJob
from app.models.user import User
from app.schemas.geo_audit import (
    AuditVisibilityCreateResponse,
    AuditVisibilityRequest,
    AuditVisibilityResult,
    AuditVisibilityStatusResponse,
)
from app.services.geo.audit import compute_request_hash

logger = logging.getLogger(__name__)

router = APIRouter()

_AUDIT_ENGINE = "perplexity"
_DEDUP_DAYS = 30
_QUOTA_TTL = 86400  # 24h


def _parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="audit_id invalide")


def _redis_url() -> str:
    return os.getenv("REDIS_URL", settings.redis_url)


async def _quota_allow(key_name: str) -> bool:
    """Incremente + verifie le quota journalier de la cle. Fail-open si Redis KO."""
    day = datetime.now(UTC).strftime("%Y%m%d")
    redis_key = f"geo_audit:quota:{key_name}:{day}"
    client = redis_async.from_url(_redis_url(), decode_responses=True)
    try:
        count = await client.incr(redis_key)
        if count == 1:
            await client.expire(redis_key, _QUOTA_TTL)
        return count <= settings.geo_audit_daily_quota
    except Exception as exc:  # noqa: BLE001 — fail-open (ne pas bloquer sur Redis KO)
        logger.warning("[GEO audit] quota Redis indisponible : %s", exc)
        return True
    finally:
        await client.aclose()


@router.post("/audit-visibility", response_model=AuditVisibilityCreateResponse)
async def create_audit_visibility(
    payload: AuditVisibilityRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_service_scope("geo:audit")),
) -> AuditVisibilityCreateResponse:
    prompts = payload.clean_prompts()
    if not prompts:
        raise HTTPException(status_code=422, detail="Au moins un prompt non vide requis")
    aliases = payload.clean_aliases()
    request_hash = compute_request_hash(
        domain=payload.domain, engine=_AUDIT_ENGINE, prompts=prompts,
        country=payload.country, language=payload.language,
    )

    # 1. Dedup (30j) : une mesure recente identique -> cache_hit, pas de re-facturation.
    if not payload.refresh:
        cutoff = datetime.now(UTC) - timedelta(days=_DEDUP_DAYS)
        recent = (
            await db.execute(
                select(GeoAuditJob)
                .where(
                    GeoAuditJob.request_hash == request_hash,
                    GeoAuditJob.status == "completed",
                    GeoAuditJob.finished_at >= cutoff,
                )
                .order_by(GeoAuditJob.finished_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if recent is not None:
            return AuditVisibilityCreateResponse(
                audit_id=recent.id, status="completed", cache_hit=True
            )

    # 2. Quota journalier (consomme seulement pour une vraie mesure, pas les cache hits)
    key_name = getattr(request.state, "api_key_name", "unknown")
    if not await _quota_allow(key_name):
        raise HTTPException(
            status_code=429,
            detail="Quota journalier de mesures depasse",
            headers={"Retry-After": "3600"},
        )

    # 3. Creation du job + enqueue
    job = GeoAuditJob(
        domain=payload.domain,
        company_name=payload.company_name,
        request_hash=request_hash,
        engine=_AUDIT_ENGINE,
        status="queued",
        params_json={
            "prompts": prompts,
            "aliases": aliases,
            "country": payload.country,
            "language": payload.language,
        },
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    from app.tasks.geo import geo_audit_visibility_task
    geo_audit_visibility_task.delay(str(job.id))

    return AuditVisibilityCreateResponse(audit_id=job.id, status="queued", cache_hit=False)


@router.get("/audit-visibility/{audit_id}", response_model=AuditVisibilityStatusResponse)
async def get_audit_visibility(
    audit_id: str,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_service_scope("geo:audit")),
) -> AuditVisibilityStatusResponse:
    job = await db.get(GeoAuditJob, _parse_uuid(audit_id))
    if job is None:
        raise HTTPException(status_code=404, detail="audit_id introuvable")

    result = None
    if job.status == "completed" and job.result_json:
        result = AuditVisibilityResult.model_validate(job.result_json)

    return AuditVisibilityStatusResponse(
        audit_id=job.id,
        status=job.status,
        engine=job.engine,
        company_name=job.company_name,
        domain=job.domain,
        created_at=job.created_at,
        result=result,
    )
