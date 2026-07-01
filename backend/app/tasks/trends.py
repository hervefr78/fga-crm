# =============================================================================
# FGA CRM - Celery Tasks : module Trends
# =============================================================================
"""Task Celery du module Trends (mode deep / recherche profonde).

Le mode quick tourne inline dans la route (mock instantane). Le mode deep passe
ici : execution asynchrone, l'UI poll GET /trends/jobs/{id}.

Celery ne supporte pas les coroutines : wrap via asyncio.run. Le job_id transite
en str et est converti en UUID dans la coroutine.
"""

import asyncio
import logging
from uuid import UUID

from app.db.session import task_session_maker
from app.services.trends import orchestrator
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)


async def _run(job_id: str) -> dict:
    """Charge le job et l'execute (cree sa propre session — pas d'injection FastAPI)."""
    from app.models.trends import TrendJob

    async with task_session_maker() as db:
        job = await db.get(TrendJob, UUID(job_id))
        if job is None:
            logger.warning("[Trends task] job %s introuvable", job_id)
            return {"job_id": job_id, "status": "not_found"}
        await orchestrator.run_job(db, job)
        return {"job_id": job_id, "status": job.status}


@app.task(
    name="app.tasks.trends.trends_run_job_task",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def trends_run_job_task(self, job_id: str) -> dict:
    """Task Celery — execute un job Trends deep."""
    logger.info("[Trends task] job demarre %s", job_id)
    try:
        result = asyncio.run(_run(job_id))
        logger.info("[Trends task] job termine : %s", result)
        return result
    except Exception as exc:
        logger.exception("[Trends task] erreur fatale job %s : %s", job_id, exc)
        raise
