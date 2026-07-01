"""Tests du SerpApiProvider (HTTP mocke sur la structure reelle validee en live)."""

from __future__ import annotations

import httpx
import pytest

from app.services.trends.provider import PROVIDER_SERPAPI, get_trends_provider
from app.services.trends.serpapi_provider import SerpApiProvider, _safe_err

# Fixtures calquees sur la reponse reelle serpapi.com google_trends (2026-07-01).
_TIMESERIES = {
    "interest_over_time": {
        "timeline_data": [
            {"date": "Jun 29 - Jul 5, 2025", "timestamp": "1751155200",
             "values": [{"query": "x", "value": "61", "extracted_value": 61}]},
        ]
    }
}
_RELATED = {
    "related_queries": {
        "top": [{"query": "le marketing digital", "value": "100", "extracted_value": 100}],
        "rising": [
            {"query": "metiersdart", "value": "Breakout", "extracted_value": 19900},
            {"query": "growth", "value": "+120%", "extracted_value": 120},
        ],
    }
}
_GEO = {"interest_by_region": [
    {"geo": "FR-L", "location": "Limousin", "value": "100", "extracted_value": 100},
    {"geo": "FR-A", "location": "Alsace", "value": "40", "extracted_value": 40},
]}


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> SerpApiProvider:
    from app.services.trends import serpapi_provider as mod
    monkeypatch.setattr(mod.settings, "serpapi_key", "test_key")
    return SerpApiProvider()


async def test_factory_prefers_serpapi_over_searchapi(monkeypatch: pytest.MonkeyPatch):
    from app.services.trends import provider as pmod
    monkeypatch.setattr(pmod.settings, "dataforseo_login", None)
    monkeypatch.setattr(pmod.settings, "dataforseo_password", None)
    monkeypatch.setattr(pmod.settings, "serpapi_key", "k")
    monkeypatch.setattr(pmod.settings, "searchapi_key", "other")  # serpapi doit gagner
    assert get_trends_provider().name == PROVIDER_SERPAPI


async def test_timeseries_mapping(provider: SerpApiProvider, monkeypatch: pytest.MonkeyPatch):
    async def _fake_get(_path, params=None):
        return _TIMESERIES
    monkeypatch.setattr(provider, "_get", _fake_get)
    pts = await provider.fetch_category_timeseries(
        category="marketing-digital", country="FR", language="fr", timeframe="today 12-m",
    )
    assert len(pts) == 1 and pts[0].value == 61 and pts[0].date == "2025-06-29"


async def test_related_queries_breakout(provider: SerpApiProvider, monkeypatch: pytest.MonkeyPatch):
    async def _fake_get(_path, params=None):
        return _RELATED
    monkeypatch.setattr(provider, "_get", _fake_get)
    rq = await provider.fetch_related_queries(
        category="x", country="FR", language="fr", timeframe="today 12-m",
    )
    assert rq.top[0].value == 100
    assert rq.rising[0].breakout is True and rq.rising[0].growth == 19900.0
    assert rq.rising[1].breakout is False and rq.rising[1].growth == 120.0


async def test_regions_sorted(provider: SerpApiProvider, monkeypatch: pytest.MonkeyPatch):
    async def _fake_get(_path, params=None):
        return _GEO
    monkeypatch.setattr(provider, "_get", _fake_get)
    regions = await provider.fetch_region_breakdown(
        category="x", country="FR", language="fr", timeframe="today 12-m",
    )
    assert [r.region for r in regions] == ["Limousin", "Alsace"]
    assert regions[0].value == 100


def test_safe_err_never_leaks_url():
    # Une HTTPStatusError contient une URL avec api_key -> _safe_err ne doit
    # retourner que le status, jamais l'URL.
    req = httpx.Request("GET", "https://serpapi.com/search?api_key=SECRET123")
    resp = httpx.Response(401, request=req)
    err = httpx.HTTPStatusError("boom", request=req, response=resp)
    msg = _safe_err(err)
    assert "SECRET123" not in msg
    assert msg == "HTTP 401"
    assert _safe_err(None) == "inconnu"


async def test_missing_key_raises(monkeypatch: pytest.MonkeyPatch):
    from app.services.trends import serpapi_provider as mod
    from app.services.trends.provider import TrendsProviderError
    monkeypatch.setattr(mod.settings, "serpapi_key", None)
    with pytest.raises(TrendsProviderError):
        SerpApiProvider()
