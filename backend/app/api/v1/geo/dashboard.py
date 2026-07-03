# =============================================================================
# FGA CRM - GEO Routes : Dashboard + competitors
# =============================================================================
"""Endpoints d'agregation : dashboard visibilite et concurrents d'une marque."""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.geo import GeoMetricsDaily, GeoRun
from app.models.user import User
from app.schemas.geo import (
    GeoBrandResponse,
    GeoDashboardResponse,
    GeoEngine,
    GeoMetricsDailyResponse,
)

from ._common import (
    _get_brand_or_404,
    _parse_iso_date,
    _parse_uuid,
    _require_geo_access,
)

router = APIRouter()

# Fenetre par defaut du dashboard si date_from non fourni
DEFAULT_DASHBOARD_DAYS = 30

# Top N pour competitors / sources
TOP_N = 10


# ---------------------------------------------------------------------------
# Dashboard + competitors
# ---------------------------------------------------------------------------

def _resolve_window(date_from: str | None, date_to: str | None) -> tuple[date, date]:
    """Resoudre la fenetre [date_from, date_to] avec defaut 30 jours."""
    d_to = _parse_iso_date(date_to, "date_to") if date_to else datetime.now(UTC).date()
    d_from = (
        _parse_iso_date(date_from, "date_from")
        if date_from
        else d_to - timedelta(days=DEFAULT_DASHBOARD_DAYS)
    )
    if d_from > d_to:
        raise HTTPException(status_code=422, detail="date_from doit preceder date_to")
    return d_from, d_to


@router.get("/brands/{brand_id}/dashboard", response_model=GeoDashboardResponse)
async def brand_dashboard(
    brand_id: str,
    engine: str = Query(...),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> GeoDashboardResponse:
    bid = _parse_uuid(brand_id, "brand_id")
    if engine not in {e.value for e in GeoEngine}:
        raise HTTPException(status_code=422, detail="engine invalide")
    brand = await _get_brand_or_404(db, bid, user)
    d_from, d_to = _resolve_window(date_from, date_to)

    # Metriques pre-calculees sur la fenetre
    metrics = (
        await db.execute(
            select(GeoMetricsDaily)
            .where(
                and_(
                    GeoMetricsDaily.brand_id == bid,
                    GeoMetricsDaily.engine == engine,
                    GeoMetricsDaily.day >= d_from,
                    GeoMetricsDaily.day <= d_to,
                )
            )
            .order_by(GeoMetricsDaily.day)
            .limit(366)
        )
    ).scalars().all()

    top_competitors, top_sources = await _aggregate_runs(
        db, bid, engine, d_from, d_to
    )

    return GeoDashboardResponse(
        brand=GeoBrandResponse.model_validate(brand),
        engine=engine,
        date_from=d_from,
        date_to=d_to,
        metrics=[GeoMetricsDailyResponse.model_validate(m) for m in metrics],
        top_competitors=top_competitors,
        top_sources=top_sources,
    )


async def _aggregate_runs(
    db: AsyncSession,
    brand_id: uuid.UUID,
    engine: str,
    d_from: date,
    d_to: date,
) -> tuple[list[dict], list[dict]]:
    """Agreger concurrents + sources depuis les runs de la fenetre.

    Volumes bornes (limite 5000 runs) — agregation Python portable PG/SQLite.
    """
    runs = (
        await db.execute(
            select(GeoRun.brands_found, GeoRun.citations)
            .where(
                and_(
                    GeoRun.brand_id == brand_id,
                    GeoRun.engine == engine,
                    GeoRun.run_at
                    >= datetime.combine(d_from, datetime.min.time(), tzinfo=UTC),
                    GeoRun.run_at
                    < datetime.combine(d_to + timedelta(days=1), datetime.min.time(), tzinfo=UTC),
                )
            )
            .limit(5000)
        )
    ).all()

    competitor_mentions: dict[str, int] = defaultdict(int)
    source_counts: dict[str, int] = defaultdict(int)
    total_mentions = 0

    for brands_found, citations in runs:
        for entry in brands_found or []:
            nom = (entry.get("nom") if isinstance(entry, dict) else None) or ""
            nom = nom.strip()
            if nom:
                competitor_mentions[nom] += 1
                total_mentions += 1
        for cit in citations or []:
            domain = (cit.get("domain") if isinstance(cit, dict) else None) or ""
            domain = domain.strip()
            if domain:
                source_counts[domain] += 1

    top_competitors = [
        {
            "nom": nom,
            "mentions": count,
            "sov_share": round(count / total_mentions * 100, 2) if total_mentions else 0.0,
        }
        for nom, count in sorted(
            competitor_mentions.items(), key=lambda kv: kv[1], reverse=True
        )[:TOP_N]
    ]
    top_sources = [
        {"domain": domain, "count": count}
        for domain, count in sorted(
            source_counts.items(), key=lambda kv: kv[1], reverse=True
        )[:TOP_N]
    ]
    return top_competitors, top_sources


@router.get("/brands/{brand_id}/competitors")
async def brand_competitors(
    brand_id: str,
    engine: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> list[dict]:
    bid = _parse_uuid(brand_id, "brand_id")
    await _get_brand_or_404(db, bid, user)
    if engine is not None and engine not in {e.value for e in GeoEngine}:
        raise HTTPException(status_code=422, detail="engine invalide")
    d_from, d_to = _resolve_window(date_from, date_to)

    # Si engine non fourni : agreger tous les moteurs (boucle sur les distincts)
    engines: list[str]
    if engine:
        engines = [engine]
    else:
        engines = list(
            (
                await db.execute(
                    select(GeoRun.engine)
                    .where(GeoRun.brand_id == bid)
                    .group_by(GeoRun.engine)
                )
            ).scalars().all()
        )

    merged: dict[str, int] = defaultdict(int)
    total = 0
    for eng in engines:
        competitors, _ = await _aggregate_runs(db, bid, eng, d_from, d_to)
        for c in competitors:
            merged[c["nom"]] += c["mentions"]
            total += c["mentions"]

    return [
        {
            "nom": nom,
            "mentions": count,
            "sov_share": round(count / total * 100, 2) if total else 0.0,
        }
        for nom, count in sorted(merged.items(), key=lambda kv: kv[1], reverse=True)[
            :TOP_N
        ]
    ]
