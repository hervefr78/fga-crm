# =============================================================================
# FGA CRM - GEO Collector (multi-moteurs)
# =============================================================================
"""Collecteur multi-moteurs pour le module GEO.

Interface commune (BaseCollector) + implementations :
- PerplexityCollector (P1) — Sonar API, format compatible OpenAI
- OpenAICollector (P2) — GPT-4o + web search tool
- GeminiCollector (P2) — Gemini 2.0 Flash + grounding Google Search

Chaque collecteur gere son propre timeout (30s) et ses propres retries (max 2,
backoff 1s/2s). Au-dela, l'exception est propagee pour que Celery la gere.

Le collecteur ne fait QUE la collecte (reponse brute + citations). L'extraction
structuree des marques est strictement separee (voir extractor.py).
"""

import asyncio
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Timeout commun a tous les appels HTTP de collecte
COLLECT_TIMEOUT = 30.0

# Retry : max 2 retries (3 tentatives au total), backoff exponentiel 1s puis 2s
MAX_RETRIES = 2
BACKOFF_BASE = 1.0

# System prompt commun aux collecteurs conversationnels (FR)
SYSTEM_PROMPT_FR = (
    "Tu es un assistant qui repond aux questions d'utilisateurs francophones."
)

# Temperatures de collecte (leger bruit voulu — l'extracteur, lui, est a T=0)
PERPLEXITY_TEMPERATURE = 0.2
OPENAI_TEMPERATURE = 0.3
GEMINI_TEMPERATURE = 0.3


# ---------------------------------------------------------------------------
# Resultat de collecte
# ---------------------------------------------------------------------------

@dataclass
class CollectorResult:
    raw_answer: str
    citations: list[dict] = field(default_factory=list)  # [{url, domain, rank}]
    model_version: str = ""
    engine: str = ""


class CollectorError(Exception):
    """Echec de collecte apres epuisement des retries, ou moteur non configure."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _domain_from_url(url: str) -> str:
    """Extraire le domaine d'une URL (sans dependance lourde — urlparse stdlib).

    Retourne le netloc en minuscules, sans prefixe www. Chaine vide si invalide.
    """
    try:
        netloc = urlparse(url).netloc.lower()
    except (ValueError, TypeError):
        return ""
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _citations_from_urls(urls: list) -> list[dict]:
    """Construire la liste de citations [{url, domain, rank}] depuis des URLs brutes."""
    citations: list[dict] = []
    for rank, raw in enumerate(urls, start=1):
        if not isinstance(raw, str) or not raw:
            continue
        citations.append({"url": raw, "domain": _domain_from_url(raw), "rank": rank})
    return citations


async def _retry_async(coro_factory, *, engine: str):
    """Executer coro_factory() avec retry (max 2) et backoff exponentiel.

    coro_factory est un callable sans argument qui retourne une coroutine fraiche
    a chaque tentative (une coroutine n'est pas reutilisable).
    """
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return await coro_factory()
        except Exception as exc:  # noqa: BLE001 — on relance apres epuisement
            last_exc = exc
            if attempt < MAX_RETRIES:
                delay = BACKOFF_BASE * (2**attempt)
                logger.warning(
                    "[GEO collector:%s] tentative %d/%d echouee (%s) — retry dans %.0fs",
                    engine, attempt + 1, MAX_RETRIES + 1, exc, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "[GEO collector:%s] echec apres %d tentatives : %s",
                    engine, MAX_RETRIES + 1, exc,
                )
    raise CollectorError(f"Collecte {engine} echouee : {last_exc}") from last_exc


# ---------------------------------------------------------------------------
# Interface commune
# ---------------------------------------------------------------------------

class BaseCollector:
    engine: str = ""

    async def collect(
        self, prompt_text: str, country: str = "FR", language: str = "fr"
    ) -> CollectorResult:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Perplexity (P1)
# ---------------------------------------------------------------------------

class PerplexityCollector(BaseCollector):
    """P1 — Sonar API via httpx (format compatible OpenAI)."""

    engine = "perplexity"
    API_URL = "https://api.perplexity.ai/chat/completions"
    MODEL = "sonar"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key if api_key is not None else settings.perplexity_api_key

    async def collect(
        self, prompt_text: str, country: str = "FR", language: str = "fr"
    ) -> CollectorResult:
        if not self._api_key:
            raise CollectorError("Perplexity non configure (perplexity_api_key manquante)")

        payload = {
            "model": self.MODEL,
            "temperature": PERPLEXITY_TEMPERATURE,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT_FR},
                {"role": "user", "content": prompt_text},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async def _call() -> CollectorResult:
            async with httpx.AsyncClient(timeout=COLLECT_TIMEOUT) as http:
                resp = await http.post(self.API_URL, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            choices = data.get("choices") or []
            raw_answer = ""
            if choices:
                raw_answer = (choices[0].get("message") or {}).get("content") or ""
            # Perplexity renvoie une liste d'URLs dans data["citations"]
            urls = data.get("citations") or []
            model_version = data.get("model") or self.MODEL
            return CollectorResult(
                raw_answer=raw_answer,
                citations=_citations_from_urls(urls),
                model_version=model_version,
                engine=self.engine,
            )

        return await _retry_async(_call, engine=self.engine)


# ---------------------------------------------------------------------------
# OpenAI (P2)
# ---------------------------------------------------------------------------

class OpenAICollector(BaseCollector):
    """P2 — GPT-4o avec web search tool (si disponible)."""

    engine = "openai"
    MODEL = "gpt-4o"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key if api_key is not None else settings.openai_api_key

    async def collect(
        self, prompt_text: str, country: str = "FR", language: str = "fr"
    ) -> CollectorResult:
        if not self._api_key:
            raise CollectorError("OpenAI non configure (openai_api_key manquante)")

        # Import tardif — la lib openai est lourde, on ne la charge qu'au besoin.
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._api_key, timeout=COLLECT_TIMEOUT)

        async def _call() -> CollectorResult:
            # On tente d'abord avec le tool web_search_preview ; si l'API ne le
            # supporte pas (TypeError/BadRequest), on retombe sur un appel simple.
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT_FR},
                {"role": "user", "content": prompt_text},
            ]
            try:
                resp = await client.chat.completions.create(
                    model=self.MODEL,
                    temperature=OPENAI_TEMPERATURE,
                    messages=messages,
                    tools=[{"type": "web_search_preview"}],
                )
            except Exception as exc:  # noqa: BLE001 — fallback sans tool
                logger.info(
                    "[GEO collector:openai] web_search indisponible (%s) — fallback sans tool",
                    exc,
                )
                resp = await client.chat.completions.create(
                    model=self.MODEL,
                    temperature=OPENAI_TEMPERATURE,
                    messages=messages,
                )
            choice = resp.choices[0] if resp.choices else None
            raw_answer = ""
            if choice and choice.message:
                raw_answer = choice.message.content or ""
            return CollectorResult(
                raw_answer=raw_answer,
                citations=[],  # pas de citations natives fiables sans tool structure
                model_version=getattr(resp, "model", None) or self.MODEL,
                engine=self.engine,
            )

        return await _retry_async(_call, engine=self.engine)


# ---------------------------------------------------------------------------
# Gemini (P2)
# ---------------------------------------------------------------------------

class GeminiCollector(BaseCollector):
    """P2 — Gemini 2.0 Flash avec grounding Google Search (API REST, pas de SDK)."""

    engine = "gemini"
    MODEL = "gemini-2.0-flash"
    API_URL = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent"
    )

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key if api_key is not None else settings.gemini_api_key

    async def collect(
        self, prompt_text: str, country: str = "FR", language: str = "fr"
    ) -> CollectorResult:
        if not self._api_key:
            raise CollectorError("Gemini non configure (gemini_api_key manquante)")

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT_FR}]},
            "contents": [{"role": "user", "parts": [{"text": prompt_text}]}],
            "tools": [{"googleSearch": {}}],
            "generationConfig": {"temperature": GEMINI_TEMPERATURE},
        }
        # Cle API en header (pas en query param) : evite qu'elle apparaisse en clair
        # dans les access logs httpx/nginx. Gemini supporte x-goog-api-key en header.
        gemini_headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }

        async def _call() -> CollectorResult:
            async with httpx.AsyncClient(timeout=COLLECT_TIMEOUT) as http:
                resp = await http.post(self.API_URL, json=payload, headers=gemini_headers)
                resp.raise_for_status()
                data = resp.json()
            candidates = data.get("candidates") or []
            raw_answer = ""
            citations: list[dict] = []
            if candidates:
                cand = candidates[0]
                parts = (cand.get("content") or {}).get("parts") or []
                raw_answer = "".join(
                    p.get("text", "") for p in parts if isinstance(p, dict)
                )
                # Citations depuis groundingMetadata.groundingChunks[].web.uri
                grounding = cand.get("groundingMetadata") or {}
                chunks = grounding.get("groundingChunks") or []
                urls: list[str] = []
                for chunk in chunks:
                    web = (chunk or {}).get("web") or {}
                    uri = web.get("uri")
                    if uri:
                        urls.append(uri)
                citations = _citations_from_urls(urls)
            return CollectorResult(
                raw_answer=raw_answer,
                citations=citations,
                model_version=self.MODEL,
                engine=self.engine,
            )

        return await _retry_async(_call, engine=self.engine)


# ---------------------------------------------------------------------------
# SerpApi — Google AI Overviews (P3)
# ---------------------------------------------------------------------------

class SerpApiCollector(BaseCollector):
    """P3 — Google AI Overviews via SerpApi.

    Mesure deux choses distinctes :
    - appearance (bool) : l'AI Overview est-il apparu sur ce prompt ?
    - raw_answer (str) : le contenu textuel de l'Overview si present, sinon ""

    citations = les sources listees dans l'Overview (si disponibles).

    API : GET https://serpapi.com/search.json
    Params : q=..., engine=google, api_key=..., location=France, hl=fr, gl=fr
    """

    engine = "google_aio"
    API_URL = "https://serpapi.com/search.json"

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key if api_key is not None else settings.serpapi_key

    async def collect(
        self, prompt_text: str, country: str = "FR", language: str = "fr"
    ) -> CollectorResult:
        if not self._api_key:
            raise CollectorError("SerpApi non configure (serpapi_key manquante)")

        params = {
            "q": prompt_text,
            "engine": "google",
            "api_key": self._api_key,
            "hl": language,
            "gl": country.lower(),
            "location": "France" if country.upper() == "FR" else country,
        }

        async def _call() -> CollectorResult:
            async with httpx.AsyncClient(timeout=COLLECT_TIMEOUT) as http:
                resp = await http.get(self.API_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            # Extraire l'AI Overview depuis la reponse SerpApi
            # SerpApi renvoie ai_overview.text_blocks ou ai_overview.organic_results
            ai_overview = data.get("ai_overview") or {}

            # Construire le texte depuis les blocs textuels
            raw_answer = ""
            if ai_overview:
                text_blocks = ai_overview.get("text_blocks") or []
                parts = []
                for block in text_blocks:
                    if isinstance(block, dict):
                        text = block.get("snippet") or block.get("text") or ""
                        if text:
                            parts.append(text)
                raw_answer = " ".join(parts)
                # Fallback : certaines reponses ont .organic_results[].snippet
                if not raw_answer:
                    for r in (ai_overview.get("organic_results") or []):
                        sn = r.get("snippet") or ""
                        if sn:
                            parts.append(sn)
                    raw_answer = " ".join(parts)

            # Citations : sources listees dans l'Overview
            sources = ai_overview.get("sources") or []
            urls = [
                s.get("link")
                for s in sources
                if isinstance(s, dict) and s.get("link")
            ]

            return CollectorResult(
                raw_answer=raw_answer,
                citations=_citations_from_urls(urls),
                model_version="google-ai-overviews",
                engine=self.engine,
            )

        return await _retry_async(_call, engine=self.engine)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_COLLECTORS: dict[str, type[BaseCollector]] = {
    "perplexity": PerplexityCollector,
    "openai": OpenAICollector,
    "gemini": GeminiCollector,
    "google_aio": SerpApiCollector,
}


def get_collector(engine: str) -> BaseCollector:
    """Factory — leve ValueError si moteur inconnu ou non configure.

    Un moteur est "non configure" si sa cle API n'est pas presente dans settings.
    On verifie a l'instanciation pour echouer tot (avant tout appel reseau).
    """
    collector_cls = _COLLECTORS.get(engine)
    if collector_cls is None:
        raise ValueError(
            f"Moteur GEO inconnu ou non supporte (P1/P2) : {engine}. "
            f"Supportes : {', '.join(sorted(_COLLECTORS))}"
        )
    collector = collector_cls()
    # Verifier la configuration (cle API) immediatement
    if not getattr(collector, "_api_key", None):
        raise ValueError(f"Moteur GEO non configure (cle API manquante) : {engine}")
    return collector
