# =============================================================================
# FGA CRM - GEO Pipeline (orchestrateur)
# =============================================================================
"""Orchestrateur principal du module GEO.

execute_geo_run : un run complet collect -> extract -> derive metriques -> stocke.
execute_geo_batch : N runs par prompt, sequentiel (respecte les quotas API).

Sequence d'un run :
1. Fetch le prompt
2. collect() -> CollectorResult
3. Tronquer raw_answer (settings.geo_raw_answer_max_chars)
4. extraire_marques() -> ExtractionResult
5. Deriver brand_mentioned / position / sentiment / recommended via les aliases
6. Inserer GeoRun + commit

Guard anti-doublon : si (prompt_id, engine, run_index, aujourd'hui) existe deja,
on retourne le RunResult existant sans re-executer (DC4 — idempotence).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.geo import GeoBrand, GeoPrompt, GeoRun
from app.schemas.geo import ExtractionResult, MarqueTrouvee
from app.services.geo.collector import get_collector
from app.services.geo.extractor import extraire_marques

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    run_id: UUID | None
    prompt_id: UUID
    brand_id: UUID
    engine: str
    run_index: int
    success: bool
    error: str | None = None


def _normalize(value: str) -> str:
    """Normaliser un nom de marque pour la comparaison (casse + espaces)."""
    return (value or "").strip().lower()


def _match_brand(
    brand: GeoBrand, extraction: ExtractionResult
) -> MarqueTrouvee | None:
    """Trouver l'entree d'extraction correspondant a la marque suivie.

    Match par nom OU alias (comparaison normalisee). Retourne l'entree de plus
    petit rang si plusieurs correspondent (premiere apparition).
    """
    targets = {_normalize(brand.name)}
    targets |= {_normalize(a) for a in (brand.aliases or []) if a}
    targets.discard("")

    matches = [m for m in extraction.marques if _normalize(m.nom) in targets]
    if not matches:
        return None
    return min(matches, key=lambda m: m.rang)


def _brands_found_payload(extraction: ExtractionResult) -> list[dict]:
    """Serialiser l'extraction en payload JSONB pour brands_found."""
    return [
        {
            "nom": m.nom,
            "rang": m.rang,
            "recommandee": m.recommandee,
            "sentiment": m.sentiment.value,
            "justification": m.justification,
        }
        for m in extraction.marques
    ]


async def _existing_run(
    db: AsyncSession,
    prompt_id: UUID,
    engine: str,
    run_index: int,
    day: date,
) -> GeoRun | None:
    """Guard anti-doublon : chercher un run identique pour aujourd'hui.

    Filtre par range datetime [jour, jour+1) plutot que cast(run_at, Date) :
    portable PG/SQLite et insensible au stockage tz-aware (le cast en date
    echoue silencieusement en SQLite).
    """
    day_start = datetime.combine(day, datetime.min.time(), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)
    result = await db.execute(
        select(GeoRun).where(
            and_(
                GeoRun.prompt_id == prompt_id,
                GeoRun.engine == engine,
                GeoRun.run_index == run_index,
                GeoRun.run_at >= day_start,
                GeoRun.run_at < day_end,
            )
        )
    )
    return result.scalars().first()


async def execute_geo_run(
    db: AsyncSession,
    prompt_id: UUID,
    brand_id: UUID,
    engine: str,
    run_index: int,
    country: str = "FR",
    language: str = "fr",
) -> RunResult:
    """Executer un run complet : collect -> extract -> derive -> stocke."""
    today = datetime.now(UTC).date()

    # 0. Guard anti-doublon (SELECT puis INSERT — on veut savoir si c'est un doublon)
    existing = await _existing_run(db, prompt_id, engine, run_index, today)
    if existing is not None:
        logger.info(
            "[GEO pipeline] doublon ignore prompt=%s engine=%s idx=%d",
            prompt_id, engine, run_index,
        )
        return RunResult(
            run_id=existing.id,
            prompt_id=prompt_id,
            brand_id=brand_id,
            engine=engine,
            run_index=run_index,
            success=True,
        )

    try:
        # 1. Fetch le prompt + la marche (aliases necessaires au matching)
        prompt = (
            await db.execute(select(GeoPrompt).where(GeoPrompt.id == prompt_id))
        ).scalar_one_or_none()
        if prompt is None:
            raise ValueError(f"Prompt introuvable : {prompt_id}")

        brand = (
            await db.execute(select(GeoBrand).where(GeoBrand.id == brand_id))
        ).scalar_one_or_none()
        if brand is None:
            raise ValueError(f"Marque introuvable : {brand_id}")

        # 2. Collecte
        collector = get_collector(engine)
        logger.info(
            "[GEO pipeline] collect prompt=%s engine=%s idx=%d",
            prompt_id, engine, run_index,
        )
        collected = await collector.collect(
            prompt.text, country=country, language=language
        )

        # 3. Troncature avant stockage
        raw_answer = (collected.raw_answer or "")[: settings.geo_raw_answer_max_chars]

        # Pour Google AIO : appearance = si le contenu brut est non vide (Overview apparu).
        # On lit l'engine depuis le CollectorResult (chaque collecteur le renseigne)
        # plutot que depuis l'instance, plus robuste aux mocks.
        appearance = None
        if collected.engine == "google_aio":
            appearance = bool((collected.raw_answer or "").strip())

        # 4. Extraction structuree (toujours gpt-4o-mini)
        logger.info("[GEO pipeline] extract prompt=%s", prompt_id)
        extraction = await extraire_marques(
            raw_answer, max_chars=settings.geo_extract_input_max_chars
        )

        # 5. Derivation des metriques par-run
        matched = _match_brand(brand, extraction)
        brand_mentioned = matched is not None
        brand_position = matched.rang if matched else None
        brand_sentiment = matched.sentiment.value if matched else None
        brand_recommended = matched.recommandee if matched else None

        # 6. Insertion du run (organization_id hérité du prompt)
        run = GeoRun(
            organization_id=prompt.organization_id,
            prompt_id=prompt_id,
            brand_id=brand_id,
            run_index=run_index,
            engine=engine,
            model_version=collected.model_version or None,
            country=country,
            language=language,
            raw_answer=raw_answer,
            citations=collected.citations,
            brands_found=_brands_found_payload(extraction),
            brand_mentioned=brand_mentioned,
            brand_position=brand_position,
            brand_sentiment=brand_sentiment,
            brand_recommended=brand_recommended,
            appearance=appearance,
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)

        logger.info(
            "[GEO pipeline] run ok id=%s mentioned=%s position=%s",
            run.id, brand_mentioned, brand_position,
        )
        return RunResult(
            run_id=run.id,
            prompt_id=prompt_id,
            brand_id=brand_id,
            engine=engine,
            run_index=run_index,
            success=True,
        )

    except Exception as exc:  # noqa: BLE001 — on capture pour ne pas planter le batch
        await db.rollback()
        logger.exception(
            "[GEO pipeline] echec run prompt=%s engine=%s idx=%d : %s",
            prompt_id, engine, run_index, exc,
        )
        return RunResult(
            run_id=None,
            prompt_id=prompt_id,
            brand_id=brand_id,
            engine=engine,
            run_index=run_index,
            success=False,
            error=str(exc),
        )


async def execute_geo_batch(
    db: AsyncSession,
    brand_id: UUID,
    engine: str,
    prompt_ids: list[UUID],
    n_runs: int = 3,
    country: str = "FR",
    language: str = "fr",
) -> dict:
    """Lancer N runs pour chaque prompt (sequentiel — respecte les quotas API)."""
    results: list[RunResult] = []
    success = 0
    failed = 0

    for prompt_id in prompt_ids:
        for run_index in range(1, n_runs + 1):
            result = await execute_geo_run(
                db,
                prompt_id=prompt_id,
                brand_id=brand_id,
                engine=engine,
                run_index=run_index,
                country=country,
                language=language,
            )
            results.append(result)
            if result.success:
                success += 1
            else:
                failed += 1

    logger.info(
        "[GEO pipeline] batch termine brand=%s engine=%s total=%d ok=%d ko=%d",
        brand_id, engine, len(results), success, failed,
    )
    return {
        "total": len(results),
        "success": success,
        "failed": failed,
        "results": results,
    }
