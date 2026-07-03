# =============================================================================
# FGA CRM - Integrations API : Startup Radar (synchronisation)
# =============================================================================

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_manager
from app.db.session import get_db
from app.models.user import User
from app.schemas.integration import (
    SyncEnqueuedResponse,
    SyncResultResponse,
    SyncStatusResponse,
)
from app.services import sync_status
from app.services.startup_radar import StartupRadarError
from app.services.startup_radar_sync import sync_recent_startups
from app.tasks.startup_radar_full_sync import full_sync_task

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- POST /startup-radar/sync ----------


@router.post(
    "/startup-radar/sync",
    response_model=SyncEnqueuedResponse,
    status_code=202,
)
async def sync_startup_radar(
    current_user: User = Depends(get_current_manager),
):
    """Lancer une full sync Startup Radar → CRM en tache de fond.

    Reserve aux managers/admins (operation couteuse : ~1000+ requetes SR +
    milliers d'ecritures DB). La sync tourne dans le worker Celery : l'endpoint
    retourne immediatement 202, le frontend poll GET /startup-radar/status
    jusqu'a completed/failed. Les entites creees appartiennent a l'utilisateur
    qui lance le sync.

    Single-flight : refuse (409) si une sync est deja en cours, pour ne pas
    marteler Startup Radar en double.
    """
    job_id = str(uuid.uuid4())
    started_at = datetime.now(UTC).isoformat()

    # Verrou single-flight (Redis SET NX EX atomique — DC4)
    if not await sync_status.try_acquire_lock(job_id):
        raise HTTPException(
            status_code=409,
            detail="Une synchronisation Startup Radar est deja en cours.",
        )

    # Statut 'running' immediat : visible des le 1er poll, avant meme que le
    # worker ait pris la task.
    await sync_status.set_status_async(
        sync_status.build_status(
            job_id=job_id,
            status=sync_status.STATUS_RUNNING,
            started_at=started_at,
        )
    )

    # Enqueue. Si la mise en file echoue, liberer le verrou + marquer failed
    # (DC2 — pas de blocage muet).
    try:
        full_sync_task.delay(str(current_user.id), job_id, started_at)
    except Exception as e:
        logger.error("[Integrations] Enqueue full sync echoue: %s", e)
        # Ecrire le statut 'failed' AVANT de liberer le verrou : si l'ecriture
        # Redis echoue, le verrou reste pose (et expire via TTL) plutot que de
        # laisser un statut 'running' fantome avec un verrou libre.
        await sync_status.set_status_async(
            sync_status.build_status(
                job_id=job_id,
                status=sync_status.STATUS_FAILED,
                started_at=started_at,
                finished_at=datetime.now(UTC).isoformat(),
                error="Echec de mise en file de la synchronisation.",
            )
        )
        await sync_status.release_lock_async(job_id)
        raise HTTPException(
            status_code=503,
            detail="Impossible de lancer la synchronisation (file de tache indisponible).",
        ) from e

    return SyncEnqueuedResponse(status="running", job_id=job_id, started_at=started_at)


# ---------- POST /startup-radar/sync-recent-funding ----------


@router.post(
    "/startup-radar/sync-recent-funding",
    response_model=SyncResultResponse,
    status_code=200,
)
async def sync_recent_funding(
    days_back: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_manager),
) -> SyncResultResponse:
    """Synchroniser uniquement les startups SR creees/modifiees recemment.

    Cible : ramener les nouvelles levees detectees par le pipeline SR
    multi-source (LesPepitesTech, Maddyness, Eldorado, L'Usine Digitale, BODACC)
    sans refaire une full sync (couteuse).

    Cree pour chaque startup avec amount > 0 :
    - Activity 'funding_detected' (idempotent par subject incluant montant+serie)
    - Task 'qualification' (idempotent : 1 task ouverte par company a la fois)

    Args:
        days_back: fenetre de remontee en jours (defaut 7, max 90).
    """
    # DC1 — borner days_back
    if days_back < 1 or days_back > 90:
        raise HTTPException(
            status_code=422,
            detail="days_back doit etre entre 1 et 90",
        )

    try:
        result = await sync_recent_startups(db, current_user, days_back=days_back)
    except StartupRadarError as e:
        logger.error("[Integrations] Erreur sync-recent-funding: %s", e)
        raise HTTPException(
            status_code=503, detail=f"Erreur Startup Radar: {e}",
        ) from e

    return SyncResultResponse(
        companies_created=result.companies_created,
        companies_updated=result.companies_updated,
        contacts_created=result.contacts_created,
        contacts_updated=result.contacts_updated,
        investors_created=result.investors_created,
        investors_updated=result.investors_updated,
        audits_created=result.audits_created,
        funding_activities_created=result.funding_activities_created,
        qualification_tasks_created=result.qualification_tasks_created,
        errors=result.errors,
    )


# ---------- GET /startup-radar/status ----------


@router.get("/startup-radar/status", response_model=SyncStatusResponse)
async def get_sync_status(
    current_user: User = Depends(get_current_manager),
):
    """Statut de la full sync, lu depuis Redis.

    Reserve aux managers/admins (le statut contient des noms d'entites + des
    erreurs internes). Source partagee : visible par tous les workers uvicorn ET
    reflete ce que le worker Celery a ecrit (un global memoire ne le permettrait
    pas).
    """
    st = await sync_status.get_status()

    if st is None:
        return SyncStatusResponse(has_synced=False, status=sync_status.STATUS_IDLE)

    status_value = st.get("status", sync_status.STATUS_IDLE)
    error = st.get("error")

    # Detection de job zombie : statut 'running' mais plus de verrou actif
    # (worker mort/tue avant d'avoir ecrit le statut final). On rapporte 'failed'
    # pour debloquer l'UI (sinon le frontend poll a l'infini).
    if status_value == sync_status.STATUS_RUNNING and not await sync_status.is_locked():
        status_value = sync_status.STATUS_FAILED
        error = "Synchronisation interrompue (worker indisponible). Relancez."

    result = st.get("result")
    return SyncStatusResponse(
        has_synced=status_value == sync_status.STATUS_COMPLETED,
        status=status_value,
        started_at=st.get("started_at"),
        finished_at=st.get("finished_at"),
        error=error,
        last_result=SyncResultResponse(**result) if result else None,
    )
