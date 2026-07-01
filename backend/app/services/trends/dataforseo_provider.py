# =============================================================================
# FGA CRM - Trends DataForSEOProvider (Google Trends via DataForSEO)
# =============================================================================
"""Adapter DataForSEO Google Trends API.

ATTENTION — parsing a valider en LIVE (DC17) :
Ce module est ecrit d'apres la documentation DataForSEO mais N'A PAS ete teste
contre l'API reelle (aucune cle provisionnee au moment de l'ecriture). Des qu'un
compte est configure (`DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD`), lancer un
smoke test live et ajuster le mapping des champs si besoin (P1.1).

Le format de sortie est strictement le format normalise de `provider.py`.
Securite : Basic Auth cote backend uniquement, jamais expose au frontend.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import settings
from app.services.trends.provider import (
    PROVIDER_DATAFORSEO,
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

_BASE_URL = "https://api.dataforseo.com"
_EXPLORE_PATH = "/v3/keywords_data/google_trends/explore/live"
_USER_DATA_PATH = "/v3/appendix/user_data"
_CATEGORIES_PATH = "/v3/keywords_data/google_trends/categories"

_TIMEOUT = 40.0
_MAX_RETRIES = 2
_BACKOFF_BASE = 1.0

# Mapping timeframe interne -> valeur DataForSEO (`date_range`)
_TIMEFRAME_MAP = {
    "now 7-d": "past_7_days",
    "today 1-m": "past_30_days",
    "today 3-m": "past_90_days",
    "today 12-m": "past_12_months",
    "today 5-y": "past_5_years",
}
_DEFAULT_DATE_RANGE = "past_12_months"


class DataForSEOProvider(TrendsProvider):
    """Provider Google Trends via DataForSEO (Basic Auth)."""

    name = PROVIDER_DATAFORSEO

    def __init__(self) -> None:
        if not settings.dataforseo_login or not settings.dataforseo_password:
            raise TrendsProviderError("DataForSEO non configure (login/password absents)")
        self._auth = httpx.BasicAuth(settings.dataforseo_login, settings.dataforseo_password)

    # -- HTTP bas niveau -------------------------------------------------

    async def _post(self, path: str, payload: list[dict]) -> dict:
        """POST authentifie avec retry/backoff. Retourne le JSON decode."""

        async def _do() -> dict:
            async with httpx.AsyncClient(timeout=_TIMEOUT, auth=self._auth) as client:
                resp = await client.post(f"{_BASE_URL}{path}", json=payload)
                resp.raise_for_status()
                return resp.json()

        return await self._retry(_do)

    async def _get(self, path: str) -> dict:
        async def _do() -> dict:
            async with httpx.AsyncClient(timeout=_TIMEOUT, auth=self._auth) as client:
                resp = await client.get(f"{_BASE_URL}{path}")
                resp.raise_for_status()
                return resp.json()

        return await self._retry(_do)

    async def _retry(self, coro_factory):
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await coro_factory()
            except Exception as exc:  # noqa: BLE001 — relance apres epuisement
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_BACKOFF_BASE * (2**attempt))
                else:
                    logger.error("[Trends dataforseo] echec apres %d essais : %s",
                                 _MAX_RETRIES + 1, exc)
        raise TrendsProviderError(f"DataForSEO indisponible : {last_exc}") from last_exc

    def _explore_payload(
        self, keywords: list[str], country: str, language: str, timeframe: str
    ) -> list[dict]:
        return [
            {
                "keywords": keywords[:5],  # DataForSEO limite a 5 keywords/tache
                "location_name": country,
                "language_code": language,
                "date_range": _TIMEFRAME_MAP.get(timeframe, _DEFAULT_DATE_RANGE),
            }
        ]

    @staticmethod
    def _first_result(data: dict) -> dict | None:
        """Extrait le premier result d'une reponse DataForSEO (defensif)."""
        try:
            tasks = data.get("tasks") or []
            if not tasks:
                return None
            results = tasks[0].get("result") or []
            return results[0] if results else None
        except (AttributeError, IndexError, TypeError):
            return None

    @staticmethod
    def _items_of_type(result: dict | None, item_type: str) -> list[dict]:
        """Retourne les items d'un `type` donne dans un result explore (defensif)."""
        if not result:
            return []
        items = result.get("items") or []
        return [it for it in items if isinstance(it, dict) and it.get("type") == item_type]

    # -- Interface -------------------------------------------------------

    async def list_categories(self) -> list[CategoryItem]:
        data = await self._get(_CATEGORIES_PATH)
        result = self._first_result(data)
        out: list[CategoryItem] = []
        items = (result or {}).get("items") or []
        for it in items:
            if not isinstance(it, dict):
                continue
            cat_id = it.get("category_code") or it.get("id")
            name = it.get("category_name") or it.get("name")
            if name is None:
                continue
            out.append(
                CategoryItem(
                    slug=str(name).lower().replace(" ", "-"),
                    label=str(name),
                    provider_category_id=str(cat_id) if cat_id is not None else None,
                )
            )
        return out

    async def fetch_category_timeseries(
        self, *, category: str, country: str, language: str, timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[TimeseriesPoint]:
        keywords = seed_terms or [category.replace("-", " ")]
        data = await self._post(
            _EXPLORE_PATH, self._explore_payload(keywords, country, language, timeframe)
        )
        result = self._first_result(data)
        graphs = self._items_of_type(result, "google_trends_graph")
        points: list[TimeseriesPoint] = []
        for graph in graphs:
            for pt in graph.get("data") or []:
                ts = pt.get("date_from") or pt.get("timestamp")
                values = pt.get("values") or []
                value = values[0] if values and values[0] is not None else 0
                if ts is not None:
                    points.append(TimeseriesPoint(date=str(ts)[:10], value=int(value)))
            break  # un seul graph attendu
        return points

    async def fetch_related_queries(
        self, *, category: str, country: str, language: str, timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> RelatedQueries:
        keywords = seed_terms or [category.replace("-", " ")]
        data = await self._post(
            _EXPLORE_PATH, self._explore_payload(keywords, country, language, timeframe)
        )
        result = self._first_result(data)
        rq = RelatedQueries()
        for item in self._items_of_type(result, "google_trends_queries_list"):
            for entry in item.get("data") or []:
                query = entry.get("query")
                if not query:
                    continue
                qi = QueryItem(
                    query=str(query),
                    value=int(entry.get("value") or 0),
                    growth=entry.get("value_percent"),
                    breakout=bool(entry.get("value_percent") and entry["value_percent"] >= 5000),
                )
                # DataForSEO distingue top/rising via `keyword_type` ou un flag.
                if entry.get("keyword_type") == "rising" or qi.breakout:
                    rq.rising.append(qi)
                else:
                    rq.top.append(qi)
        return rq

    async def fetch_related_topics(
        self, *, category: str, country: str, language: str, timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[TopicItem]:
        keywords = seed_terms or [category.replace("-", " ")]
        data = await self._post(
            _EXPLORE_PATH, self._explore_payload(keywords, country, language, timeframe)
        )
        result = self._first_result(data)
        out: list[TopicItem] = []
        for item in self._items_of_type(result, "google_trends_topics_list"):
            for entry in item.get("data") or []:
                topic = entry.get("topic_title") or entry.get("title")
                if topic:
                    out.append(TopicItem(topic=str(topic), value=int(entry.get("value") or 0)))
        return out

    async def fetch_trending_now(
        self, *, country: str, language: str
    ) -> list[QueryItem]:
        # DataForSEO n'expose pas un "trending now" direct sur Google Trends explore.
        # A brancher sur l'endpoint dedie quand le compte est actif (P1.1).
        logger.info("[Trends dataforseo] trending_now non implemente — retour vide")
        return []

    async def fetch_region_breakdown(
        self, *, category: str, country: str, language: str, timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[RegionItem]:
        keywords = seed_terms or [category.replace("-", " ")]
        data = await self._post(
            _EXPLORE_PATH, self._explore_payload(keywords, country, language, timeframe)
        )
        result = self._first_result(data)
        out: list[RegionItem] = []
        for item in self._items_of_type(result, "google_trends_map"):
            for entry in item.get("data") or []:
                region = entry.get("geo_name") or entry.get("geo_id")
                values = entry.get("values") or []
                value = values[0] if values and values[0] is not None else 0
                if region is not None:
                    out.append(RegionItem(region=str(region), value=int(value)))
        out.sort(key=lambda r: r.value, reverse=True)
        return out

    async def healthcheck(self) -> HealthResult:
        try:
            await self._get(_USER_DATA_PATH)
            return HealthResult(provider=PROVIDER_DATAFORSEO, status="ok")
        except TrendsProviderError as exc:
            return HealthResult(provider=PROVIDER_DATAFORSEO, status="error", error=str(exc))
