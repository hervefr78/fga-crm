# =============================================================================
# FGA CRM - Trends Cache (Redis) + hash de requete
# =============================================================================
"""Cache court du payload normalise d'un rapport + calcul du request_hash.

- request_hash : empreinte stable des parametres d'un rapport. Sert a la
  deduplication des jobs (table trend_jobs) ET a la cle de cache Redis.
- cache Redis : evite de rappeler le fournisseur pour une requete identique
  recente (maitrise du cout — cf. doc 02).

Client Redis cree A LA VOLEE a chaque operation (pas de singleton) : l'orchestrateur
tourne aussi bien dans la boucle asyncio FastAPI que dans un `asyncio.run` de task
Celery (nouvelle boucle a chaque fois). Un singleton async se lierait a la 1re
boucle et casserait dans les suivantes (RuntimeError loop — cf. sync_status.py).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os

import redis.asyncio as redis_async

from app.config import settings

logger = logging.getLogger(__name__)

_CACHE_PREFIX = "trends:report:"


def _redis_url() -> str:
    return os.getenv("REDIS_URL", settings.redis_url)


def compute_request_hash(
    *,
    mode: str,
    category_id: str,
    country: str,
    language: str,
    timeframe: str,
    seed_terms: list[str],
) -> str:
    """Empreinte deterministe des parametres d'un rapport.

    L'ordre des seeds est SIGNIFICATIF : le provider les consomme dans l'ordre saisi
    (mock -> seeds[0] comme terme d'habillage ; DataForSEO -> ordre des keywords).
    On ne trie donc PAS les seeds dans le hash — sinon deux ordres differents
    partageraient la meme cle de dedup/cache tout en produisant des rapports differents.
    """
    canonical = json.dumps(
        {
            "mode": mode,
            "category_id": category_id,
            "country": country,
            "language": language,
            "timeframe": timeframe,
            "seed_terms": seed_terms,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


async def get_cached_report(request_hash: str) -> dict | None:
    """Lire un rapport en cache. None si absent ou illisible."""
    client = redis_async.from_url(_redis_url(), decode_responses=True)
    try:
        raw = await client.get(f"{_CACHE_PREFIX}{request_hash}")
    except Exception as exc:  # noqa: BLE001 — cache best-effort, ne bloque pas
        logger.warning("[TrendsCache] lecture echouee : %s", exc)
        return None
    finally:
        await client.aclose()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[TrendsCache] payload illisible, ignore")
        return None


async def set_cached_report(request_hash: str, payload: dict, ttl_seconds: int) -> None:
    """Ecrire un rapport en cache avec TTL. Best-effort (n'echoue jamais l'appelant)."""
    client = redis_async.from_url(_redis_url(), decode_responses=True)
    try:
        await client.set(
            f"{_CACHE_PREFIX}{request_hash}", json.dumps(payload), ex=ttl_seconds
        )
    except Exception as exc:  # noqa: BLE001 — cache best-effort
        logger.warning("[TrendsCache] ecriture echouee : %s", exc)
    finally:
        await client.aclose()
