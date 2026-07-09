# =============================================================================
# FGA CRM - Lead Engine : helpers partages des routes (DC8)
# =============================================================================

import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead_engine import LeadSignal
from app.models.user import User


def parse_uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail="Identifiant invalide") from None


async def get_signal_or_404(db: AsyncSession, signal_id: str, user: User) -> LeadSignal:
    """Signal de l'org du user — 404 (pas 403) si cross-org (pas de divulgation)."""
    signal = await db.get(LeadSignal, parse_uuid(signal_id))
    if signal is None or signal.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Signal introuvable")
    return signal
