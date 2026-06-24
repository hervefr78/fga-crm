# =============================================================================
# FGA CRM - GEO Alertes
# =============================================================================
"""Service d'alertes GEO.

Detecte les anomalies critiques sur les metriques GEO :
- Chute de SoV semaine/semaine > seuil
- Effondrement sur un prompt prioritaire (visibility_rate -> 0)
- Pic de sentiment negatif (sentiment_avg < -0.5)
- Concurrent depassant notre marque en SoV

Format des alertes : liste de dataclasses GeoAlert (pas de modele DB — stocke
cote appelant si besoin).
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import GeoBrand, GeoMetricsDaily, GeoPrompt, GeoRun
from app.services.geo.scorer import _day_bounds

logger = logging.getLogger(__name__)

# Seuils (valeurs documentees, pas de surcharge runtime pour cette iteration)
SOV_DROP_THRESHOLD = 20.0      # % de chute SoV semaine/semaine pour alerter
VISIBILITY_FLOOR = 0.0         # visibility_rate = 0 sur prompt prioritaire = alerte
SENTIMENT_FLOOR = -0.5         # sentiment_avg < seuil = alerte negatif


@dataclass
class GeoAlert:
    alert_type: str           # sov_drop | visibility_zero | sentiment_negative | competitor_overtake
    brand_id: UUID
    engine: str
    severity: str             # info | warning | critical
    message: str
    detail: dict = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))


async def detect_weekly_alerts(
    db: AsyncSession,
    brand_id: UUID | None = None,
    engine: str | None = None,
    reference_date: date | None = None,
) -> list[GeoAlert]:
    """Detecter les alertes sur la fenetre semaine courante vs semaine precedente.

    reference_date : date de fin de la semaine courante (defaut = aujourd'hui).
    Si brand_id est None, analyser toutes les marques owned (is_owned=True).
    Si engine est None, analyser tous les moteurs avec donnees.

    Retourne une liste de GeoAlert (peut etre vide).
    """
    ref = reference_date or datetime.now(UTC).date()
    week_end = ref
    week_start = ref - timedelta(days=7)
    prev_week_start = week_start - timedelta(days=7)

    alerts: list[GeoAlert] = []

    # Resoudre la liste de brand_ids a analyser
    if brand_id is not None:
        brand_ids = [brand_id]
    else:
        owned_brands = (await db.execute(
            select(GeoBrand.id).where(
                and_(GeoBrand.is_owned.is_(True), GeoBrand.active.is_(True))
            )
        )).scalars().all()
        brand_ids = list(owned_brands)

    for bid in brand_ids:
        # Moteurs a analyser
        if engine:
            engines = [engine]
        else:
            engines_result = (await db.execute(
                select(GeoMetricsDaily.engine)
                .where(GeoMetricsDaily.brand_id == bid)
                .group_by(GeoMetricsDaily.engine)
            )).scalars().all()
            engines = list(engines_result)

        for eng in engines:
            # Metriques semaine courante (moyenne sur la periode)
            current = await _avg_metrics_period(db, bid, eng, week_start, week_end)
            previous = await _avg_metrics_period(db, bid, eng, prev_week_start, week_start)

            if current is None:
                continue  # pas de donnees cette semaine

            # 1. Chute SoV
            if (
                current.get("sov") is not None
                and previous is not None
                and previous.get("sov") is not None
                and previous["sov"] > 0
            ):
                drop = previous["sov"] - current["sov"]
                if drop >= SOV_DROP_THRESHOLD:
                    alert = GeoAlert(
                        alert_type="sov_drop",
                        brand_id=bid,
                        engine=eng,
                        severity="critical" if drop >= 40 else "warning",
                        message=(
                            f"Chute SoV {eng}: {previous['sov']:.1f}% -> "
                            f"{current['sov']:.1f}% (-{drop:.1f}pts)"
                        ),
                        detail={
                            "sov_prev": previous["sov"],
                            "sov_curr": current["sov"],
                            "drop": drop,
                        },
                    )
                    logger.info("[GEO alerts] %s", alert.message)
                    alerts.append(alert)

            # 2. Sentiment negatif
            if (
                current.get("sentiment_avg") is not None
                and current["sentiment_avg"] < SENTIMENT_FLOOR
            ):
                alert = GeoAlert(
                    alert_type="sentiment_negative",
                    brand_id=bid,
                    engine=eng,
                    severity="warning",
                    message=f"Sentiment negatif {eng}: {current['sentiment_avg']:.2f}",
                    detail={"sentiment_avg": current["sentiment_avg"]},
                )
                logger.info("[GEO alerts] %s", alert.message)
                alerts.append(alert)

            # 3. Prompts prioritaires a visibilite zero
            priority_gaps = await _find_priority_zero_visibility(
                db, bid, eng, week_start, week_end
            )
            for gap_text in priority_gaps:
                alert = GeoAlert(
                    alert_type="visibility_zero",
                    brand_id=bid,
                    engine=eng,
                    severity="critical",
                    message=f"Prompt prioritaire absent sur {eng}: « {gap_text[:80]}… »",
                    detail={"prompt_text": gap_text},
                )
                logger.info("[GEO alerts] %s", alert.message)
                alerts.append(alert)

    return alerts


async def _avg_metrics_period(
    db: AsyncSession, brand_id: UUID, engine: str, start: date, end: date
) -> dict | None:
    """Metriques moyennes sur une periode depuis geo_metrics_daily."""
    rows = (await db.execute(
        select(GeoMetricsDaily).where(
            and_(
                GeoMetricsDaily.brand_id == brand_id,
                GeoMetricsDaily.engine == engine,
                GeoMetricsDaily.day >= start,
                GeoMetricsDaily.day < end,
            )
        )
    )).scalars().all()

    if not rows:
        return None

    def avg(vals):
        cleaned = [v for v in vals if v is not None]
        return sum(cleaned) / len(cleaned) if cleaned else None

    return {
        "sov": avg([r.sov for r in rows]),
        "sov_weighted": avg([r.sov_weighted for r in rows]),
        "visibility_rate": avg([r.visibility_rate for r in rows]),
        "sentiment_avg": avg([r.sentiment_avg for r in rows]),
        "reco_rate": avg([r.reco_rate for r in rows]),
    }


async def _find_priority_zero_visibility(
    db: AsyncSession, brand_id: UUID, engine: str, start: date, end: date
) -> list[str]:
    """Textes des prompts prioritaires ou la brand n'a jamais ete mentionnee."""
    # Tous les prompts prioritaires actifs pour cette marque
    priority_prompts = (await db.execute(
        select(GeoPrompt).where(
            and_(
                GeoPrompt.brand_id == brand_id,
                GeoPrompt.priority.is_(True),
                GeoPrompt.active.is_(True),
            )
        )
    )).scalars().all()

    if not priority_prompts:
        return []

    day_start, _ = _day_bounds(start)
    _, day_end = _day_bounds(end - timedelta(days=1))

    gaps = []
    for prompt in priority_prompts:
        runs_with_mention = (await db.execute(
            select(GeoRun.id).where(
                and_(
                    GeoRun.prompt_id == prompt.id,
                    GeoRun.engine == engine,
                    GeoRun.run_at >= day_start,
                    GeoRun.run_at < day_end,
                    GeoRun.brand_mentioned.is_(True),
                )
            ).limit(1)
        )).scalar_one_or_none()

        if runs_with_mention is None:
            gaps.append(prompt.text)

    return gaps
