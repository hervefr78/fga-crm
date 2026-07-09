# =============================================================================
# FGA CRM - Celery Tasks : module Lead Engine
# =============================================================================
"""Task periodique du detecteur de signaux Lead Engine.

- lead_engine_scan_task : scanne toutes les orgs actives et cree les signaux
  (funding_detected / mmf_gap) manquants — beat horaire (celery_app).

Celery ne supporte pas nativement les coroutines : on wrappe via asyncio.run.
Kill switch : settings.lead_engine_enabled (skip silencieux + log).
"""

import asyncio
import logging

from app.config import settings
from app.db.session import task_session_maker
from app.services.lead_engine.detector import scan_all_orgs
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)


async def _scan() -> dict:
    """Wrapper async — cree sa propre session DB (pas d'injection FastAPI)."""
    async with task_session_maker() as db:
        return await scan_all_orgs(db)


@app.task(name="app.tasks.lead_engine.lead_engine_scan_task")
def lead_engine_scan_task() -> dict:
    """Scanner les signaux Lead Engine de toutes les organisations actives."""
    if not settings.lead_engine_enabled:
        logger.info("[LeadEngine] Scan desactive (lead_engine_enabled=false)")
        return {"skipped": True}
    result = asyncio.run(_scan())
    logger.info("[LeadEngine] Scan global : %s", result)
    return result
