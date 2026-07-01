# =============================================================================
# FGA CRM - Trends Provider (interface + format normalise + factory)
# =============================================================================
"""Interface commune a tous les fournisseurs de donnees de tendance.

Chaque adapter (DataForSEO, SerpApi, mock) doit retourner le MEME format interne
normalise (dataclasses ci-dessous). Sans cette couche, tout changement de
fournisseur casserait l'orchestrateur et l'UI (cf. doc 02/03).

Selection du provider (factory `get_trends_provider`) :
- si `dataforseo_login` + `dataforseo_password` configures -> DataForSEOProvider
- sinon -> MockProvider (deployable sans cle, donnees deterministes)

Securite : aucun appel provider cote frontend. Cles lues cote backend uniquement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.config import settings

# Noms de providers (source unique — DC8)
PROVIDER_MOCK = "mock"
PROVIDER_DATAFORSEO = "dataforseo"
PROVIDER_SERPAPI = "serpapi"


# ---------------------------------------------------------------------------
# Format interne normalise
# ---------------------------------------------------------------------------

@dataclass
class CategoryItem:
    slug: str
    label: str
    provider_category_id: str | None = None
    parent_slug: str | None = None


@dataclass
class TimeseriesPoint:
    date: str          # ISO date (YYYY-MM-DD) du debut de periode
    value: int         # indice d'interet 0-100 (relatif, PAS un volume absolu)


@dataclass
class QueryItem:
    query: str
    value: int                       # indice d'interet 0-100
    growth: float | None = None      # variation % (rising), None si top statique
    breakout: bool = False           # True = croissance explosive (>5000% Google)


@dataclass
class RelatedQueries:
    top: list[QueryItem] = field(default_factory=list)
    rising: list[QueryItem] = field(default_factory=list)


@dataclass
class TopicItem:
    topic: str
    value: int


@dataclass
class RegionItem:
    region: str        # code ou nom de region/pays
    value: int         # indice d'interet 0-100


@dataclass
class HealthResult:
    provider: str
    status: str                      # ok | error | unconfigured
    latency_ms: int | None = None
    error: str | None = None


class TrendsProviderError(Exception):
    """Echec d'appel fournisseur apres retries, ou fournisseur non configure."""


# ---------------------------------------------------------------------------
# Interface commune
# ---------------------------------------------------------------------------

class TrendsProvider(ABC):
    """Contrat d'un fournisseur de donnees de tendance.

    Toutes les methodes retournent le format normalise ci-dessus. Les parametres
    optionnels `seed_terms` affinent la requete (categorie seule = cadre large).
    """

    name: str = ""

    @abstractmethod
    async def list_categories(self) -> list[CategoryItem]:
        """Referentiel des categories disponibles cote fournisseur."""

    @abstractmethod
    async def fetch_category_timeseries(
        self,
        *,
        category: str,
        country: str,
        language: str,
        timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[TimeseriesPoint]:
        """Serie temporelle d'interet pour la categorie (+ seeds eventuels)."""

    @abstractmethod
    async def fetch_related_queries(
        self,
        *,
        category: str,
        country: str,
        language: str,
        timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> RelatedQueries:
        """Requetes top (dominantes) et rising (en hausse)."""

    @abstractmethod
    async def fetch_related_topics(
        self,
        *,
        category: str,
        country: str,
        language: str,
        timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[TopicItem]:
        """Sujets connexes."""

    @abstractmethod
    async def fetch_trending_now(
        self, *, country: str, language: str
    ) -> list[QueryItem]:
        """Requetes tendance a l'instant (independant d'une categorie)."""

    @abstractmethod
    async def fetch_region_breakdown(
        self,
        *,
        category: str,
        country: str,
        language: str,
        timeframe: str,
        seed_terms: list[str] | None = None,
    ) -> list[RegionItem]:
        """Repartition geographique de l'interet."""

    @abstractmethod
    async def healthcheck(self) -> HealthResult:
        """Test de configuration/connectivite du fournisseur."""


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _dataforseo_configured() -> bool:
    return bool(settings.dataforseo_login and settings.dataforseo_password)


def get_trends_provider() -> TrendsProvider:
    """Retourne le provider effectif selon la config.

    DataForSEO si credentials presents, sinon MockProvider (deployable sans cle).
    Import tardif pour eviter les cycles d'import.
    """
    if _dataforseo_configured():
        from app.services.trends.dataforseo_provider import DataForSEOProvider

        return DataForSEOProvider()

    from app.services.trends.mock_provider import MockProvider

    return MockProvider()
