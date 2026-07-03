# =============================================================================
# FGA CRM - Enrichissement : endpoint webhook Icypeas (public, HMAC)
# =============================================================================
"""Callback bulkDone d'Icypeas. Public (pas d'auth user) mais verifie par
signature HMAC-SHA1 (secret Icypeas). Resout le bulk -> contacts CRM."""

import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from urllib.parse import urlparse

import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_db
from app.services.enrichment.adapters.icypeas import verify_webhook_signature
from app.services.enrichment.bulk_callback import process_bulk_callback

logger = logging.getLogger(__name__)

router = APIRouter()

# Endpoint PUBLIC : borne la taille du corps AVANT parsing (#8, DC1) — sinon un
# attaquant sans secret force le chargement d'un JSON geant en memoire (la verif
# HMAC intervient apres le parsing).
_MAX_BODY_BYTES = 2 * 1024 * 1024  # 2 Mo
# Fenetre anti-rejeu (#2) : la signature Icypeas ne couvre que path+timestamp
# (pas le corps) -> une signature valide capturee est rejouable. On borne la
# fenetre a la fraicheur du timestamp.
_MAX_TIMESTAMP_SKEW_S = 300
# Anti-rejeu single-use (FIX #12) : le couple (timestamp, signature) valide est
# marque comme vu dans Redis (SET NX). Un attaquant qui rejoue une signature
# capturee avec un `data` forge dans la fenetre de fraicheur est refuse. Le TTL
# couvre la fenetre + une marge (au-dela, le timestamp est deja rejete).
_NONCE_TTL_S = _MAX_TIMESTAMP_SKEW_S + 60
# Timeout court : si Redis est indisponible, fail-open rapide (voir
# _mark_nonce_or_replay) sans bloquer le pipeline d'enrichissement.
_NONCE_REDIS_TIMEOUT_S = 0.5

_nonce_client: redis_async.Redis | None = None


def _get_nonce_client() -> redis_async.Redis:
    """Client Redis async (singleton, event loop FastAPI) pour le nonce anti-rejeu.

    Client dedie a timeout court : distinct du client de statut SR pour ne pas
    coupler les deux usages, et pour fail-open vite si Redis est down.
    """
    global _nonce_client
    if _nonce_client is None:
        url = os.getenv("REDIS_URL", settings.redis_url)
        _nonce_client = redis_async.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=_NONCE_REDIS_TIMEOUT_S,
            socket_timeout=_NONCE_REDIS_TIMEOUT_S,
        )
    return _nonce_client


async def _mark_nonce_or_replay(timestamp: str, signature: str) -> bool:
    """Marque le couple (timestamp, signature) comme vu (single-use) via Redis.

    Retourne True si c'est un REJEU (nonce deja present), False si premiere vue.
    SET NX EX atomique (DC4). Fail-open sur erreur Redis : la signature + la
    fenetre de fraicheur restent une defense ; on ne casse pas le pipeline sur un
    blip Redis (retourne False = laisse passer, avec log). (FIX #12)
    """
    nonce = hashlib.sha256(f"{timestamp}{signature}".encode()).hexdigest()
    key = f"icypeas:wh:nonce:{nonce}"
    try:
        stored = await _get_nonce_client().set(key, "1", nx=True, ex=_NONCE_TTL_S)
    except Exception:  # noqa: BLE001 — Redis indisponible : fail-open (DC2 : log)
        logger.warning("[Icypeas webhook] nonce Redis indisponible -> fail-open (anti-rejeu degrade)")
        return False
    # set(nx=True) : True si la cle a ete posee (1re vue), None si deja presente (rejeu).
    return not stored


def _timestamp_fresh(ts: str) -> bool:
    """True si le timestamp (ISO) est a +/- _MAX_TIMESTAMP_SKEW_S de maintenant."""
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return abs((datetime.now(UTC) - t).total_seconds()) <= _MAX_TIMESTAMP_SKEW_S


async def _read_bounded_body(request: Request) -> bytes:
    """Lit le corps en abandonnant des que _MAX_BODY_BYTES est depasse (413)."""
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > _MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="Payload trop volumineux")
    return body


@router.post("/webhook", status_code=200)
async def icypeas_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Recoit le callback bulkDone Icypeas ({signature, timestamp, data})."""
    # #9 : sans verification de signature en PROD, l'endpoint serait un injecteur
    # de contacts non authentifie -> refuser plutot que traiter (fail-safe).
    if not settings.icypeas_webhook_verify and settings.is_production:
        logger.error("[Icypeas webhook] verification HMAC desactivee en PROD -> refuse")
        raise HTTPException(status_code=503, detail="Webhook non securise")

    raw = await _read_bounded_body(request)
    try:
        payload = json.loads(raw)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Payload invalide")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload invalide")

    if settings.icypeas_webhook_verify:
        timestamp = payload.get("timestamp", "")
        # Anti-rejeu (#2) : refuser un timestamp trop ancien/futur (borne le rejeu).
        if not _timestamp_fresh(timestamp):
            logger.warning("[Icypeas webhook] timestamp hors fenetre (rejeu ?)")
            raise HTTPException(status_code=401, detail="Timestamp invalide")
        # Path signe = celui de NOTRE URL webhook (configuree), sinon le path recu.
        path = urlparse(settings.icypeas_webhook_url).path if settings.icypeas_webhook_url else request.url.path
        signature = payload.get("signature", "")
        if not verify_webhook_signature(
            settings.icypeas_api_secret or "", path,
            timestamp, signature,
        ):
            logger.warning("[Icypeas webhook] signature invalide")
            raise HTTPException(status_code=401, detail="Signature invalide")
        # Anti-rejeu single-use (FIX #12) : une signature valide capturee ne peut
        # etre rejouee (avec un `data` forge) dans la fenetre de fraicheur.
        if await _mark_nonce_or_replay(timestamp, signature):
            logger.warning("[Icypeas webhook] rejeu detecte (nonce deja vu)")
            raise HTTPException(status_code=401, detail="Rejeu détecté")

    result = await process_bulk_callback(db, payload.get("data") or {})
    return {"received": True, **result}
