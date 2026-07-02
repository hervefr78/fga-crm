# =============================================================================
# FGA CRM - GEO Routes (Generative Engine Optimization)
# =============================================================================
"""Endpoints du module GEO.

RBAC :
- Lecture (brands, prompts, runs, dashboard, competitors) : admin + manager
- Ecriture (create/update/delete, trigger, health) : admin uniquement

Le module GEO est cloisonne : les sales n'y ont pas acces du tout.
"""

import logging
import math
import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.rbac import apply_tenant_filter, check_tenant_access
from app.db.session import get_db
from app.models.geo import GeoBrand, GeoMetricsDaily, GeoPrompt, GeoRun
from app.models.user import User
from app.schemas.geo import (
    GeoBrandCreate,
    GeoBrandOverviewResponse,
    GeoBrandResponse,
    GeoBrandUpdate,
    GeoDashboardResponse,
    GeoEngine,
    GeoHealthResponse,
    GeoMetricsDailyResponse,
    GeoPromptCreate,
    GeoPromptResponse,
    GeoPromptUpdate,
    GeoRunListResponse,
    GeoRunResponse,
    GeoRunTriggerRequest,
    GeoRunTriggerResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Mapping moteur -> attribut settings de la cle API (DC8 — source unique)
ENGINE_API_KEY_ATTR: dict[str, str] = {
    "perplexity": "perplexity_api_key",
    "openai": "openai_api_key",
    "gemini": "gemini_api_key",
    "claude": "claude_api_key",
    "google_aio": "serpapi_key",
    # "grok" : pas de cle dediee en settings (P3) — considere non configure
}

# Fenetre par defaut du dashboard si date_from non fourni
DEFAULT_DASHBOARD_DAYS = 30

# Top N pour competitors / sources
TOP_N = 10


# ---------------------------------------------------------------------------
# RBAC helpers
# ---------------------------------------------------------------------------

def _require_geo_access(user: User = Depends(get_current_user)) -> User:
    if user.role == "sales":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Module GEO : acces reserve admin et manager",
        )
    return user


def _require_geo_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("admin",):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Module GEO : action reservee aux admins",
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


def _parse_iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422, detail=f"{field_name} doit etre une date ISO YYYY-MM-DD"
        )


def _engine_configured(engine: str) -> bool:
    """True si la cle API du moteur est presente dans settings."""
    attr = ENGINE_API_KEY_ATTR.get(engine)
    if attr is None:
        return False
    return bool(getattr(settings, attr, None))


async def _get_brand_or_404(
    db: AsyncSession, brand_id: uuid.UUID, user: User
) -> GeoBrand:
    brand = (
        await db.execute(select(GeoBrand).where(GeoBrand.id == brand_id))
    ).scalar_one_or_none()
    if brand is None:
        raise HTTPException(status_code=404, detail="Marque GEO introuvable")
    # Isolation multi-tenant : 404 si la marque est hors organisation (bypass super-admin)
    check_tenant_access(brand, user)
    return brand


async def _get_prompt_or_404(
    db: AsyncSession, brand_id: uuid.UUID, prompt_id: uuid.UUID, user: User
) -> GeoPrompt:
    prompt = (
        await db.execute(
            select(GeoPrompt).where(
                and_(GeoPrompt.id == prompt_id, GeoPrompt.brand_id == brand_id)
            )
        )
    ).scalar_one_or_none()
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt GEO introuvable")
    # Isolation multi-tenant : 404 si le prompt est hors organisation (bypass super-admin)
    check_tenant_access(prompt, user)
    return prompt


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
    # Unicite du slug (DC2 — erreur explicite plutot qu'IntegrityError brute)
    existing = (
        await db.execute(select(GeoBrand).where(GeoBrand.slug == payload.slug))
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
        clash = (
            await db.execute(select(GeoBrand).where(GeoBrand.slug == data["slug"]))
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


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@router.get("/brands/{brand_id}/prompts", response_model=list[GeoPromptResponse])
async def list_prompts(
    brand_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> list[GeoPromptResponse]:
    bid = _parse_uuid(brand_id, "brand_id")
    # Garde cross-FK : la marque parente doit appartenir a l'org du user
    await _get_brand_or_404(db, bid, user)
    prompts = (
        await db.execute(
            select(GeoPrompt)
            .where(and_(GeoPrompt.brand_id == bid, GeoPrompt.active.is_(True)))
            .order_by(GeoPrompt.created_at.desc())
            .limit(500)
        )
    ).scalars().all()
    return [GeoPromptResponse.model_validate(p) for p in prompts]


@router.post(
    "/brands/{brand_id}/prompts", response_model=GeoPromptResponse, status_code=201
)
async def create_prompt(
    brand_id: str,
    payload: GeoPromptCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> GeoPromptResponse:
    bid = _parse_uuid(brand_id, "brand_id")
    # Garde cross-FK : la marque parente doit appartenir a l'org du user
    await _get_brand_or_404(db, bid, user)
    prompt = GeoPrompt(
        # Isolation multi-tenant : org resolue cote serveur, pas depuis le payload (DC18)
        organization_id=user.organization_id,
        brand_id=bid,
        text=payload.text,
        intent=payload.intent.value,
        persona=payload.persona,
        country=payload.country,
        language=payload.language,
        tags=payload.tags,
        priority=payload.priority,
        active=payload.active,
    )
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    return GeoPromptResponse.model_validate(prompt)


@router.put(
    "/brands/{brand_id}/prompts/{prompt_id}", response_model=GeoPromptResponse
)
async def update_prompt(
    brand_id: str,
    prompt_id: str,
    payload: GeoPromptUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> GeoPromptResponse:
    bid = _parse_uuid(brand_id, "brand_id")
    pid = _parse_uuid(prompt_id, "prompt_id")
    prompt = await _get_prompt_or_404(db, bid, pid, user)

    data = payload.model_dump(exclude_unset=True)
    # intent est un enum -> stocker la valeur str
    if "intent" in data and data["intent"] is not None:
        data["intent"] = data["intent"].value
    for key, value in data.items():
        setattr(prompt, key, value)
    await db.commit()
    await db.refresh(prompt)
    return GeoPromptResponse.model_validate(prompt)


@router.delete("/brands/{brand_id}/prompts/{prompt_id}", status_code=204)
async def delete_prompt(
    brand_id: str,
    prompt_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> None:
    bid = _parse_uuid(brand_id, "brand_id")
    pid = _parse_uuid(prompt_id, "prompt_id")
    prompt = await _get_prompt_or_404(db, bid, pid, user)
    prompt.active = False
    await db.commit()


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


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=list[GeoHealthResponse])
async def geo_health(
    _user: User = Depends(_require_geo_admin),
) -> list[GeoHealthResponse]:
    """Statut des moteurs GEO collectables (P1/P2).

    Pour chaque moteur supporte par le collecteur : si la cle API est absente ->
    'unconfigured' ; sinon on tente un appel de test minimal -> 'ok' / 'error'.
    """
    from app.services.geo.collector import get_collector

    checked_at = datetime.now(UTC)
    results: list[GeoHealthResponse] = []

    # On ne teste que les moteurs collectables (P1/P2)
    for engine in ("perplexity", "openai", "gemini"):
        if not _engine_configured(engine):
            results.append(
                GeoHealthResponse(
                    engine=engine, status="unconfigured", checked_at=checked_at
                )
            )
            continue
        try:
            collector = get_collector(engine)
            # Appel de test minimal (peu couteux)
            await collector.collect("ping", country="FR", language="fr")
            results.append(
                GeoHealthResponse(engine=engine, status="ok", checked_at=checked_at)
            )
        except Exception as exc:  # noqa: BLE001 — on rapporte l'erreur, pas de 500
            logger.warning("[GEO health] %s en erreur : %s", engine, exc)
            results.append(
                GeoHealthResponse(
                    engine=engine,
                    status="error",
                    checked_at=checked_at,
                    error=str(exc)[:300],
                )
            )

    return results


# ---------------------------------------------------------------------------
# P3 — Alertes
# ---------------------------------------------------------------------------

@router.get("/brands/{brand_id}/alerts", response_model=list[dict])
async def brand_alerts(
    brand_id: str,
    engine: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> list[dict]:
    """Alertes GEO detectees sur la semaine ecoulee pour une marque."""
    from app.services.geo.alerts import detect_weekly_alerts

    bid = _parse_uuid(brand_id, "brand_id")
    await _get_brand_or_404(db, bid, user)

    if engine is not None and engine not in {e.value for e in GeoEngine}:
        raise HTTPException(status_code=422, detail="engine invalide")

    alerts = await detect_weekly_alerts(db, brand_id=bid, engine=engine or None)
    return [
        {
            "alert_type": a.alert_type,
            "engine": a.engine,
            "severity": a.severity,
            "message": a.message,
            "detail": a.detail,
            "detected_at": a.detected_at.isoformat(),
        }
        for a in alerts
    ]


# ---------------------------------------------------------------------------
# P4 — Gap detection et boucle d'optimisation
# ---------------------------------------------------------------------------

@router.get("/brands/{brand_id}/gaps", response_model=list[dict])
async def brand_gaps(
    brand_id: str,
    engine: str = Query(...),
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> list[dict]:
    """Prompts ou la marque n'a pas ete mentionnee dans les N derniers jours.

    Pour chaque gap : le prompt, ses runs recents, les sources concurrentes citees.
    C'est l'input de la boucle d'optimisation P4 : detecter -> agir -> re-mesurer.
    """
    from datetime import timedelta

    bid = _parse_uuid(brand_id, "brand_id")
    await _get_brand_or_404(db, bid, user)

    if engine not in {e.value for e in GeoEngine}:
        raise HTTPException(422, detail="engine invalide")

    cutoff = datetime.now(UTC) - timedelta(days=days)

    # Tous les prompts actifs de la marque
    prompts = (await db.execute(
        select(GeoPrompt).where(
            and_(GeoPrompt.brand_id == bid, GeoPrompt.active.is_(True))
        ).limit(200)
    )).scalars().all()

    if not prompts:
        return []

    prompt_ids_list = [p.id for p in prompts]

    # Batch unique — 1 requete au lieu de N (evite le N+1)
    all_runs = (await db.execute(
        select(GeoRun).where(
            and_(
                GeoRun.prompt_id.in_(prompt_ids_list),
                GeoRun.engine == engine,
                GeoRun.run_at >= cutoff,
            )
        ).order_by(GeoRun.run_at.desc()).limit(2000)
    )).scalars().all()

    # Grouper par prompt_id (max 10 runs gardes par prompt)
    runs_by_prompt: dict[uuid.UUID, list] = defaultdict(list)
    for run in all_runs:
        if len(runs_by_prompt[run.prompt_id]) < 10:
            runs_by_prompt[run.prompt_id].append(run)

    gaps = []
    for prompt in prompts:
        recent_runs = runs_by_prompt.get(prompt.id, [])

        if not recent_runs:
            continue  # jamais teste sur ce moteur

        mention_count = sum(1 for r in recent_runs if r.brand_mentioned)
        total = len(recent_runs)

        if mention_count == 0:
            # Pas une seule mention -> gap total
            # Extraire les sources concurrentes des runs
            competitor_sources: dict[str, int] = {}
            competitor_brands: dict[str, int] = {}
            for run in recent_runs:
                for cit in (run.citations or []):
                    domain = cit.get("domain", "")
                    if domain:
                        competitor_sources[domain] = competitor_sources.get(domain, 0) + 1
                for brand_entry in (run.brands_found or []):
                    nom = brand_entry.get("nom", "")
                    if nom:
                        competitor_brands[nom] = competitor_brands.get(nom, 0) + 1

            top_sources = sorted(competitor_sources.items(), key=lambda x: -x[1])[:5]
            top_competitors = sorted(competitor_brands.items(), key=lambda x: -x[1])[:5]

            gaps.append({
                "prompt_id": str(prompt.id),
                "prompt_text": prompt.text,
                "intent": prompt.intent,
                "priority": prompt.priority,
                "runs_checked": total,
                "mentions": 0,
                "visibility_rate": 0.0,
                "top_competitor_sources": [
                    {"domain": d, "count": c} for d, c in top_sources
                ],
                "top_competitors": [
                    {"nom": n, "count": c} for n, c in top_competitors
                ],
                "last_run_at": (
                    recent_runs[0].run_at.isoformat() if recent_runs else None
                ),
                "action_suggestion": _suggest_action(prompt.intent, top_sources),
            })
        elif mention_count / total < 0.5:
            # Mention partielle -> gap partiel (opportunity)
            gaps.append({
                "prompt_id": str(prompt.id),
                "prompt_text": prompt.text,
                "intent": prompt.intent,
                "priority": prompt.priority,
                "runs_checked": total,
                "mentions": mention_count,
                "visibility_rate": round(mention_count / total * 100, 1),
                "top_competitor_sources": [],
                "top_competitors": [],
                "last_run_at": (
                    recent_runs[0].run_at.isoformat() if recent_runs else None
                ),
                "action_suggestion": _suggest_action(prompt.intent, []),
            })

    # Trier : prioritaires d'abord, puis visibilite croissante
    gaps.sort(key=lambda g: (not g["priority"], g["visibility_rate"]))
    return gaps


def _suggest_action(intent: str, top_sources: list[tuple]) -> str:
    """Suggestion d'action content basee sur l'intention et les sources dominantes.

    P4 — logique heuristique (pas d'appel LLM — rapide et deterministe).
    """
    source_names = [d for d, _ in top_sources]

    # Detecter la nature des sources dominantes
    has_reddit = any("reddit" in s for s in source_names)
    has_wiki = any("wikipedia" in s for s in source_names)
    has_comparator = any(
        s in ("g2.com", "capterra.com", "producthunt.com", "trustpilot.com")
        for s in source_names
    )

    if intent == "comparatif":
        if has_comparator:
            return "Creer/optimiser fiche G2, Capterra ou Product Hunt avec donnees chiffrees"
        return "Publier une comparaison structuree (Q&A, tableau) sur le site"

    if intent == "transactionnel":
        if has_reddit:
            return "Animer la presence Reddit/communaute : repondre aux threads pertinents"
        return "Creer une page FAQ dense avec donnees chiffrees et cas clients"

    # informationnel (defaut)
    if has_wiki:
        return "Renforcer les pages Wikipedia / Wikidata liees a la marque"
    return "Publier des contenus definitionnels (guides, glossaires, Q&A) avec schema.org FAQ"


@router.post("/brands/{brand_id}/gaps/remeasure", response_model=GeoRunTriggerResponse)
async def trigger_gap_remeasure(
    brand_id: str,
    engine: str = Query(...),
    days: int = Query(default=7, ge=1, le=90),
    n_runs: int = Query(default=3, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> GeoRunTriggerResponse:
    """Declencher un re-run sur TOUS les prompts en gap pour re-mesurer l'impact.

    C'est le bouton de cloture de la boucle P4 : detecter -> agir -> re-mesurer.
    """
    from datetime import timedelta

    bid = _parse_uuid(brand_id, "brand_id")
    await _get_brand_or_404(db, bid, user)

    if engine not in {e.value for e in GeoEngine}:
        raise HTTPException(422, "engine invalide")
    if not _engine_configured(engine):
        raise HTTPException(
            422, f"Moteur {engine} non configure (cle API manquante)"
        )

    cutoff = datetime.now(UTC) - timedelta(days=days)

    # Prompts avec 0 mention sur la periode — batch unique (evite N+1)
    prompts = (await db.execute(
        select(GeoPrompt).where(
            and_(GeoPrompt.brand_id == bid, GeoPrompt.active.is_(True))
        ).limit(200)
    )).scalars().all()

    # Prompts qui ont AU MOINS une mention sur la periode (pour exclusion)
    prompt_ids_all = [p.id for p in prompts]
    mentioned_prompt_ids_result = (await db.execute(
        select(GeoRun.prompt_id).where(
            and_(
                GeoRun.prompt_id.in_(prompt_ids_all),
                GeoRun.engine == engine,
                GeoRun.run_at >= cutoff,
                GeoRun.brand_mentioned.is_(True),
            )
        ).distinct()
    )).scalars().all()
    mentioned_set = set(mentioned_prompt_ids_result)

    # Gap = prompts qui ont eu des runs mais aucune mention
    has_runs_result = (await db.execute(
        select(GeoRun.prompt_id).where(
            and_(
                GeoRun.prompt_id.in_(prompt_ids_all),
                GeoRun.engine == engine,
                GeoRun.run_at >= cutoff,
            )
        ).distinct()
    )).scalars().all()
    has_runs_set = set(has_runs_result)

    # Cap a 50 pour eviter des batches excessifs
    gap_prompt_ids = [
        p.id for p in prompts
        if p.id in has_runs_set and p.id not in mentioned_set
    ][:50]

    if not gap_prompt_ids:
        raise HTTPException(404, "Aucun gap detecte — rien a re-mesurer")

    from app.tasks.geo import geo_run_batch_task
    async_result = geo_run_batch_task.delay(  # type: ignore[attr-defined]
        brand_id=str(bid),
        engine=engine,
        prompt_ids=[str(p) for p in gap_prompt_ids],
        n_runs=n_runs,
        country="FR",
        language="fr",
    )

    runs_scheduled = len(gap_prompt_ids) * n_runs
    logger.info(
        "[GEO P4] remeasure brand=%s engine=%s gaps=%d runs=%d task=%s",
        bid, engine, len(gap_prompt_ids), runs_scheduled, async_result.id,
    )

    return GeoRunTriggerResponse(
        task_id=str(async_result.id), runs_scheduled=runs_scheduled
    )
