# =============================================================================
# FGA CRM - Enrichissement : cascade waterfall (cout-croissant, stop-on-success)
# =============================================================================
"""Cascade generique reutilisable (spec §7) : essaie les providers du moins cher
au plus cher, s'arrete au 1er succes, respecte le budget (CreditLedger).
Sert au sourcing des personnes ET a un futur fallback d'email finders."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.services.enrichment.credit_ledger import CreditLedger


@dataclass
class WaterfallStep[T]:
    name: str
    cost: float
    call: Callable[[], Awaitable[T | None]]


@dataclass
class WaterfallResult[T]:
    result: T | None
    used: str | None = None


async def waterfall[T](
    steps: list[WaterfallStep[T]], ledger: CreditLedger
) -> WaterfallResult[T]:
    """Ordonne par cout croissant, s'arrete au 1er resultat non nul dans le budget."""
    for step in sorted(steps, key=lambda s: s.cost):
        if not ledger.can_spend(step.cost):
            break
        result = await step.call()
        if result:
            ledger.record(step.name, step.cost)
            return WaterfallResult(result=result, used=step.name)
    return WaterfallResult(result=None)
