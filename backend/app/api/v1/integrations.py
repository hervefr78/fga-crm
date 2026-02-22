# =============================================================================
# FGA CRM - Integrations API (Startup Radar sync)
# =============================================================================

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.integration import SyncResultResponse, SyncStatusResponse
from app.services.startup_radar import StartupRadarError
from app.services.startup_radar_sync import full_sync, get_last_sync_result

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- POST /startup-radar/sync ----------


@router.post("/startup-radar/sync", response_model=SyncResultResponse, status_code=200)
async def sync_startup_radar(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lancer une synchronisation complete Startup Radar → CRM.

    Les entites creees appartiennent a l'utilisateur qui lance le sync.
    """
    try:
        result = await full_sync(db, current_user)
    except StartupRadarError as e:
        logger.error("[Integrations] Erreur sync SR: %s", e)
        raise HTTPException(status_code=503, detail=f"Erreur Startup Radar: {e}") from e

    return SyncResultResponse(
        companies_created=result.companies_created,
        companies_updated=result.companies_updated,
        contacts_created=result.contacts_created,
        contacts_updated=result.contacts_updated,
        investors_created=result.investors_created,
        investors_updated=result.investors_updated,
        audits_created=result.audits_created,
        errors=result.errors,
    )


# ---------- GET /startup-radar/status ----------


@router.get("/startup-radar/status", response_model=SyncStatusResponse)
async def get_sync_status(
    current_user: User = Depends(get_current_user),
):
    """Retourner le statut de la derniere synchronisation."""
    last = get_last_sync_result()

    if last is None:
        return SyncStatusResponse(has_synced=False, last_result=None)

    return SyncStatusResponse(
        has_synced=True,
        last_result=SyncResultResponse(
            companies_created=last.companies_created,
            companies_updated=last.companies_updated,
            contacts_created=last.contacts_created,
            contacts_updated=last.contacts_updated,
            investors_created=last.investors_created,
            investors_updated=last.investors_updated,
            audits_created=last.audits_created,
            errors=last.errors,
        ),
    )
