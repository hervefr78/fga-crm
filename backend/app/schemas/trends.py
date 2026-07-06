# =============================================================================
# FGA CRM - Schemas Trends (Pydantic)
# =============================================================================
"""Schemas d'API du module Trends. Alignes sur les types front (types/trends.ts).

Regles projet :
- toutes les entrees bornees (DC1) : max_length sur strings, cap sur listes
- dates de statut en datetime (from_attributes), timeframe = enum borne
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Bornes (DC1)
MAX_SEED_TERM_LEN = 120
MAX_SEED_TERMS = 20
MAX_QUERY_LEN = 120
MAX_COUNTRY_LEN = 8
MAX_LANG_LEN = 8


class TrendMode(StrEnum):
    quick = "quick"
    deep = "deep"


class TrendTimeframe(StrEnum):
    """Fenetres temporelles supportees (bornees — DC1). Mappees cote provider."""

    d7 = "now 7-d"
    m1 = "today 1-m"
    m3 = "today 3-m"
    m12 = "today 12-m"
    y5 = "today 5-y"


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

class TrendCategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    label: str
    provider: str
    provider_category_id: str | None
    parent_slug: str | None
    active: bool
    display_order: int


# ---------------------------------------------------------------------------
# Creation de rapport (job)
# ---------------------------------------------------------------------------

class TrendReportCreateRequest(BaseModel):
    mode: TrendMode = TrendMode.quick
    # Ciblage : categorie du referentiel OU sujet libre (exactement un — cf.
    # validateur). category_id = categorie predefinie ; query = sujet hors
    # referentiel (analyse one-shot, non persistee).
    category_id: UUID | None = None
    query: str | None = Field(None, max_length=MAX_QUERY_LEN)
    country: str = Field("FR", max_length=MAX_COUNTRY_LEN)
    language: str = Field("fr", max_length=MAX_LANG_LEN)
    timeframe: TrendTimeframe = TrendTimeframe.m12
    seed_terms: list[str] = Field(default_factory=list, max_length=MAX_SEED_TERMS)
    # refresh=True force un recalcul meme si un rapport en cache existe
    refresh: bool = False

    @model_validator(mode="after")
    def _exactly_one_target(self) -> TrendReportCreateRequest:
        """Exactement un ciblage : category_id XOR query (DC1 : entree bornee/valide)."""
        has_cat = self.category_id is not None
        has_query = bool((self.query or "").strip())
        if has_cat == has_query:  # les deux fournis, ou aucun
            raise ValueError("Fournir soit category_id, soit query (exactement un).")
        return self

    def normalized_query(self) -> str | None:
        """Sujet libre nettoye/borne (DC1). None si absent."""
        q = (self.query or "").strip()[:MAX_QUERY_LEN]
        return q or None

    def normalized_seeds(self) -> list[str]:
        """Seeds nettoyes, bornes en taille (DC1)."""
        out: list[str] = []
        for raw in self.seed_terms:
            term = (raw or "").strip()[:MAX_SEED_TERM_LEN]
            if term:
                out.append(term)
        return out[:MAX_SEED_TERMS]


# ---------------------------------------------------------------------------
# Statut de job
# ---------------------------------------------------------------------------

class TrendJobProgress(BaseModel):
    steps_total: int
    steps_done: int


class TrendJobResponse(BaseModel):
    job_id: UUID
    mode: str
    status: str
    provider_primary: str
    provider_effective: str | None
    cache_hit: bool = False
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    progress: TrendJobProgress
    created_at: datetime


# ---------------------------------------------------------------------------
# Signaux normalises (contenu du rapport)
# ---------------------------------------------------------------------------

class MarketPulse(BaseModel):
    interest_index: float          # moyenne d'interet recente 0-100
    direction: str                 # up | down | flat
    freshness: str                 # fresh | cached


class TrendQuery(BaseModel):
    query: str
    value: int
    growth: float | None = None
    breakout: bool = False


class TrendTopic(BaseModel):
    topic: str
    value: int


class TrendRegion(BaseModel):
    region: str
    value: int


class TrendTimeseriesPoint(BaseModel):
    date: str
    value: int


class TrendSignals(BaseModel):
    market_pulse: MarketPulse
    timeseries: list[TrendTimeseriesPoint] = Field(default_factory=list)
    rising_queries: list[TrendQuery] = Field(default_factory=list)
    top_queries: list[TrendQuery] = Field(default_factory=list)
    related_topics: list[TrendTopic] = Field(default_factory=list)
    regions: list[TrendRegion] = Field(default_factory=list)


class TrendReportMeta(BaseModel):
    provider_effective: str
    generated_at: str
    cached: bool
    category_slug: str
    country: str
    language: str
    timeframe: str


class TrendReportResponse(BaseModel):
    job_id: UUID
    status: str
    summary_md: str | None
    opportunity_score: float | None
    signals: TrendSignals | None
    meta: TrendReportMeta | None


# ---------------------------------------------------------------------------
# Health (admin)
# ---------------------------------------------------------------------------

class TrendHealthResponse(BaseModel):
    provider: str
    status: str                    # ok | error | unconfigured
    latency_ms: int | None = None
    error: str | None = None
