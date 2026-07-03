# =============================================================================
# FGA CRM - GEO Routes : Brands
# =============================================================================
"""Endpoints CRUD des marques GEO + overview pour le selecteur."""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import apply_tenant_filter
from app.db.session import get_db
from app.models.geo import GeoBrand, GeoMetricsDaily
from app.models.user import User
from app.schemas.geo import (
    GeoBrandCreate,
    GeoBrandOverviewResponse,
    GeoBrandResponse,
    GeoBrandUpdate,
    GeoEngine,
)

from ._common import (
    _get_brand_or_404,
    _parse_uuid,
    _require_geo_access,
    _require_geo_admin,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Brands
# ---------------------------------------------------------------------------

@router.get("/brands", response_model=list[GeoBrandResponse])
async def list_brands(
    is_owned: bool | None = Query(None),
    organization_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> list[GeoBrandResponse]:
    query = select(GeoBrand).where(GeoBrand.active.is_(True))
    # Isolation multi-tenant : restreindre a l'organisation du user (bypass super-admin)
    query = apply_tenant_filter(query, GeoBrand, user)
    if is_owned is not None:
        query = query.where(GeoBrand.is_owned.is_(is_owned))
    if organization_id is not None:
        oid = _parse_uuid(organization_id, "organization_id")
        query = query.where(GeoBrand.organization_id == oid)
    query = query.order_by(GeoBrand.name).limit(500)
    brands = (await db.execute(query)).scalars().all()
    return [GeoBrandResponse.model_validate(b) for b in brands]


@router.get("/brands/overview", response_model=list[GeoBrandOverviewResponse])
async def brands_overview(
    engine: GeoEngine = Query(...),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> list[GeoBrandOverviewResponse]:
    """Marques possedees + leur visibilite moyenne (moteur/periode) pour le selecteur.

    Une seule requete agregee (pas de N+1) : LEFT JOIN sur la moyenne de
    visibility_rate par marque sur la fenetre demandee.
    """
    cutoff = datetime.now(UTC).date() - timedelta(days=days)
    vis_subq = (
        select(
            GeoMetricsDaily.brand_id.label("brand_id"),
            func.avg(GeoMetricsDaily.visibility_rate).label("vis"),
        )
        .where(
            GeoMetricsDaily.engine == engine.value,
            GeoMetricsDaily.day >= cutoff,
        )
        .group_by(GeoMetricsDaily.brand_id)
        .subquery()
    )
    query = (
        select(GeoBrand, vis_subq.c.vis)
        .outerjoin(vis_subq, vis_subq.c.brand_id == GeoBrand.id)
        .where(GeoBrand.active.is_(True), GeoBrand.is_owned.is_(True))
        .order_by(GeoBrand.name)
        .limit(500)
    )
    # Isolation multi-tenant : restreindre a l'organisation du user (bypass super-admin)
    query = apply_tenant_filter(query, GeoBrand, user)
    rows = (await db.execute(query)).all()
    return [
        GeoBrandOverviewResponse(
            id=brand.id,
            slug=brand.slug,
            name=brand.name,
            visibility_rate=(float(vis) if vis is not None else None),
        )
        for brand, vis in rows
    ]


@router.post("/brands", response_model=GeoBrandResponse, status_code=201)
async def create_brand(
    payload: GeoBrandCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> GeoBrandResponse:
    # Unicite du slug PAR organisation (DC2 — erreur explicite plutot qu'IntegrityError
    # brute). Dedup scopee a l'org (FIX #9) : deux orgs peuvent avoir le meme slug.
    existing = (
        await db.execute(
            apply_tenant_filter(
                select(GeoBrand).where(GeoBrand.slug == payload.slug), GeoBrand, user
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Un slug identique existe deja")

    brand = GeoBrand(
        # Isolation multi-tenant : org resolue cote serveur, pas depuis le payload (DC18)
        organization_id=user.organization_id,
        slug=payload.slug,
        name=payload.name,
        aliases=payload.aliases,
        is_owned=payload.is_owned,
        active=payload.active,
    )
    db.add(brand)
    await db.commit()
    await db.refresh(brand)
    return GeoBrandResponse.model_validate(brand)


@router.get("/brands/{brand_id}", response_model=GeoBrandResponse)
async def get_brand(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> GeoBrandResponse:
    bid = _parse_uuid(brand_id, "brand_id")
    brand = await _get_brand_or_404(db, bid, user)
    return GeoBrandResponse.model_validate(brand)


@router.put("/brands/{brand_id}", response_model=GeoBrandResponse)
async def update_brand(
    brand_id: str,
    payload: GeoBrandUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> GeoBrandResponse:
    bid = _parse_uuid(brand_id, "brand_id")
    brand = await _get_brand_or_404(db, bid, user)

    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"] != brand.slug:
        # Dedup scopee a l'org (FIX #9) : un meme slug peut exister dans une autre org.
        clash = (
            await db.execute(
                apply_tenant_filter(
                    select(GeoBrand).where(GeoBrand.slug == data["slug"]),
                    GeoBrand,
                    user,
                )
            )
        ).scalar_one_or_none()
        if clash is not None:
            raise HTTPException(status_code=409, detail="Un slug identique existe deja")
    for key, value in data.items():
        setattr(brand, key, value)
    await db.commit()
    await db.refresh(brand)
    return GeoBrandResponse.model_validate(brand)


@router.delete("/brands/{brand_id}", status_code=204)
async def delete_brand(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> None:
    bid = _parse_uuid(brand_id, "brand_id")
    brand = await _get_brand_or_404(db, bid, user)
    # Soft delete (active=False) — preserve l'historique des runs/metriques
    brand.active = False
    await db.commit()
