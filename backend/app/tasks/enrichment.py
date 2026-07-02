# =============================================================================
# FGA CRM - Celery Tasks : enrichissement d'emails B2B (feature Compass)
# =============================================================================
"""Task Celery d'enrichissement (mode company | batch | icp). Async via
asyncio.run + task_session_maker (NullPool). job_id transite en str."""

import asyncio
import logging
from uuid import UUID

from app.config import settings
from app.db.session import task_session_maker
from app.services.enrichment.bulk_callback import reconcile_stuck_bulks
from app.services.enrichment.orchestrator import run_enrichment_job
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)


async def _run(job_id: str) -> dict:
    from app.models.enrichment import EnrichmentJob

    async with task_session_maker() as db:
        job = await db.get(EnrichmentJob, UUID(job_id))
        if job is None:
            logger.warning("[Enrichment task] job %s introuvable", job_id)
            return {"job_id": job_id, "status": "not_found"}
        await run_enrichment_job(db, job)
        return {"job_id": job_id, "status": job.status}


@app.task(
    name="app.tasks.enrichment.enrichment_run_job_task",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def enrichment_run_job_task(self, job_id: str) -> dict:
    """Task Celery — execute un job d'enrichissement."""
    logger.info("[Enrichment task] demarre %s", job_id)
    try:
        result = asyncio.run(_run(job_id))
        logger.info("[Enrichment task] termine : %s", result)
        return result
    except Exception as exc:
        logger.exception("[Enrichment task] erreur fatale %s : %s", job_id, exc)
        raise


async def _reconcile() -> dict:
    async with task_session_maker() as db:
        n = await reconcile_stuck_bulks(db, timeout_hours=settings.enrichment_bulk_timeout_hours)
        return {"reconciled": n}


@app.task(name="app.tasks.enrichment.enrichment_reconcile_bulks_task")
def enrichment_reconcile_bulks_task() -> dict:
    """Task Celery (beat) — finalise les bulks bloques sans callback (timeout)."""
    try:
        result = asyncio.run(_reconcile())
        if result["reconciled"]:
            logger.info("[Enrichment reconcile] %s bulk(s) finalise(s)", result["reconciled"])
        return result
    except Exception as exc:
        logger.exception("[Enrichment reconcile] erreur : %s", exc)
        raise
