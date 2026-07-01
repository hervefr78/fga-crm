# =============================================================================
# FGA CRM - Pricing API Anthropic (calcul du cout token en EUR)
# =============================================================================
"""Tarifs Anthropic en USD / M tokens (a maintenir — cf. SHARED_ERRORS
« prix LLM hardcode obsolete »).

Le cout est calcule A LA LECTURE depuis les tokens bruts stockes : une
correction de tarif ici recalcule tout l'historique.

Matching robuste par prefixe de famille (« claude-haiku », « claude-sonnet »,
« claude-opus ») pour survivre aux suffixes de version (ex.
`claude-haiku-4-5-20251001`). Modele inconnu -> cout 0.0 + WARNING (DC2 :
pas de cout fantome silencieux).
"""

import logging

from app.config import settings

logger = logging.getLogger(__name__)

# Diviseur : les tarifs sont exprimes par MILLION de tokens.
TOKENS_PER_MILLION = 1_000_000

# Multiplicateurs cache (rapportes au tarif input du modele).
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25

# Tarifs input/output en USD / M tokens, par famille de modele.
# cache_read et cache_write sont derives de l'input (0.1x / 1.25x).
# Cle = prefixe de famille (matching par startswith apres normalisation).
MODEL_RATES_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-haiku": {"input": 1.0, "output": 5.0},
    "claude-sonnet": {"input": 3.0, "output": 15.0},
    "claude-opus": {"input": 5.0, "output": 25.0},
}


def _resolve_rates(model: str) -> dict[str, float] | None:
    """Retrouver les tarifs input/output pour un nom de modele.

    Matching par prefixe de famille : `claude-haiku-4-5-20251001` -> Haiku.
    Retourne None si aucune famille ne correspond (modele inconnu).
    """
    if not model:
        return None
    normalized = model.strip().lower()
    for prefix, rates in MODEL_RATES_USD_PER_MTOK.items():
        if normalized.startswith(prefix):
            return rates
    return None


def cost_eur(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
) -> float:
    """Calculer le cout en EUR pour une conso de tokens sur un modele donne.

    Formule (USD puis conversion EUR) :
        cout_usd = (in x r_in + out x r_out
                    + cache_read x r_in x 0.1
                    + cache_write x r_in x 1.25) / 1e6
        cout_eur = cout_usd x EUR_USD

    Modele inconnu -> 0.0 + WARNING (DC2 : jamais de cout fantome silencieux).
    """
    rates = _resolve_rates(model)
    if rates is None:
        logger.warning(
            "[pricing] modele inconnu '%s' — cout force a 0.0 (tarif a ajouter "
            "dans MODEL_RATES_USD_PER_MTOK)",
            model,
        )
        return 0.0

    rate_in = rates["input"]
    rate_out = rates["output"]
    rate_cache_read = rate_in * CACHE_READ_MULTIPLIER
    rate_cache_write = rate_in * CACHE_WRITE_MULTIPLIER

    cost_usd = (
        input_tokens * rate_in
        + output_tokens * rate_out
        + cache_read_tokens * rate_cache_read
        + cache_write_tokens * rate_cache_write
    ) / TOKENS_PER_MILLION

    return cost_usd * settings.eur_usd
