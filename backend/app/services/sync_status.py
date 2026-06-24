# =============================================================================
# FGA CRM - Statut partage de la full sync Startup Radar (via Redis)
# =============================================================================
"""Statut + verrou single-flight de la synchronisation complete SR -> CRM.

POURQUOI Redis et pas un global memoire :
La prod tourne avec `uvicorn --workers 2` (2 process) + un process Celery worker
separe. Un global Python n'est visible que dans le process qui l'ecrit : la task
Celery ecrirait le resultat dans SA memoire, invisible des workers uvicorn qui
servent `GET /status`. Le statut DOIT donc etre dans un store partage (Redis,
deja present comme broker Celery).

Deux faces :
- Cote FastAPI (boucle asyncio longue et unique) : client async singleton.
- Cote Celery task (`asyncio.run` par task -> nouvelle boucle a chaque fois) :
  client SYNC cree a la volee. Reutiliser un client async entre plusieurs
  boucles declenche `RuntimeError: Future attached to a different loop`.
"""

import json
import logging
import os

import redis as redis_sync
import redis.asyncio as redis_async

from app.config import settings

logger = logging.getLogger(__name__)

# Cles Redis
STATUS_KEY = "sr:full_sync:status"
LOCK_KEY = "sr:full_sync:lock"

# Borne haute d'une full sync. Le verrou auto-expire apres ce delai pour ne
# jamais rester bloque si la task meurt sans liberer (DC2 — pas de blocage muet).
LOCK_TTL_SECONDS = 3600  # 1h

# TTL du statut lui-meme : evite qu'un vieux statut (running zombie ou terminal)
# ne traine indefiniment dans Redis. Plus long que LOCK_TTL pour garder le
# dernier resultat consultable bien apres la fin de la sync.
STATUS_TTL_SECONDS = 86400  # 24h

# Liberation atomique du verrou : ne supprime QUE si la valeur == job_id appelant
# (DC4). Empeche une task de liberer le verrou d'une AUTRE sync (cas du verrou
# qui a expire via TTL puis ete re-acquis par un nouveau job).
_RELEASE_LOCK_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
else
    return 0
end
"""

# Etats du job (DC5 — etats exhaustifs)
STATUS_IDLE = "idle"
STATUS_RUNNING = "running"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

# Borne sur le message d'erreur stocke (DC1)
_MAX_ERROR_LEN = 2000

_async_client: redis_async.Redis | None = None


def _redis_url() -> str:
    """URL Redis — meme resolution que Celery (REDIS_URL) avec fallback settings."""
    return os.getenv("REDIS_URL", settings.redis_url)


def build_status(
    *,
    job_id: str,
    status: str,
    started_at: str,
    finished_at: str | None = None,
    result: dict | None = None,
    error: str | None = None,
) -> dict:
    """Construit le payload de statut stocke dans Redis (format unique)."""
    return {
        "job_id": job_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "result": result,
        "error": (error[:_MAX_ERROR_LEN] if error else None),
    }


# ---------------------------------------------------------------------------
# Cote FastAPI (async)
# ---------------------------------------------------------------------------


def _get_async_client() -> redis_async.Redis:
    global _async_client
    if _async_client is None:
        _async_client = redis_async.from_url(_redis_url(), decode_responses=True)
    return _async_client


async def get_status() -> dict | None:
    """Lire le statut courant du full sync. None si aucun sync n'a jamais tourne."""
    raw = await _get_async_client().get(STATUS_KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[SyncStatus] payload Redis illisible, ignore")
        return None


async def set_status_async(payload: dict) -> None:
    """Ecrire le statut (cote FastAPI)."""
    await _get_async_client().set(STATUS_KEY, json.dumps(payload), ex=STATUS_TTL_SECONDS)


async def try_acquire_lock(job_id: str) -> bool:
    """Acquerir le verrou single-flight. False si une full sync tourne deja.

    SET NX EX atomique (DC4) : pas de race entre check et set.
    """
    acquired = await _get_async_client().set(
        LOCK_KEY, job_id, nx=True, ex=LOCK_TTL_SECONDS,
    )
    return bool(acquired)


async def is_locked() -> bool:
    """True si un verrou de full sync est actif (sert a detecter un job zombie :
    statut 'running' mais plus de verrou = worker mort)."""
    return bool(await _get_async_client().exists(LOCK_KEY))


async def release_lock_async(job_id: str) -> None:
    """Liberer le verrou SI on en est proprietaire (cote FastAPI, ex: echec d'enqueue)."""
    await _get_async_client().eval(_RELEASE_LOCK_LUA, 1, LOCK_KEY, job_id)


# ---------------------------------------------------------------------------
# Cote Celery task (sync, client a la volee — voir docstring module)
# ---------------------------------------------------------------------------


def set_status_sync(payload: dict) -> None:
    """Ecrire le statut depuis la task Celery (client sync ephemere)."""
    client = redis_sync.from_url(_redis_url(), decode_responses=True)
    try:
        client.set(STATUS_KEY, json.dumps(payload), ex=STATUS_TTL_SECONDS)
    finally:
        client.close()


def release_lock_sync(job_id: str) -> None:
    """Liberer le verrou SI on en est proprietaire, depuis la task Celery."""
    client = redis_sync.from_url(_redis_url(), decode_responses=True)
    try:
        client.eval(_RELEASE_LOCK_LUA, 1, LOCK_KEY, job_id)
    finally:
        client.close()
