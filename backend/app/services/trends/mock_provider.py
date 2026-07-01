# =============================================================================
# FGA CRM - Trends MockProvider (donnees deterministes, sans cle API)
# =============================================================================
"""Fournisseur de secours pour le dev/demo : genere des donnees de tendance
DETERMINISTES a partir d'un hash des parametres.

Deterministe = meme requete -> memes donnees. Cela rend :
- le cache et la deduplication (request_hash) coherents,
- les tests reproductibles (pas de flakiness).

Ne fait AUCUN appel reseau. Les valeurs imitent le format Google Trends
(indice 0-100 relatif, PAS un volume absolu).
"""

from __future__ import annotations

import hashlib
from datetime import date, timedelta

from app.services.trends.provider import (
    PROVIDER_MOCK,
    CategoryItem,
    HealthResult,
    QueryItem,
    RegionItem,
    RelatedQueries,
    TimeseriesPoint,
    TopicItem,
    TrendsProvider,
)

# Categories mock (secteurs FGA plausibles). provider_category_id = index stable.
_MOCK_CATEGORIES: list[tuple[str, str]] = [
    ("conseil-strategie", "Conseil & Strategie"),
    ("croissance-vente", "Croissance & Vente"),
    ("marketing-digital", "Marketing Digital"),
    ("intelligence-artificielle", "Intelligence Artificielle"),
    ("saas-logiciel", "SaaS & Logiciel"),
    ("finance-levee", "Finance & Levee de fonds"),
    ("rh-recrutement", "RH & Recrutement"),
    ("industrie-btp", "Industrie & BTP"),
]

# Modeles de requetes FR pour habiller les keywords (deterministe via index)
_QUERY_TEMPLATES = [
    "{term}",
    "{term} entreprise",
    "meilleur {term}",
    "{term} prix",
    "logiciel {term}",
    "{term} France",
    "agence {term}",
    "{term} 2026",
    "comment choisir {term}",
    "{term} pour PME",
]

_TOPIC_TEMPLATES = [
    "Automatisation {term}",
    "Strategie {term}",
    "Outils {term}",
    "Tendances {term}",
    "ROI {term}",
]

_REGIONS_FR = [
    "Ile-de-France",
    "Auvergne-Rhone-Alpes",
    "Nouvelle-Aquitaine",
    "Occitanie",
    "Hauts-de-France",
    "Provence-Alpes-Cote d'Azur",
    "Grand Est",
    "Bretagne",
]

# Reference du nombre de points selon le timeframe (approximation hebdomadaire)
_TIMEFRAME_WEEKS = {
    "now 7-d": 7,
    "today 1-m": 4,
    "today 3-m": 13,
    "today 12-m": 52,
    "today 5-y": 60,
}
_DEFAULT_WEEKS = 52


def _rng(seed: str):
    """Generateur infini d'entiers pseudo-aleatoires DETERMINISTES depuis un seed.

    On derive un flux d'octets de sha256(seed:counter) — reproductible, sans
    dependance a Math.random / l'horloge.
    """
    counter = 0
    while True:
        digest = hashlib.sha256(f"{seed}:{counter}".encode()).digest()
        for i in range(0, len(digest), 4):
            yield int.from_bytes(digest[i : i + 4], "big")
        counter += 1


def _seed(*parts: str) -> str:
    return "|".join(p for p in parts if p)


def _term_from(category: str, seed_terms: list[str] | None) -> str:
    """Terme de base pour habiller les requetes : premier seed, sinon libelle categorie."""
    if seed_terms:
        return seed_terms[0]
    # slug -> mots lisibles
    return category.replace("-", " ")


class MockProvider(TrendsProvider):
    """Provider deterministe (aucune cle requise)."""

    name = PROVIDER_MOCK

    async def list_categories(self) -> list[CategoryItem]:
        return [
            CategoryItem(slug=slug, label=label, provider_category_id=str(idx))
            for idx, (slug, label) in enumerate(_MOCK_CATEGORIES)
        ]

    async def fetch_category_timeseries(
        self,
        *,
        category: str,
        country: str,
        language: str,
        timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[TimeseriesPoint]:
        weeks = _TIMEFRAME_WEEKS.get(timeframe, _DEFAULT_WEEKS)
        gen = _rng(_seed("ts", category, country, timeframe, *(seed_terms or [])))
        # Tendance de fond deterministe : pente entre -1 et +2 par semaine.
        slope = (next(gen) % 30) / 10.0 - 1.0
        base = 30 + next(gen) % 30
        start = date(2026, 6, 30) - timedelta(weeks=weeks - 1)
        points: list[TimeseriesPoint] = []
        for w in range(weeks):
            noise = next(gen) % 21 - 10  # -10..+10
            value = int(base + slope * w + noise)
            value = max(0, min(100, value))
            points.append(
                TimeseriesPoint(date=(start + timedelta(weeks=w)).isoformat(), value=value)
            )
        return points

    async def fetch_related_queries(
        self,
        *,
        category: str,
        country: str,
        language: str,
        timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> RelatedQueries:
        term = _term_from(category, seed_terms)
        gen = _rng(_seed("rq", category, country, timeframe, *(seed_terms or [])))
        top: list[QueryItem] = []
        for i in range(8):
            tmpl = _QUERY_TEMPLATES[i % len(_QUERY_TEMPLATES)]
            top.append(
                QueryItem(query=tmpl.format(term=term), value=max(5, 100 - i * 11))
            )
        rising: list[QueryItem] = []
        for i in range(6):
            tmpl = _QUERY_TEMPLATES[(i + 3) % len(_QUERY_TEMPLATES)]
            g = next(gen) % 900 + 50  # 50..950 %
            breakout = (next(gen) % 5) == 0
            rising.append(
                QueryItem(
                    query=tmpl.format(term=term),
                    value=max(5, 90 - i * 9),
                    growth=float(5000 if breakout else g),
                    breakout=breakout,
                )
            )
        return RelatedQueries(top=top, rising=rising)

    async def fetch_related_topics(
        self,
        *,
        category: str,
        country: str,
        language: str,
        timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[TopicItem]:
        term = _term_from(category, seed_terms)
        return [
            TopicItem(topic=tmpl.format(term=term), value=max(10, 100 - i * 15))
            for i, tmpl in enumerate(_TOPIC_TEMPLATES)
        ]

    async def fetch_trending_now(
        self, *, country: str, language: str
    ) -> list[QueryItem]:
        gen = _rng(_seed("tn", country))
        out: list[QueryItem] = []
        for i in range(10):
            g = next(gen) % 800 + 100
            out.append(
                QueryItem(query=f"tendance {country} #{i + 1}", value=max(5, 95 - i * 8), growth=float(g))
            )
        return out

    async def fetch_region_breakdown(
        self,
        *,
        category: str,
        country: str,
        language: str,
        timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[RegionItem]:
        gen = _rng(_seed("rg", category, country, *(seed_terms or [])))
        regions = [
            RegionItem(region=name, value=next(gen) % 101) for name in _REGIONS_FR
        ]
        # Tri decroissant : la region la plus chaude en tete.
        regions.sort(key=lambda r: r.value, reverse=True)
        return regions

    async def healthcheck(self) -> HealthResult:
        # Le mock est toujours operationnel (aucune dependance externe).
        return HealthResult(provider=PROVIDER_MOCK, status="ok", latency_ms=0)
