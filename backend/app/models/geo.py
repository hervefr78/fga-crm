# =============================================================================
# FGA CRM - Modeles GEO (Generative Engine Optimization)
# =============================================================================
"""Modeles du module GEO : suivi de la visibilite des marques dans les moteurs
generatifs (Perplexity, OpenAI, Gemini, etc.).

- GeoBrand : marques suivies + concurrents decouverts
- GeoPrompt : univers de prompts par marque
- GeoRun : une ligne par execution (immutable — created_at seul, pas d'updated_at)
- GeoMetricsDaily : agregats pre-calcules par jour/marque/moteur
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

# Moteurs supportes (source unique — DC8). Les schemas Pydantic exposent l'enum.
GEO_ENGINES = ["perplexity", "openai", "gemini", "claude", "grok", "google_aio"]

# Intentions de prompt
GEO_INTENTS = ["informationnel", "comparatif", "transactionnel"]

# Sentiments possibles envers une marque
GEO_SENTIMENTS = ["positif", "neutre", "negatif"]


class GeoBrand(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "geo_brands"

    # organization_id : isolation multi-tenant. Nullable jusqu'a creation de la table
    # organizations. Index pour les futures requetes filtrees par organisation.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    # Aliases alternatifs (variantes de nom) utilises pour matcher la marque
    aliases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # True = marque possedee par le client (par opposition aux concurrents decouverts)
    is_owned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    prompts: Mapped[list["GeoPrompt"]] = relationship(
        back_populates="brand", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GeoBrand {self.slug}>"


class GeoPrompt(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "geo_prompts"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geo_brands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # informationnel | comparatif | transactionnel
    intent: Mapped[str] = mapped_column(Text, nullable=False)
    persona: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(Text, nullable=False, default="FR")
    language: Mapped[str] = mapped_column(Text, nullable=False, default="fr")
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    priority: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    brand: Mapped["GeoBrand"] = relationship(back_populates="prompts")

    def __repr__(self) -> str:
        return f"<GeoPrompt {self.id} ({self.intent})>"


class GeoRun(Base, UUIDMixin):
    """Une execution = une ligne. Immutable : created_at seul, pas d'updated_at.

    On n'herite PAS de TimestampMixin (qui impose updated_at) — un run ne doit
    jamais etre modifie apres insertion.
    """

    __tablename__ = "geo_runs"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geo_prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geo_brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_index: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    engine: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    country: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    raw_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    citations: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    brands_found: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    brand_mentioned: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    brand_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    brand_sentiment: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_recommended: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Google AI Overviews uniquement (apparition dans l'AIO)
    appearance: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # created_at seul (run immutable). Defini explicitement car pas de TimestampMixin.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        # Index composites pour les agregations (dashboard, scorer).
        Index("ix_geo_runs_brand_engine_run_at", "brand_id", "engine", "run_at"),
        Index("ix_geo_runs_prompt_run_at", "prompt_id", "run_at"),
    )

    def __repr__(self) -> str:
        return f"<GeoRun {self.id} {self.engine} idx={self.run_index}>"


class GeoMetricsDaily(Base, UUIDMixin):
    """Agregats pre-calcules par (jour, marque, moteur). Recalculables depuis geo_runs."""

    __tablename__ = "geo_metrics_daily"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geo_brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    engine: Mapped[str] = mapped_column(Text, nullable=False)

    visibility_rate: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    sov: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    sov_weighted: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    sentiment_avg: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    reco_rate: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    runs_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("day", "brand_id", "engine", name="uq_geo_metrics_day_brand_engine"),
    )

    def __repr__(self) -> str:
        return f"<GeoMetricsDaily {self.day} {self.engine}>"


# Statuts d'un job d'audit de visibilite (state machine — DC5)
GEO_AUDIT_STATUSES = ["queued", "running", "completed", "failed"]


class GeoAuditJob(Base, UUIDMixin, TimestampMixin):
    """Mesure de visibilite a la demande (integration Startup Radar).

    SR envoie {company_name, domain, aliases, prompts}. Le CRM cree une marque
    EPHEMERE (is_owned=false -> invisible du dashboard), lance 1 run Perplexity,
    agrege le resultat. request_hash = dedup (30j). Cf. docs/integrations/.
    """

    __tablename__ = "geo_audit_jobs"

    # NOT NULL depuis mt_contract_001 (job cree par la route, toujours tague org).
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    domain: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256(domain|engine|prompts tries|country|language) — deduplication
    request_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    engine: Mapped[str] = mapped_column(Text, nullable=False, default="perplexity")
    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    brand_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("geo_brands.id", ondelete="SET NULL"),
        nullable=True,
    )
    # prompts + aliases + country + language (entree SR)
    params_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # resultat agrege (contrat API) — {} tant que non termine
    result_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_geo_audit_jobs_hash_status", "request_hash", "status"),
    )

    def __repr__(self) -> str:
        return f"<GeoAuditJob {self.domain} {self.status}>"
