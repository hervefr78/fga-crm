# =============================================================================
# FGA CRM - Celery Task : full sync Startup Radar -> CRM (tache de fond)
# =============================================================================
"""Full sync SR -> CRM executee en arriere-plan.

Flux :
1. POST /integrations/startup-radar/sync pose le verrou single-flight + le
   statut 'running' dans Redis, puis enqueue cette task et retourne 202.
2. Cette task fait le travail (plusieurs minutes : startups, investors,
   contacts, audits — ~3000 requetes a SR), ecrit le statut final dans Redis,
   et LIBERE TOUJOURS le verrou (finally).
3. Le frontend poll GET /integrations/startup-radar/status jusqu'a
   completed/failed.

Calque sur app/tasks/funding_sync.py : Celery ne supporte pas nativement les
tasks async, donc on wrappe via asyncio.run (event loop isole par task).
"""

import asyncio
import dataclasses
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.session import task_session_maker
from app.models.user import User
from app.services.startup_radar_sync import full_sync
from app.services.sync_status import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    build_status,
    release_lock_sync,
    set_status_sync,
)
from app.tasks.celery_app import app

logger = logging.getLogger(__name__)

# Cap des erreurs stockees dans le statut Redis (DC1) : sur une sync degradee
# (SR down), result.errors peut contenir des milliers d'entrees retransferees a
# chaque poll. On garde les N premieres + un compteur.
MAX_STORED_ERRORS = 50


async def _run_full_sync(user_id: str) -> dict:
    """Charge l'owner (celui qui a clique) dans une session dediee puis lance
    la full sync. Retourne le SyncResult serialise en dict."""
    async with task_session_maker() as db:
        user = (await db.execute(
            select(User).where(User.id == uuid.UUID(user_id)),
        )).scalar_one_or_none()
        # Message generique : le statut Redis est expose via l'API, ne pas y
        # fuiter d'identifiant interne. Le detail (user_id) reste dans les logs.
        if user is None or not user.is_active:
            logger.error("[FullSync] Owner invalide/inactif: %s", user_id)
            raise ValueError("Utilisateur introuvable ou inactif")

        # Isolation multi-tenant : org de rattachement des entites creees.
        # Priorite au user declencheur ; fallback sur le premier admin actif si
        # le user n'a pas encore d'org (phase expand : organization_id nullable).
        organization_id = user.organization_id
        if organization_id is None:
            admin = (await db.execute(
                select(User).where(
                    User.role == "admin", User.is_active.is_(True)
                ).limit(1)
            )).scalar_one_or_none()
            organization_id = admin.organization_id if admin else None
        if organization_id is None:
            logger.error(
                "[FullSync] Aucune organization_id resoluble (user=%s sans org, "
                "pas d'admin avec org)", user_id,
            )
            raise ValueError("Organisation introuvable pour la synchronisation")

        result = await full_sync(db, user, organization_id)
        return dataclasses.asdict(result)


def _cap_errors(result: dict) -> dict:
    """Borne result['errors'] avant stockage Redis (DC1)."""
    errors = result.get("errors") or []
    if len(errors) > MAX_STORED_ERRORS:
        extra = len(errors) - MAX_STORED_ERRORS
        result["errors"] = [
            *errors[:MAX_STORED_ERRORS],
            f"... +{extra} autres erreurs (voir logs serveur)",
        ]
    return result


@app.task(name="app.tasks.startup_radar_full_sync.full_sync_task", bind=True)
def full_sync_task(self, user_id: str, job_id: str, started_at: str) -> dict:
    """Full sync SR -> CRM en tache de fond.

    Args:
        user_id: owner des entites creees (celui qui a lance la sync).
        job_id: identifiant du job (valeur du verrou pose par l'endpoint).
        started_at: timestamp ISO du lancement (pour le statut).

    Le statut 'running' a deja ete pose par l'endpoint. Ici on ecrit le statut
    final (completed/failed) et on libere le verrou dans tous les cas.
    """
    logger.info("[FullSync] Demarrage job=%s user=%s", job_id, user_id)
    try:
        result = _cap_errors(asyncio.run(_run_full_sync(user_id)))
        set_status_sync(build_status(
            job_id=job_id,
            status=STATUS_COMPLETED,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
            result=result,
        ))
        logger.info(
            "[FullSync] Termine job=%s — companies +%d, contacts +%d, erreurs %d",
            job_id,
            result["companies_created"],
            result["contacts_created"],
            len(result["errors"]),
        )
        return result
    except Exception as e:
        logger.exception("[FullSync] Echec job=%s : %s", job_id, e)
        set_status_sync(build_status(
            job_id=job_id,
            status=STATUS_FAILED,
            started_at=started_at,
            finished_at=datetime.now(UTC).isoformat(),
            error=str(e),
        ))
        raise
    finally:
        # En dernier (apres l'ecriture du statut) : on libere SEULEMENT notre
        # propre verrou (compare-and-delete par job_id).
        release_lock_sync(job_id)
