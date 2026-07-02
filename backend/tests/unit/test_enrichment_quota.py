"""Tests C3 (bug hunt) : plafond credits/run respecte par resultat (#6) et
comportement fail-open (dev) / fail-closed (prod) du quota Redis (#12)."""

from __future__ import annotations

import pytest

from app.config import settings
from app.services.enrichment import credit_ledger
from app.services.enrichment.credit_ledger import CreditLedger, reserve_daily_credits
from app.services.enrichment.orchestrator import _source_people
from app.services.enrichment.ports import Company, PersonCandidate


class _BigPeopleSource:
    """Renvoie 25 leads (comme IcypeasPeopleSource._SIZE) pour un seul can_spend."""
    name = "big"
    cost_per_result = 1.0

    async def find_people(self, company, roles):
        return [
            PersonCandidate(first_name=f"P{i}", last_name="X", title_raw="CTO", source="big")
            for i in range(25)
        ]


@pytest.mark.asyncio
async def test_source_people_respects_run_budget(db_session):
    # #6 : budget=3 mais le provider renvoie 25 -> on ne debite/garde que 3
    ledger = CreditLedger(max_per_run=3)
    stats = {"companies": 0, "people_found": 0, "suppressed": 0}
    company = Company(siren="123", name="Acme", domain="acme.fr")

    _, people = await _source_people(
        db_session, company=company, company_src=None, people_srcs=[_BigPeopleSource()],
        ledger=ledger, org_id=None, stats=stats,
    )

    assert ledger.spent_this_run() == 3.0  # plafond respecte (pas 25)
    assert len(people) == 3


class _FakeDownRedis:
    async def eval(self, *a, **k):
        raise ConnectionError("redis down")

    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_reserve_daily_credits_fail_open_in_dev(monkeypatch):
    # #12 : Redis KO en dev -> fail-open (ne bloque pas le local)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(credit_ledger.redis_async, "from_url", lambda *a, **k: _FakeDownRedis())
    assert await reserve_daily_credits("org-x", 10) is True


@pytest.mark.asyncio
async def test_reserve_daily_credits_fail_closed_in_prod(monkeypatch):
    # #12 : Redis KO en prod -> fail-CLOSED (le quota est la seule barriere de cout)
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(credit_ledger.redis_async, "from_url", lambda *a, **k: _FakeDownRedis())
    assert await reserve_daily_credits("org-x", 10) is False
