"""Tests du provider Trends (mock deterministe + factory)."""

from __future__ import annotations

from app.services.trends.mock_provider import MockProvider
from app.services.trends.provider import (
    PROVIDER_MOCK,
    RelatedQueries,
    get_trends_provider,
)

_KW = {"category": "marketing-digital", "country": "FR", "language": "fr", "timeframe": "today 12-m"}


def test_factory_returns_mock_without_key():
    # En test, aucune cle DataForSEO -> provider mock.
    assert get_trends_provider().name == PROVIDER_MOCK


async def test_mock_list_categories_non_empty():
    provider = MockProvider()
    cats = await provider.list_categories()
    assert len(cats) >= 1
    assert all(c.slug and c.label for c in cats)


async def test_mock_timeseries_deterministic():
    provider = MockProvider()
    a = await provider.fetch_category_timeseries(**_KW)
    b = await provider.fetch_category_timeseries(**_KW)
    assert [p.value for p in a] == [p.value for p in b]
    # Bornes respectees (indice 0-100)
    assert all(0 <= p.value <= 100 for p in a)


async def test_mock_timeseries_length_varies_by_timeframe():
    provider = MockProvider()
    short = await provider.fetch_category_timeseries(
        category="x", country="FR", language="fr", timeframe="now 7-d"
    )
    long = await provider.fetch_category_timeseries(
        category="x", country="FR", language="fr", timeframe="today 12-m"
    )
    assert len(short) < len(long)


async def test_mock_related_queries_shape():
    provider = MockProvider()
    rq: RelatedQueries = await provider.fetch_related_queries(**_KW, seed_terms=["prospection"])
    assert rq.top and rq.rising
    # Les rising portent une croissance ; certains peuvent etre breakout.
    assert all(q.growth is not None for q in rq.rising)


async def test_mock_regions_sorted_desc():
    provider = MockProvider()
    regions = await provider.fetch_region_breakdown(**_KW)
    values = [r.value for r in regions]
    assert values == sorted(values, reverse=True)


async def test_mock_healthcheck_ok():
    provider = MockProvider()
    h = await provider.healthcheck()
    assert h.provider == PROVIDER_MOCK
    assert h.status == "ok"


async def test_mock_different_seed_changes_data():
    provider = MockProvider()
    a = await provider.fetch_category_timeseries(**_KW, seed_terms=["a"])
    b = await provider.fetch_category_timeseries(**_KW, seed_terms=["b"])
    # Des seeds differents produisent des series differentes (seed du hash).
    assert [p.value for p in a] != [p.value for p in b]
