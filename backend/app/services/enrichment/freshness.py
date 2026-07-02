# =============================================================================
# FGA CRM - Enrichissement : cache de fraicheur (idempotence)
# =============================================================================
"""TTL de fraicheur (spec §13) : evite de re-depenser un credit si une donnee a
ete enrichie recemment. Clefs : person:{siren}:{name}, company_people:{siren}.
Redis, client par appel (safe across-loops Celery), fail-open."""

from __future__ import annotations

import logging
import os

import redis.asyncio as redis_async

from app.config import settings

logger = logging.getLogger(__name__)

_PREFIX = "enrichment:fresh:"


def _redis_url() -> str:
    return os.getenv("REDIS_URL", settings.redis_url)


async def is_fresh(key: str) -> bool:
    """True si la clef existe encore (donnee fraiche). Fail-open -> False (re-enrichit)."""
    client = redis_async.from_url(_redis_url(), decode_responses=True)
    try:
        return bool(await client.exists(f"{_PREFIX}{key}"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Enrichment] freshness lecture KO : %s", exc)
        return False
    finally:
        await client.aclose()


async def touch(key: str, ttl_days: int) -> None:
    """Marque la clef fraiche pour ttl_days. Best-effort."""
    client = redis_async.from_url(_redis_url(), decode_responses=True)
    try:
        await client.set(f"{_PREFIX}{key}", "1", ex=max(1, ttl_days) * 86400)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Enrichment] freshness ecriture KO : %s", exc)
    finally:
        await client.aclose()
