# =============================================================================
# FGA CRM - Celery Task : sync incrementale Startup Radar (funding multi-source)
# =============================================================================
"""Task Celery periodique qui declenche la sync incrementale des startups
recentes (avec funding) depuis Startup Radar.

Programme via beat_schedule (cf. celery_app.py) :
- Cron : 09:00 quotidien (apres le pipeline SR 06:00 + enrichissement 08:30)
- Fenetre de remontee : 7 jours (couvre les jours non synces apres incident)
"""

import asyncio
import logging

from sqlalchemy import select

from app.db.session import task_session_maker
from app.models.organization import DEFAULT_ORG_ID
from app.models.user import User
from app.services.startup_radar_sync import sync_recent_startups
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)


async def _run_sync(days_back: int) -> dict:
    """Wrapper async appele par la task Celery (sync) via asyncio.run.

    Cree sa propre DB session (Celery n'a pas d'injection FastAPI).

    Startup Radar est une source FGA-partagee (credentials uniques) : la sync
    cron alimente DETERMINISTIQUEMENT l'org FGA par defaut. Owner = un admin actif
    de cette org (et non "le premier admin trouve", qui serait arbitraire en
    multi-tenant). Une sync SR par-org pour d'autres clients necessiterait des
    credentials SR par tenant — hors scope actuel.
    """
    async with task_session_maker() as db:
        admin = (await db.execute(
            select(User).where(
                User.role == "admin",
                User.is_active.is_(True),
                User.organization_id == DEFAULT_ORG_ID,
            ).limit(1)
        )).scalar_one_or_none()
        if admin is None:
            logger.error("[FundingSync cron] Pas d'admin actif dans l'org FGA — sync annulee")
            return {"status": "error", "reason": "no_admin"}

        result = await sync_recent_startups(db, admin, days_back=days_back)

        return {
            "status": "ok" if not result.errors else "partial",
            "companies_created": result.companies_created,
            "companies_updated": result.companies_updated,
            "contacts_created": result.contacts_created,
            "contacts_updated": result.contacts_updated,
            "funding_activities_created": result.funding_activities_created,
            "qualification_tasks_created": result.qualification_tasks_created,
            "errors_count": len(result.errors),
            "errors": result.errors[:5],  # cap log pour eviter blob enorme
        }


@app.task(name="app.tasks.funding_sync.sync_recent_funding_task", bind=True)
def sync_recent_funding_task(self, days_back: int = 7) -> dict:
    """Task Celery qui declenche la sync incrementale SR → CRM.

    Celery ne supporte pas nativement les tasks async, donc on wrappe
    via asyncio.run. Chaque execution cree son propre event loop isole.

    Args:
        days_back: fenetre de remontee en jours (defaut 7).

    Returns:
        Dict avec status + compteurs (visible dans le backend Celery / logs).
    """
    logger.info("[FundingSync cron] Demarrage sync (days_back=%d)", days_back)
    try:
        result = asyncio.run(_run_sync(days_back))
        logger.info("[FundingSync cron] Termine : %s", result)
        return result
    except Exception as e:
        logger.exception("[FundingSync cron] Erreur fatale : %s", e)
        # Re-raise pour que Celery enregistre la failure (retry possible)
        raise
