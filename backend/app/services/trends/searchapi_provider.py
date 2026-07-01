# =============================================================================
# FGA CRM - Trends SearchApiProvider (Google Trends via SearchApi.io)
# =============================================================================
"""Adapter Google Trends via SearchApi.io (searchapi.io — a NE PAS confondre avec
serpapi.com utilise par le moteur GEO google_aio).

Structure de reponse VALIDEE en live (2026-07-01) :
- TIMESERIES : interest_over_time.timeline_data[] -> {timestamp, values[{extracted_value}]}
- RELATED_QUERIES : related_queries.{top,rising}[] -> {query, extracted_value, values}
  (rising : values == "Breakout" -> breakout ; extracted_value = croissance %)
- GEO_MAP : interest_by_region[] (peut renvoyer une erreur -> best-effort vide)

Auth : Bearer token cote backend uniquement. 1 credit SearchApi par data_type.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

import httpx

from app.config import settings
from app.services.trends.provider import (
    PROVIDER_SEARCHAPI,
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

_BASE_URL = "https://www.searchapi.io/api/v1"
_SEARCH_PATH = "/search"
_ME_PATH = "/me"
_ENGINE = "google_trends"

_TIMEOUT = 30.0
_MAX_RETRIES = 2
_BACKOFF_BASE = 1.0

# Categories métier (memes que le mock : ce sont des libelles utilises comme
# requete `q` — pas la taxonomie de categories Google Trends). Coherence UX.
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


class SearchApiProvider(TrendsProvider):
    """Provider Google Trends via SearchApi.io (Bearer auth)."""

    name = PROVIDER_SEARCHAPI

    def __init__(self) -> None:
        if not settings.searchapi_key:
            raise TrendsProviderError("SearchApi non configure (searchapi_key absent)")
        self._headers = {"Authorization": f"Bearer {settings.searchapi_key}"}

    # -- HTTP -----------------------------------------------------------

    async def _get(self, path: str, params: dict | None = None) -> dict:
        async def _do() -> dict:
            async with httpx.AsyncClient(timeout=_TIMEOUT, headers=self._headers) as client:
                resp = await client.get(f"{_BASE_URL}{path}", params=params or {})
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
                    logger.error("[Trends searchapi] echec apres %d essais : %s",
                                 _MAX_RETRIES + 1, exc)
        raise TrendsProviderError(f"SearchApi indisponible : {last_exc}") from last_exc

    def _query_term(self, category: str, seed_terms: list[str] | None) -> str:
        """Terme de recherche `q` : premier seed, sinon libelle categorie lisible."""
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
            "time": timeframe,
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
            breakout = str(it.get("values", "")).strip().lower() == "breakout"
            rising.append(QueryItem(
                query=str(it["query"]),
                value=0,  # rising : pas d'indice d'interet 0-100, seule la croissance compte
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
        # SearchApi expose google_trends_trending_now via un autre engine (P1.1).
        logger.info("[Trends searchapi] trending_now non implemente — retour vide")
        return []

    async def fetch_region_breakdown(
        self, *, category: str, country: str, language: str, timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[RegionItem]:
        data = await self._trends(
            data_type="GEO_MAP", category=category, country=country,
            timeframe=timeframe, seed_terms=seed_terms,
        )
        regions_raw = data.get("interest_by_region") or data.get("compared_breakdown_by_region") or []
        out: list[RegionItem] = []
        for it in regions_raw:
            name = it.get("location") or it.get("geo_name") or it.get("region")
            values = it.get("values") or []
            value = self._to_int(values[0].get("extracted_value")) if values else self._to_int(it.get("extracted_value"))
            if name:
                out.append(RegionItem(region=str(name), value=value))
        out.sort(key=lambda r: r.value, reverse=True)
        return out

    async def healthcheck(self) -> HealthResult:
        try:
            await self._get(_ME_PATH)
            return HealthResult(provider=PROVIDER_SEARCHAPI, status="ok")
        except TrendsProviderError as exc:
            return HealthResult(provider=PROVIDER_SEARCHAPI, status="error", error=str(exc))
