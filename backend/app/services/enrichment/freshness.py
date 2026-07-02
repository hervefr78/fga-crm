# =============================================================================
# FGA CRM - Enrichissement : cache de fraicheur (idempotence)
# =============================================================================
"""TTL de fraicheur (spec §13) : evite de re-depenser un credit si une donnee a
ete enrichie recemment. Clefs : person:{org}:{siren}:{name}.

Redis. Par defaut client par appel (safe across-loops Celery : chaque task tourne
dans sa propre event loop via asyncio.run). Pour la boucle chaude d'un job, passer
un `client` reutilisable ouvert via `client_scope()` DANS la meme loop (fix #13 :
evite d'ouvrir/fermer une connexion par personne)."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as redis_async

from app.config import settings

logger = logging.getLogger(__name__)

_PREFIX = "enrichment:fresh:"


def _redis_url() -> str:
    return os.getenv("REDIS_URL", settings.redis_url)


def person_key(org_id: object, siren: str | None, first_name: str, last_name: str) -> str:
    """Clef de fraicheur scopee org + siren + nom. PARTAGEE inline & bulk (DC8) :
    une personne enrichie via bulk doit etre vue fraiche par un run inline ulterieur."""
    org = org_id or "default"
    return f"person:{org}:{siren}:{first_name}.{last_name}".lower()


@asynccontextmanager
async def client_scope() -> AsyncIterator[redis_async.Redis]:
    """Client Redis reutilisable le temps d'un job (a utiliser dans UNE event loop).
    Evite le churn de connexions dans la boucle chaude (is_fresh/touch par personne)."""
    client = redis_async.from_url(_redis_url(), decode_responses=True)
    try:
        yield client
    finally:
        await client.aclose()


async def is_fresh(key: str, *, client: redis_async.Redis | None = None) -> bool:
    """True si la clef existe encore (donnee fraiche). Fail-open -> False (re-enrichit)."""
    own = client is None
    c = client or redis_async.from_url(_redis_url(), decode_responses=True)
    try:
        return bool(await c.exists(f"{_PREFIX}{key}"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Enrichment] freshness lecture KO : %s", exc)
        return False
    finally:
        if own:
            await c.aclose()


async def touch(key: str, ttl_days: int, *, client: redis_async.Redis | None = None) -> None:
    """Marque la clef fraiche pour ttl_days. Best-effort."""
    own = client is None
    c = client or redis_async.from_url(_redis_url(), decode_responses=True)
    try:
        await c.set(f"{_PREFIX}{key}", "1", ex=max(1, ttl_days) * 86400)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Enrichment] freshness ecriture KO : %s", exc)
    finally:
        if own:
            await c.aclose()
