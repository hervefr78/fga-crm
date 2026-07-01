# =============================================================================
# FGA CRM - Tests unitaires du pricing API Anthropic
# =============================================================================
"""Couverture pricing.cost_eur :
- Haiku / Sonnet / Opus : tarifs input/output corrects
- cache read (x0.1) / cache write (x1.25)
- modele inconnu -> 0.0 sans crash (+ WARNING logge)
- suffixes de version (matching par prefixe de famille)
- edge cases : tokens=0, gros volumes
"""

import logging

from app.config import settings
from app.core.pricing import (
    CACHE_READ_MULTIPLIER,
    CACHE_WRITE_MULTIPLIER,
    TOKENS_PER_MILLION,
    cost_eur,
)

EUR = settings.eur_usd


# ---------------------------------------------------------------------------
# Tarifs de base par famille
# ---------------------------------------------------------------------------

class TestBaseRates:
    def test_haiku_input_output(self):
        # 1M input @1$ + 1M output @5$ = 6$ -> x EUR
        cost = cost_eur("claude-haiku-4-5-20251001", 1_000_000, 1_000_000, 0, 0)
        assert cost == (1.0 + 5.0) * EUR

    def test_sonnet_input_output(self):
        # 1M input @3$ + 1M output @15$ = 18$ -> x EUR
        cost = cost_eur("claude-sonnet-4-20250514", 1_000_000, 1_000_000, 0, 0)
        assert cost == (3.0 + 15.0) * EUR

    def test_opus_input_output(self):
        # 1M input @5$ + 1M output @25$ = 30$ -> x EUR
        cost = cost_eur("claude-opus-4-20250101", 1_000_000, 1_000_000, 0, 0)
        assert cost == (5.0 + 25.0) * EUR

    def test_input_only(self):
        cost = cost_eur("claude-haiku-4-5", 500_000, 0, 0, 0)
        assert cost == (500_000 * 1.0 / TOKENS_PER_MILLION) * EUR

    def test_output_only(self):
        cost = cost_eur("claude-sonnet-4", 0, 200_000, 0, 0)
        assert cost == (200_000 * 15.0 / TOKENS_PER_MILLION) * EUR


# ---------------------------------------------------------------------------
# Cache read / write
# ---------------------------------------------------------------------------

class TestCache:
    def test_cache_read_multiplier(self):
        # cache_read tarife a input x 0.1 -> Haiku : 0.1$/Mtok
        cost = cost_eur("claude-haiku-4-5", 0, 0, 1_000_000, 0)
        expected = (1.0 * CACHE_READ_MULTIPLIER) * EUR
        assert cost == expected

    def test_cache_write_multiplier(self):
        # cache_write tarife a input x 1.25 -> Haiku : 1.25$/Mtok
        cost = cost_eur("claude-haiku-4-5", 0, 0, 0, 1_000_000)
        expected = (1.0 * CACHE_WRITE_MULTIPLIER) * EUR
        assert cost == expected

    def test_cache_write_opus(self):
        # Opus input=5$ -> cache_write = 6.25$/Mtok
        cost = cost_eur("claude-opus-4", 0, 0, 0, 1_000_000)
        assert cost == (5.0 * 1.25) * EUR

    def test_all_dimensions_combined(self):
        # Sonnet : in=3, out=15, cr=0.3, cw=3.75 ($/Mtok)
        cost = cost_eur("claude-sonnet-4", 1_000_000, 1_000_000, 1_000_000, 1_000_000)
        expected = (3.0 + 15.0 + 0.3 + 3.75) * EUR
        assert abs(cost - expected) < 1e-9


# ---------------------------------------------------------------------------
# Modele inconnu (DC2 — 0.0 + warning, pas de crash)
# ---------------------------------------------------------------------------

class TestUnknownModel:
    def test_unknown_model_returns_zero(self):
        assert cost_eur("gpt-4o", 1_000_000, 1_000_000, 0, 0) == 0.0

    def test_unknown_model_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING):
            cost_eur("mistral-large", 1000, 1000, 0, 0)
        assert any("modele inconnu" in r.message for r in caplog.records)

    def test_empty_model_returns_zero(self):
        assert cost_eur("", 1000, 1000, 0, 0) == 0.0

    def test_none_like_prefix_not_matched(self):
        # "claude" seul sans famille reconnue -> inconnu
        assert cost_eur("claude", 1000, 1000, 0, 0) == 0.0


# ---------------------------------------------------------------------------
# Robustesse du matching (suffixes de version)
# ---------------------------------------------------------------------------

class TestVersionSuffixes:
    def test_haiku_various_suffixes(self):
        for model in (
            "claude-haiku-4-5",
            "claude-haiku-4-5-20251001",
            "claude-haiku-3-5-20241022",
        ):
            assert cost_eur(model, 1_000_000, 0, 0, 0) == (1.0 * EUR)

    def test_case_insensitive(self):
        assert cost_eur("CLAUDE-SONNET-4-20250514", 1_000_000, 0, 0, 0) == (3.0 * EUR)

    def test_whitespace_trimmed(self):
        assert cost_eur("  claude-opus-4  ", 1_000_000, 0, 0, 0) == (5.0 * EUR)


# ---------------------------------------------------------------------------
# Edge cases (DC11)
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_all_zero_tokens(self):
        assert cost_eur("claude-haiku-4-5", 0, 0, 0, 0) == 0.0

    def test_large_volume_no_overflow(self):
        # 10 milliards de tokens input Haiku = 10_000$ -> x EUR, pas d'overflow
        cost = cost_eur("claude-haiku-4-5", 10_000_000_000, 0, 0, 0)
        assert cost == (10_000_000_000 * 1.0 / TOKENS_PER_MILLION) * EUR
        assert cost > 0
