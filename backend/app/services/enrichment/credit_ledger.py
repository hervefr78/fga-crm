# =============================================================================
# FGA CRM - Enrichissement : compteur de credits & quotas
# =============================================================================
"""Garde-fous de cout (spec §12) :
- CreditLedger : budget PAR RUN (en memoire, dans l'orchestrateur/waterfall).
- reserve_daily_credits : quota journalier PAR ORGANISATION (Redis, multi-tenant),
  fail-open si Redis KO (ne bloque jamais sur une panne cache).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime

import redis.asyncio as redis_async

from app.config import settings

logger = logging.getLogger(__name__)

_QUOTA_TTL = 86400  # 24h

# Reservation atomique du quota journalier (DC4 : check-then-incr en une operation).
# N'incremente QUE si la reservation tient sous le quota -> pas d'inflation du
# compteur sur refus (fix #4 : evite le lockout de l'org pour la journee).
# Retourne 1 (accorde) ou 0 (refuse).
_RESERVE_LUA = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local credits = tonumber(ARGV[1])
if current + credits > tonumber(ARGV[2]) then
  return 0
end
local total = redis.call('INCRBY', KEYS[1], credits)
if total == credits then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
end
return 1
"""


class CreditLedger:
    """Suivi du budget d'un run. can_spend() = garde-fou avant chaque depense."""

    def __init__(self, *, max_per_run: int) -> None:
        self.max_per_run = max_per_run
        self._spent = 0.0
        self.operations: list[tuple[str, float]] = []

    def can_spend(self, credits: float) -> bool:
        return (self._spent + credits) <= self.max_per_run

    def record(self, op: str, credits: float) -> None:
        self._spent += credits
        self.operations.append((op, credits))

    def spent_this_run(self) -> float:
        return round(self._spent, 3)


def _redis_url() -> str:
    return os.getenv("REDIS_URL", settings.redis_url)


async def reserve_daily_credits(organization_id: str | None, credits: int) -> bool:
    """Reserve `credits` sur le quota journalier de l'org. False si depasse.

    Compteur Redis `enrichment:credits:{org}:{yyyymmdd}`. Fail-open (Redis KO -> autorise).
    """
    org = organization_id or "default"
    day = datetime.now(UTC).strftime("%Y%m%d")
    key = f"enrichment:credits:{org}:{day}"
    client = redis_async.from_url(_redis_url(), decode_responses=True)
    try:
        # Atomique (#4) : n'incremente que si la reservation tient -> pas de lockout.
        granted = await client.eval(
            _RESERVE_LUA, 1, key, credits, settings.enrichment_daily_quota, _QUOTA_TTL
        )
        return bool(granted)
    except Exception as exc:  # noqa: BLE001
        # #12 : le quota est la SEULE barriere de cout avant le debit Icypeas reel.
        # En prod -> fail-CLOSED (refuse) plutot que risquer un cout non borne.
        # En dev -> fail-open (ne bloque pas le local). ERROR = observabilite.
        logger.error("[Enrichment] quota Redis indisponible : %s", exc)
        return not settings.is_production
    finally:
        await client.aclose()
