# =============================================================================
# FGA CRM - GEO Scorer (calcul des metriques quotidiennes)
# =============================================================================
"""Calcul des metriques GEO depuis geo_runs vers geo_metrics_daily.

Les agregats sont calcules en Python depuis les runs du jour (et non en SQL brut)
pour rester portable entre PostgreSQL (prod) et SQLite (tests). Les volumes
journaliers par (marque, moteur) sont faibles (quelques dizaines de runs), donc
l'agregation cote application est sans impact perf.

Formules :
- visibility_rate = mentions / total_runs * 100
- sov            = mentions / total_brands_found * 100
- sov_weighted   = somme(1/position de la marque suivie) / somme(1/rang de toutes
                   les marches trouvees) * 100
- sentiment_avg  = moyenne(positif=1, neutre=0, negatif=-1) sur les runs mentionnes
- reco_rate      = recommandations / mentions * 100
"""

import logging
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.geo import GeoBrand, GeoMetricsDaily, GeoRun

logger = logging.getLogger(__name__)

# Mapping sentiment -> score numerique pour la moyenne
SENTIMENT_SCORE: dict[str, int] = {"positif": 1, "neutre": 0, "negatif": -1}


def _day_bounds(day: date) -> tuple[datetime, datetime]:
    """Bornes [debut_jour, debut_jour_suivant) en UTC.

    Filtrer par range datetime plutot que cast(run_at, Date) : portable PG/SQLite
    et insensible au stockage tz-aware (le cast d'un timestamptz en date echoue
    silencieusement en SQLite).
    """
    start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    return start, start + timedelta(days=1)


def _round2(value: float) -> float:
    """Arrondi a 2 decimales (aligne sur NUMERIC(_, 2))."""
    return round(value, 2)


def _rank_of(entry: dict) -> int | None:
    """Extraire un rang positif depuis une entree brands_found, sinon None."""
    rang = entry.get("rang") if isinstance(entry, dict) else None
    if isinstance(rang, int) and rang >= 1:
        return rang
    return None


async def compute_daily_metrics(
    db: AsyncSession, brand_id: UUID, day: date, engine: str
) -> GeoMetricsDaily | None:
    """Calculer et upserter les metriques pour (brand_id, day, engine).

    Retourne None si aucun run pour cette combinaison (DC2 — pas d'upsert vide).
    """
    # Tous les runs de la journee pour cette marque + ce moteur (range datetime).
    day_start, day_end = _day_bounds(day)
    result = await db.execute(
        select(GeoRun).where(
            and_(
                GeoRun.brand_id == brand_id,
                GeoRun.engine == engine,
                GeoRun.run_at >= day_start,
                GeoRun.run_at < day_end,
            )
        )
    )
    runs = list(result.scalars().all())
    if not runs:
        return None

    total_runs = len(runs)
    mentions = 0
    recommandations = 0
    total_brands_found = 0
    sentiment_scores: list[int] = []
    poids_marque = 0.0       # somme 1/position pour la marque suivie
    poids_total = 0.0        # somme 1/rang pour toutes les marques trouvees

    for run in runs:
        brands_found = run.brands_found or []
        total_brands_found += len(brands_found)

        # Denominateur sov_weighted : 1/rang pour chaque marque trouvee
        for entry in brands_found:
            rang = _rank_of(entry)
            if rang is not None:
                poids_total += 1.0 / rang

        if run.brand_mentioned:
            mentions += 1
            if run.brand_recommended:
                recommandations += 1
            score = SENTIMENT_SCORE.get(run.brand_sentiment or "")
            if score is not None:
                sentiment_scores.append(score)
            if run.brand_position is not None and run.brand_position >= 1:
                poids_marque += 1.0 / run.brand_position

    visibility_rate = _round2(mentions / total_runs * 100) if total_runs else 0.0
    sov = _round2(mentions / total_brands_found * 100) if total_brands_found else None
    sov_weighted = _round2(poids_marque / poids_total * 100) if poids_total else None
    sentiment_avg = (
        _round2(sum(sentiment_scores) / len(sentiment_scores))
        if sentiment_scores
        else None
    )
    reco_rate = _round2(recommandations / mentions * 100) if mentions else None

    # Upsert ON CONFLICT (day, brand_id, engine).
    # pg_insert fonctionne en Postgres ; en SQLite (tests) on retombe sur un
    # SELECT-puis-update/insert manuel (le dialecte ne supporte pas le meme upsert).
    # La metrique herite de l'org de sa marque (isolation multi-tenant).
    org_id = await db.scalar(select(GeoBrand.organization_id).where(GeoBrand.id == brand_id))

    values = {
        "day": day,
        "brand_id": brand_id,
        "engine": engine,
        "organization_id": org_id,
        "visibility_rate": visibility_rate,
        "sov": sov,
        "sov_weighted": sov_weighted,
        "sentiment_avg": sentiment_avg,
        "reco_rate": reco_rate,
        "runs_total": total_runs,
        "computed_at": datetime.now(UTC),
    }

    if "postgresql" in settings.database_url:
        stmt = pg_insert(GeoMetricsDaily).values(**values)
        update_cols = {
            k: stmt.excluded[k]
            for k in (
                "visibility_rate", "sov", "sov_weighted", "sentiment_avg",
                "reco_rate", "runs_total", "computed_at",
            )
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=["day", "brand_id", "engine"],
            set_=update_cols,
        )
        await db.execute(stmt)
    else:
        # Fallback portable (tests SQLite) : SELECT puis update/insert
        existing = (
            await db.execute(
                select(GeoMetricsDaily).where(
                    and_(
                        GeoMetricsDaily.day == day,
                        GeoMetricsDaily.brand_id == brand_id,
                        GeoMetricsDaily.engine == engine,
                    )
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            for key, val in values.items():
                if key in ("day", "brand_id", "engine", "organization_id"):
                    continue
                setattr(existing, key, val)
        else:
            db.add(GeoMetricsDaily(**values))

    await db.flush()

    # Recharger la ligne pour la retourner
    metrics = (
        await db.execute(
            select(GeoMetricsDaily).where(
                and_(
                    GeoMetricsDaily.day == day,
                    GeoMetricsDaily.brand_id == brand_id,
                    GeoMetricsDaily.engine == engine,
                )
            )
        )
    ).scalar_one_or_none()
    return metrics


async def compute_all_metrics(
    db: AsyncSession, target_date: date | None = None
) -> dict:
    """Calculer les metriques pour toutes les combinaisons brand x engine du jour.

    target_date par defaut = hier (les runs du jour courant sont encore partiels).
    Retourne {computed: int, errors: list[str]}.
    """
    day = target_date or (datetime.now(UTC).date() - timedelta(days=1))

    # Combinaisons (brand_id, engine) distinctes ayant des runs ce jour-la.
    day_start, day_end = _day_bounds(day)
    combos = (
        await db.execute(
            select(GeoRun.brand_id, GeoRun.engine)
            .where(and_(GeoRun.run_at >= day_start, GeoRun.run_at < day_end))
            .group_by(GeoRun.brand_id, GeoRun.engine)
        )
    ).all()

    computed = 0
    errors: list[str] = []
    for brand_id, engine in combos:
        try:
            metrics = await compute_daily_metrics(db, brand_id, day, engine)
            if metrics is not None:
                computed += 1
        except Exception as exc:  # noqa: BLE001 — on continue sur les autres combos
            msg = f"brand={brand_id} engine={engine}: {exc}"
            logger.error("[GEO scorer] echec compute : %s", msg)
            errors.append(msg)

    await db.commit()
    logger.info(
        "[GEO scorer] jour=%s computed=%d errors=%d", day, computed, len(errors)
    )
    return {"computed": computed, "errors": errors}
