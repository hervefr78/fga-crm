"""Tests du SearchApiProvider (HTTP mocke sur la structure reelle validee en live)."""

from __future__ import annotations

import pytest

from app.services.trends.provider import PROVIDER_SEARCHAPI, get_trends_provider
from app.services.trends.searchapi_provider import SearchApiProvider

# Fixtures calquees sur la reponse reelle SearchApi.io google_trends (2026-07-01).
_TIMESERIES = {
    "interest_over_time": {
        "timeline_data": [
            {"date": "Jun 29 - Jul 5, 2025", "timestamp": "1751155200",
             "values": [{"query": "x", "value": "60", "extracted_value": 60}]},
            {"date": "Jul 6 - Jul 12, 2025", "timestamp": "1751760000",
             "values": [{"query": "x", "value": "72", "extracted_value": 72}]},
        ]
    }
}
_RELATED = {
    "related_queries": {
        "top": [
            {"position": 1, "query": "le marketing digital", "values": "100", "extracted_value": 100},
            {"position": 2, "query": "agence marketing", "values": "80", "extracted_value": 80},
        ],
        "rising": [
            {"position": 1, "query": "lidl near me", "values": "Breakout", "extracted_value": 20900},
            {"position": 2, "query": "growth hacking", "values": "+150%", "extracted_value": 150},
        ],
    }
}


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> SearchApiProvider:
    from app.services.trends import searchapi_provider as mod
    monkeypatch.setattr(mod.settings, "searchapi_key", "test_key")
    return SearchApiProvider()


async def test_factory_selects_searchapi(monkeypatch: pytest.MonkeyPatch):
    from app.services.trends import provider as pmod
    monkeypatch.setattr(pmod.settings, "dataforseo_login", None)
    monkeypatch.setattr(pmod.settings, "dataforseo_password", None)
    monkeypatch.setattr(pmod.settings, "searchapi_key", "k")
    assert get_trends_provider().name == PROVIDER_SEARCHAPI


async def test_timeseries_mapping(provider: SearchApiProvider, monkeypatch: pytest.MonkeyPatch):
    async def _fake_get(_path, params=None):
        return _TIMESERIES
    monkeypatch.setattr(provider, "_get", _fake_get)
    pts = await provider.fetch_category_timeseries(
        category="marketing-digital", country="FR", language="fr", timeframe="today 12-m",
    )
    assert len(pts) == 2
    assert pts[0].value == 60 and pts[1].value == 72
    # timestamp unix -> date ISO
    assert pts[0].date == "2025-06-29"


async def test_related_queries_breakout(provider: SearchApiProvider, monkeypatch: pytest.MonkeyPatch):
    async def _fake_get(_path, params=None):
        return _RELATED
    monkeypatch.setattr(provider, "_get", _fake_get)
    rq = await provider.fetch_related_queries(
        category="x", country="FR", language="fr", timeframe="today 12-m",
    )
    assert len(rq.top) == 2 and rq.top[0].value == 100
    assert len(rq.rising) == 2
    # "Breakout" -> breakout=True ; croissance = extracted_value
    assert rq.rising[0].breakout is True
    assert rq.rising[0].growth == 20900.0
    assert rq.rising[1].breakout is False
    assert rq.rising[1].growth == 150.0


async def test_regions_empty_on_error(provider: SearchApiProvider, monkeypatch: pytest.MonkeyPatch):
    async def _fake_get(_path, params=None):
        return {"error": "no geo data"}  # cas GEO_MAP en erreur
    monkeypatch.setattr(provider, "_get", _fake_get)
    regions = await provider.fetch_region_breakdown(
        category="x", country="FR", language="fr", timeframe="today 12-m",
    )
    assert regions == []


async def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch):
    from app.services.trends import searchapi_provider as mod
    from app.services.trends.provider import TrendsProviderError
    monkeypatch.setattr(mod.settings, "searchapi_key", None)
    with pytest.raises(TrendsProviderError):
        SearchApiProvider()
