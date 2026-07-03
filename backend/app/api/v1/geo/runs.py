# =============================================================================
# FGA CRM - GEO Routes : Runs (trigger + list)
# =============================================================================
"""Endpoints de declenchement et de listing des runs GEO."""

import logging
import math
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.geo import GeoPrompt, GeoRun
from app.models.user import User
from app.schemas.geo import (
    GeoEngine,
    GeoRunListResponse,
    GeoRunResponse,
    GeoRunTriggerRequest,
    GeoRunTriggerResponse,
)

from ._common import (
    _engine_configured,
    _get_brand_or_404,
    _parse_iso_date,
    _parse_uuid,
    _require_geo_access,
    _require_geo_admin,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Runs — trigger + list
# ---------------------------------------------------------------------------

@router.post("/runs/trigger", response_model=GeoRunTriggerResponse)
async def trigger_runs(
    payload: GeoRunTriggerRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> GeoRunTriggerResponse:
    engine = payload.engine.value

    # 1. Moteur configure ? (cle API presente)
    if not _engine_configured(engine):
        raise HTTPException(
            status_code=422,
            detail=f"Moteur '{engine}' non configure (cle API absente cote serveur)",
        )

    # 2. Marque existe et appartient a l'org du user (garde cross-FK) ?
    brand = await _get_brand_or_404(db, payload.brand_id, user)

    # 3. Tous les prompt_ids existent et appartiennent a la marque ?
    prompt_ids = list(payload.prompt_ids)
    found = (
        await db.execute(
            select(GeoPrompt.id).where(
                and_(
                    GeoPrompt.brand_id == brand.id,
                    GeoPrompt.id.in_(prompt_ids),
                )
            )
        )
    ).scalars().all()
    found_set = set(found)
    missing = [str(p) for p in prompt_ids if p not in found_set]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Prompts inconnus ou hors marque : {', '.join(missing)}",
        )

    # 4. Enqueue la task Celery
    # Import tardif — evite de charger Celery a l'import du module route.
    from app.tasks.geo import geo_run_batch_task

    async_result = geo_run_batch_task.delay(  # type: ignore[attr-defined]
        brand_id=str(brand.id),
        engine=engine,
        prompt_ids=[str(p) for p in prompt_ids],
        n_runs=payload.n_runs,
        country=payload.country,
        language=payload.language,
    )

    runs_scheduled = len(prompt_ids) * payload.n_runs
    logger.info(
        "[GEO API] trigger brand=%s engine=%s runs=%d task=%s",
        brand.id, engine, runs_scheduled, async_result.id,
    )
    return GeoRunTriggerResponse(
        task_id=str(async_result.id), runs_scheduled=runs_scheduled
    )


@router.get("/runs", response_model=GeoRunListResponse)
async def list_runs(
    brand_id: str = Query(...),
    engine: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> GeoRunListResponse:
    bid = _parse_uuid(brand_id, "brand_id")
    # Garde cross-FK : la marque parente doit appartenir a l'org du user.
    # On isole les runs via la marque (deterministe) plutot que via
    # GeoRun.organization_id (peuple cote task, hors scope de cette route).
    await _get_brand_or_404(db, bid, user)

    filters = [GeoRun.brand_id == bid]
    if engine:
        if engine not in {e.value for e in GeoEngine}:
            raise HTTPException(status_code=422, detail="engine invalide")
        filters.append(GeoRun.engine == engine)
    if date_from:
        d_from = _parse_iso_date(date_from, "date_from")
        filters.append(GeoRun.run_at >= datetime.combine(d_from, datetime.min.time(), tzinfo=UTC))
    if date_to:
        d_to = _parse_iso_date(date_to, "date_to")
        # borne inclusive : < debut du jour suivant
        filters.append(
            GeoRun.run_at < datetime.combine(d_to + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
        )

    base = select(GeoRun).where(and_(*filters))
    total = (
        await db.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()

    runs = (
        await db.execute(
            base.order_by(GeoRun.run_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()

    pages = math.ceil(total / size) if size else 0
    return GeoRunListResponse(
        items=[GeoRunResponse.model_validate(r) for r in runs],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )
