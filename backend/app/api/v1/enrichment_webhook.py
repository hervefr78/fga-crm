# =============================================================================
# FGA CRM - Enrichissement : endpoint webhook Icypeas (public, HMAC)
# =============================================================================
"""Callback bulkDone d'Icypeas. Public (pas d'auth user) mais verifie par
signature HMAC-SHA1 (secret Icypeas). Resout le bulk -> contacts CRM."""

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.services.enrichment.adapters.icypeas import verify_webhook_signature
from app.services.enrichment.bulk_callback import process_bulk_callback

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook", status_code=200)
async def icypeas_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Recoit le callback bulkDone Icypeas ({signature, timestamp, data})."""
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001 — corps non-JSON
        raise HTTPException(status_code=400, detail="Payload invalide")

    if settings.icypeas_webhook_verify:
        # Path signe = celui de NOTRE URL webhook (configuree), sinon le path recu.
        path = urlparse(settings.icypeas_webhook_url).path if settings.icypeas_webhook_url else request.url.path
        if not verify_webhook_signature(
            settings.icypeas_api_secret or "", path,
            payload.get("timestamp", ""), payload.get("signature", ""),
        ):
            logger.warning("[Icypeas webhook] signature invalide")
            raise HTTPException(status_code=401, detail="Signature invalide")

    result = await process_bulk_callback(db, payload.get("data") or {})
    return {"received": True, **result}
