"""Tests P2 : adapters mock deterministes, waterfall, CreditLedger."""

from __future__ import annotations

from app.services.enrichment.adapters.mock import (
    MockCompanySource,
    MockEmailFinder,
    MockEmailVerifier,
    MockPeopleSource,
)
from app.services.enrichment.credit_ledger import CreditLedger
from app.services.enrichment.ports import Company, IcpFilter, PersonCandidate
from app.services.enrichment.waterfall import WaterfallStep, waterfall

# --- Mock adapters ---

async def test_mock_company_source_deterministic():
    src = MockCompanySource()
    a = await src.get_companies(IcpFilter(naf_codes=["5829C"], limit=3))
    b = await src.get_companies(IcpFilter(naf_codes=["5829C"], limit=3))
    assert len(a) == 3
    assert [c.siren for c in a] == [c.siren for c in b]
    assert all(c.domain for c in a)


async def test_mock_people_source_one_per_role():
    people = await MockPeopleSource().find_people(
        Company(siren="123", name="X", domain="x.fr"), ["CTO", "CPO", "CMO"],
    )
    assert len(people) == 3
    assert {p.title_raw for p in people}  # titres renseignes
    # deterministe
    again = await MockPeopleSource().find_people(
        Company(siren="123", name="X", domain="x.fr"), ["CTO", "CPO", "CMO"],
    )
    assert [p.last_name for p in people] == [p.last_name for p in again]


async def test_mock_email_finder_format_and_determinism():
    p = PersonCandidate(first_name="Julie", last_name="Martin", title_raw="CTO", source="mock")
    e1 = await MockEmailFinder().find(p, "acme.fr")
    e2 = await MockEmailFinder().find(p, "acme.fr")
    assert e1 is not None
    assert e1.email == "julie.martin@acme.fr"
    assert 0.6 <= e1.confidence <= 0.99
    assert e1.confidence == e2.confidence


async def test_mock_verifier_statuses():
    v = await MockEmailVerifier().verify("julie.martin@acme.fr")
    assert v.status in {"valid", "catch_all", "risky", "invalid"}


# --- CreditLedger ---

def test_credit_ledger_budget_guard():
    led = CreditLedger(max_per_run=3)
    assert led.can_spend(2) is True
    led.record("op1", 2)
    assert led.spent_this_run() == 2.0
    assert led.can_spend(2) is False   # 2+2 > 3
    assert led.can_spend(1) is True


# --- Waterfall ---

async def test_waterfall_cheapest_first():
    async def expensive():
        return "EXP"

    async def cheap():
        return "CHEAP"

    led = CreditLedger(max_per_run=100)
    res = await waterfall([
        WaterfallStep("expensive", 5, expensive),
        WaterfallStep("cheap", 1, cheap),
    ], led)
    assert res.result == "CHEAP" and res.used == "cheap"
    assert led.spent_this_run() == 1.0


async def test_waterfall_stops_on_first_success():
    async def none_step():
        return None

    async def hit_step():
        return "Z"

    led = CreditLedger(max_per_run=100)
    res = await waterfall([
        WaterfallStep("a", 1, none_step),
        WaterfallStep("b", 2, hit_step),
    ], led)
    assert res.result == "Z" and res.used == "b"


async def test_waterfall_respects_budget():
    async def hit():
        return "X"

    led = CreditLedger(max_per_run=0)  # aucun budget
    res = await waterfall([WaterfallStep("a", 1, hit)], led)
    assert res.result is None
