# =============================================================================
# FGA CRM - Schemas GEO (Generative Engine Optimization)
# =============================================================================
"""Schemas Pydantic v2 du module GEO.

- Enums : GeoEngine, GeoIntent, GeoSentiment
- Create / Update / Response pour chaque modele
- Schemas d'extraction (interne, non exposes en API)
- Schemas API speciaux (trigger, dashboard, health)
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
# StrEnum (py3.11+) : equivalent fonctionnel a (str, Enum) — .value et la
# comparaison avec un str fonctionnent a l'identique. Choisi pour rester
# ruff-compatible (regle UP042) sur ce projet cible py312.

class GeoEngine(StrEnum):
    perplexity = "perplexity"
    openai = "openai"
    gemini = "gemini"
    claude = "claude"
    grok = "grok"
    google_aio = "google_aio"


class GeoIntent(StrEnum):
    informationnel = "informationnel"
    comparatif = "comparatif"
    transactionnel = "transactionnel"


class GeoSentiment(StrEnum):
    positif = "positif"
    neutre = "neutre"
    negatif = "negatif"


# ---------------------------------------------------------------------------
# GeoBrand
# ---------------------------------------------------------------------------

class GeoBrandCreate(BaseModel):
    organization_id: UUID | None = None
    slug: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    aliases: list[Annotated[str, Field(max_length=255)]] = Field(default_factory=list, max_length=50)
    is_owned: bool = False
    active: bool = True


class GeoBrandUpdate(BaseModel):
    organization_id: UUID | None = None
    slug: str | None = Field(None, min_length=1, max_length=255)
    name: str | None = Field(None, min_length=1, max_length=255)
    aliases: list[Annotated[str, Field(max_length=255)]] | None = Field(None, max_length=50)
    is_owned: bool | None = None
    active: bool | None = None


class GeoBrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None
    slug: str
    name: str
    aliases: list[str]
    is_owned: bool
    active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# GeoPrompt
# ---------------------------------------------------------------------------

class GeoPromptCreate(BaseModel):
    organization_id: UUID | None = None
    text: str = Field(..., min_length=1, max_length=2000)
    intent: GeoIntent
    persona: str | None = Field(None, max_length=255)
    country: str = Field("FR", max_length=8)
    language: str = Field("fr", max_length=8)
    tags: list[str] = Field(default_factory=list, max_length=30)
    priority: bool = False
    active: bool = True


class GeoPromptUpdate(BaseModel):
    text: str | None = Field(None, min_length=1, max_length=2000)
    intent: GeoIntent | None = None
    persona: str | None = Field(None, max_length=255)
    country: str | None = Field(None, max_length=8)
    language: str | None = Field(None, max_length=8)
    tags: list[str] | None = Field(None, max_length=30)
    priority: bool | None = None
    active: bool | None = None


class GeoPromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None
    brand_id: UUID
    text: str
    intent: str
    persona: str | None
    country: str
    language: str
    tags: list[str]
    priority: bool
    active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# GeoRun
# ---------------------------------------------------------------------------

class GeoRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    prompt_id: UUID
    brand_id: UUID
    run_index: int
    engine: str
    model_version: str | None
    country: str | None
    language: str | None
    run_at: datetime
    raw_answer: str | None
    citations: list[dict]
    brands_found: list[dict]
    brand_mentioned: bool | None
    brand_position: int | None
    brand_sentiment: str | None
    brand_recommended: bool | None
    appearance: bool | None
    created_at: datetime


class GeoRunListResponse(BaseModel):
    items: list[GeoRunResponse]
    total: int
    page: int
    size: int
    pages: int


# ---------------------------------------------------------------------------
# GeoMetricsDaily
# ---------------------------------------------------------------------------

class GeoMetricsDailyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID | None
    day: date
    brand_id: UUID
    engine: str
    visibility_rate: float | None
    sov: float | None
    sov_weighted: float | None
    sentiment_avg: float | None
    reco_rate: float | None
    runs_total: int
    computed_at: datetime


# ---------------------------------------------------------------------------
# Extraction (interne — non expose en API)
# ---------------------------------------------------------------------------

class MarqueTrouvee(BaseModel):
    nom: str
    rang: int = Field(ge=1)
    recommandee: bool
    sentiment: GeoSentiment
    justification: str = Field(max_length=500)


class ExtractionResult(BaseModel):
    marques: list[MarqueTrouvee]


# ---------------------------------------------------------------------------
# Schemas API speciaux
# ---------------------------------------------------------------------------

class GeoRunTriggerRequest(BaseModel):
    brand_id: UUID
    engine: GeoEngine
    prompt_ids: list[UUID] = Field(min_length=1, max_length=50)
    n_runs: int = Field(default=3, ge=1, le=5)
    country: str = Field("FR", max_length=8)
    language: str = Field("fr", max_length=8)


class GeoRunTriggerResponse(BaseModel):
    task_id: str
    runs_scheduled: int


class GeoDashboardResponse(BaseModel):
    brand: GeoBrandResponse
    engine: str
    date_from: date
    date_to: date
    metrics: list[GeoMetricsDailyResponse]
    top_competitors: list[dict]   # [{nom, mentions, sov_share}]
    top_sources: list[dict]       # [{domain, count}]


class GeoHealthResponse(BaseModel):
    engine: str
    status: str   # ok|error|unconfigured
    checked_at: datetime
    error: str | None = None
