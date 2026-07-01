# =============================================================================
# FGA CRM - Trends SerpApiProvider (Google Trends via SerpApi.com)
# =============================================================================
"""Adapter Google Trends via SerpApi.com (serpapi.com — meme service que le
moteur GEO google_aio, meme cle `serpapi_key`).

Structure de reponse VALIDEE en live (2026-07-01) :
- TIMESERIES : interest_over_time.timeline_data[] -> {timestamp, values[{extracted_value}]}
- RELATED_QUERIES : related_queries.{top,rising}[] -> {query, extracted_value, value}
  (rising : value == "Breakout" -> breakout ; extracted_value = croissance %)
- GEO_MAP_0 : interest_by_region[] -> {location, extracted_value}

Securite : la cle transite en query param `api_key`. Les messages d'erreur ne
doivent JAMAIS exposer l'URL (qui contient la cle) -> _safe_err() redige.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx

from app.config import settings
from app.services.trends.provider import (
    PROVIDER_SERPAPI,
    CategoryItem,
    HealthResult,
    QueryItem,
    RegionItem,
    RelatedQueries,
    TimeseriesPoint,
    TopicItem,
    TrendsProvider,
    TrendsProviderError,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://serpapi.com"
_SEARCH_PATH = "/search"
_ACCOUNT_PATH = "/account"
_ENGINE = "google_trends"

_TIMEOUT = 30.0
_MAX_RETRIES = 2
_BACKOFF_BASE = 1.0

# Categories métier (libelles utilises comme requete `q`, pas la taxonomie Google
# Trends). Memes que le mock/SearchApi -> coherence UX quel que soit le provider.
_CATEGORIES: list[tuple[str, str]] = [
    ("conseil-strategie", "Conseil & Strategie"),
    ("croissance-vente", "Croissance & Vente"),
    ("marketing-digital", "Marketing Digital"),
    ("intelligence-artificielle", "Intelligence Artificielle"),
    ("saas-logiciel", "SaaS & Logiciel"),
    ("finance-levee", "Finance & Levee de fonds"),
    ("rh-recrutement", "RH & Recrutement"),
    ("industrie-btp", "Industrie & BTP"),
]


def _safe_err(exc: Exception | None) -> str:
    """Message d'erreur SANS l'URL (qui contient api_key). Anti-fuite de secret."""
    if exc is None:
        return "inconnu"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__


class SerpApiProvider(TrendsProvider):
    """Provider Google Trends via SerpApi.com (auth par query param api_key)."""

    name = PROVIDER_SERPAPI

    def __init__(self) -> None:
        if not settings.serpapi_key:
            raise TrendsProviderError("SerpApi non configure (serpapi_key absent)")
        self._key = settings.serpapi_key

    # -- HTTP -----------------------------------------------------------

    async def _get(self, path: str, params: dict | None = None) -> dict:
        full = {**(params or {}), "api_key": self._key}

        async def _do() -> dict:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(f"{_BASE_URL}{path}", params=full)
                resp.raise_for_status()
                return resp.json()

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await _do()
            except Exception as exc:  # noqa: BLE001 — relance apres epuisement
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_BACKOFF_BASE * (2**attempt))
                else:
                    # NE PAS logger exc brut : son URL contient api_key.
                    logger.error("[Trends serpapi] echec apres %d essais : %s",
                                 _MAX_RETRIES + 1, _safe_err(exc))
        raise TrendsProviderError(f"SerpApi indisponible : {_safe_err(last_exc)}") from None

    def _query_term(self, category: str, seed_terms: list[str] | None) -> str:
        if seed_terms:
            return seed_terms[0]
        return category.replace("-", " ")

    async def _trends(
        self, *, data_type: str, category: str, country: str, timeframe: str,
        seed_terms: list[str] | None,
    ) -> dict:
        return await self._get(_SEARCH_PATH, params={
            "engine": _ENGINE,
            "q": self._query_term(category, seed_terms),
            "geo": country,
            "date": timeframe,
            "data_type": data_type,
        })

    @staticmethod
    def _to_int(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    # -- Interface ------------------------------------------------------

    async def list_categories(self) -> list[CategoryItem]:
        return [
            CategoryItem(slug=slug, label=label, provider_category_id=str(idx))
            for idx, (slug, label) in enumerate(_CATEGORIES)
        ]

    async def fetch_category_timeseries(
        self, *, category: str, country: str, language: str, timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[TimeseriesPoint]:
        data = await self._trends(
            data_type="TIMESERIES", category=category, country=country,
            timeframe=timeframe, seed_terms=seed_terms,
        )
        timeline = ((data.get("interest_over_time") or {}).get("timeline_data")) or []
        points: list[TimeseriesPoint] = []
        for pt in timeline:
            values = pt.get("values") or []
            value = self._to_int(values[0].get("extracted_value")) if values else 0
            ts = pt.get("timestamp")
            if ts is not None:
                try:
                    day = datetime.fromtimestamp(int(ts), tz=UTC).date().isoformat()
                except (ValueError, OverflowError, OSError):
                    day = str(pt.get("date", ""))[:10]
            else:
                day = str(pt.get("date", ""))[:10]
            points.append(TimeseriesPoint(date=day, value=value))
        return points

    async def fetch_related_queries(
        self, *, category: str, country: str, language: str, timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> RelatedQueries:
        data = await self._trends(
            data_type="RELATED_QUERIES", category=category, country=country,
            timeframe=timeframe, seed_terms=seed_terms,
        )
        rq_raw = data.get("related_queries") or {}
        top = [
            QueryItem(query=str(it.get("query", "")), value=self._to_int(it.get("extracted_value")))
            for it in (rq_raw.get("top") or []) if it.get("query")
        ]
        rising: list[QueryItem] = []
        for it in rq_raw.get("rising") or []:
            if not it.get("query"):
                continue
            breakout = str(it.get("value", "")).strip().lower() == "breakout"
            rising.append(QueryItem(
                query=str(it["query"]),
                value=0,  # rising : pas d'indice 0-100, seule la croissance compte
                growth=float(self._to_int(it.get("extracted_value"))),
                breakout=breakout,
            ))
        return RelatedQueries(top=top, rising=rising)

    async def fetch_related_topics(
        self, *, category: str, country: str, language: str, timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[TopicItem]:
        data = await self._trends(
            data_type="RELATED_TOPICS", category=category, country=country,
            timeframe=timeframe, seed_terms=seed_terms,
        )
        rt_raw = data.get("related_topics") or {}
        out: list[TopicItem] = []
        for it in (rt_raw.get("top") or []):
            topic = it.get("topic") or {}
            title = (topic.get("title") if isinstance(topic, dict) else None) or it.get("title")
            if title:
                out.append(TopicItem(topic=str(title), value=self._to_int(it.get("extracted_value"))))
        return out

    async def fetch_trending_now(
        self, *, country: str, language: str
    ) -> list[QueryItem]:
        logger.info("[Trends serpapi] trending_now non implemente — retour vide")
        return []

    async def fetch_region_breakdown(
        self, *, category: str, country: str, language: str, timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[RegionItem]:
        data = await self._trends(
            data_type="GEO_MAP_0", category=category, country=country,
            timeframe=timeframe, seed_terms=seed_terms,
        )
        out: list[RegionItem] = []
        for it in (data.get("interest_by_region") or []):
            name = it.get("location") or it.get("geo")
            if name:
                out.append(RegionItem(region=str(name), value=self._to_int(it.get("extracted_value"))))
        out.sort(key=lambda r: r.value, reverse=True)
        return out

    async def healthcheck(self) -> HealthResult:
        try:
            data = await self._get(_ACCOUNT_PATH)
            if data.get("error"):
                return HealthResult(provider=PROVIDER_SERPAPI, status="error", error=str(data["error"])[:200])
            return HealthResult(provider=PROVIDER_SERPAPI, status="ok")
        except TrendsProviderError as exc:
            return HealthResult(provider=PROVIDER_SERPAPI, status="error", error=str(exc))
