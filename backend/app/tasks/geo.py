# =============================================================================
# FGA CRM - Celery Tasks : module GEO
# =============================================================================
"""Tasks Celery du module GEO.

- geo_run_batch_task : execute un batch de runs (collect -> extract -> store)
- geo_compute_metrics_task : calcule/met a jour les metriques quotidiennes

Celery ne supporte pas nativement les coroutines : on wrappe via asyncio.run.
Tous les IDs transitent en str (JSON-serializable) et sont convertis en UUID
dans la coroutine.
"""

import asyncio
import logging
from datetime import date
from uuid import UUID

from app.db.session import task_session_maker
from app.services.geo.pipeline import execute_geo_batch
from app.services.geo.scorer import compute_all_metrics
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)


async def _run_batch(
    brand_id: str,
    engine: str,
    prompt_ids: list[str],
    n_runs: int,
    country: str,
    language: str,
) -> dict:
    """Wrapper async — cree sa propre session DB (pas d'injection FastAPI)."""
    brand_uuid = UUID(brand_id)
    prompt_uuids = [UUID(p) for p in prompt_ids]

    async with task_session_maker() as db:
        result = await execute_geo_batch(
            db,
            brand_id=brand_uuid,
            engine=engine,
            prompt_ids=prompt_uuids,
            n_runs=n_runs,
            country=country,
            language=language,
        )
    # Les RunResult ne sont pas JSON-serializables — on ne renvoie que les compteurs.
    return {
        "total": result["total"],
        "success": result["success"],
        "failed": result["failed"],
    }


@app.task(
    name="app.tasks.geo.geo_run_batch_task",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def geo_run_batch_task(
    self,
    brand_id: str,
    engine: str,
    prompt_ids: list[str],
    n_runs: int = 3,
    country: str = "FR",
    language: str = "fr",
) -> dict:
    """Task Celery — execute un batch de runs GEO."""
    logger.info(
        "[GEO task] batch demarre brand=%s engine=%s prompts=%d n_runs=%d",
        brand_id, engine, len(prompt_ids), n_runs,
    )
    try:
        result = asyncio.run(
            _run_batch(brand_id, engine, prompt_ids, n_runs, country, language)
        )
        logger.info("[GEO task] batch termine : %s", result)
        return result
    except Exception as exc:
        logger.exception("[GEO task] erreur fatale batch : %s", exc)
        raise


async def _compute_metrics(target_date: str | None) -> dict:
    """Wrapper async pour le calcul des metriques."""
    parsed: date | None = date.fromisoformat(target_date) if target_date else None
    async with task_session_maker() as db:
        return await compute_all_metrics(db, target_date=parsed)


@app.task(name="app.tasks.geo.geo_compute_metrics_task", bind=True)
def geo_compute_metrics_task(
    self,
    brand_id: str | None = None,
    target_date: str | None = None,
) -> dict:
    """Task Celery — calcule/met a jour les metriques quotidiennes.

    target_date : ISO YYYY-MM-DD, defaut = hier (gere dans compute_all_metrics).
    brand_id est accepte pour compat future (filtrage par marque) mais le calcul
    courant porte sur toutes les combinaisons du jour.
    """
    logger.info(
        "[GEO task] compute metrics brand=%s date=%s", brand_id, target_date
    )
    try:
        result = asyncio.run(_compute_metrics(target_date))
        logger.info("[GEO task] metrics calculees : %s", result)
        return result
    except Exception as exc:
        logger.exception("[GEO task] erreur fatale metrics : %s", exc)
        raise
