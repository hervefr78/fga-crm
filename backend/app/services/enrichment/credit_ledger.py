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
        total = await client.incrby(key, credits)
        if total == credits:  # premiere reservation du jour -> pose le TTL
            await client.expire(key, _QUOTA_TTL)
        return total <= settings.enrichment_daily_quota
    except Exception as exc:  # noqa: BLE001 — fail-open sur panne Redis
        logger.warning("[Enrichment] quota Redis indisponible : %s", exc)
        return True
    finally:
        await client.aclose()
