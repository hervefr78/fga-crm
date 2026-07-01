# =============================================================================
# FGA CRM - Modeles Trends (signal de demande de marche)
# =============================================================================
"""Modeles du module Trends : lecture de la demande de marche (Google Trends via
DataForSEO, SerpApi en fallback, ou provider mock pour le dev).

Distinct des modeles geo_* (qui mesurent la visibilite d'une MARQUE dans les
moteurs generatifs). Ici on mesure une DEMANDE de recherche et des signaux.

- TrendCategory : referentiel des categories (selecteur UI, mapping fournisseur)
- TrendCategorySeed : termes seeds par categorie (Deep Research — P4)
- TrendJob : une execution (quick|deep), dedup via request_hash, auditabilite
- TrendSnapshot : resultat brut normalise d'un job (immutable)
- TrendKeyword : keywords deroules d'un snapshot (tri/filtre/export — P4)
- TrendReport : synthese lisible (summary_md, signaux, opportunity_score)
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

# Modes d'execution (source unique — DC8). Les schemas Pydantic exposent l'enum.
TREND_MODES = ["quick", "deep"]

# Statuts d'un job (state machine — DC5)
TREND_JOB_STATUSES = ["queued", "running", "completed", "failed"]

# Origine d'un keyword dans un snapshot
TREND_SOURCE_KINDS = ["top", "rising", "related", "seed"]

# Provenance d'un seed
TREND_SEED_SOURCES = ["manual", "crm-derived", "provider-derived"]


class TrendCategory(Base, UUIDMixin, TimestampMixin):
    """Referentiel des categories : alimente le selecteur UI et garde un mapping
    stable vers les categories du fournisseur."""

    __tablename__ = "trend_categories"

    # Fournisseur de reference pour le mapping (dataforseo | serpapi | mock)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    # Identifiant de la categorie cote fournisseur (nullable pour mock/global)
    provider_category_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    slug: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    parent_slug: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    seeds: Mapped[list["TrendCategorySeed"]] = relationship(
        back_populates="category", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TrendCategory {self.slug}>"


class TrendCategorySeed(Base, UUIDMixin, TimestampMixin):
    """Termes seeds attaches a une categorie (Deep Research — P4)."""

    __tablename__ = "trend_category_seeds"

    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trend_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    term: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False, default="fr")
    country: Mapped[str] = mapped_column(Text, nullable=False, default="FR")
    # manual | crm-derived | provider-derived
    source: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Relationships
    category: Mapped["TrendCategory"] = relationship(back_populates="seeds")

    def __repr__(self) -> str:
        return f"<TrendCategorySeed {self.term}>"


class TrendJob(Base, UUIDMixin, TimestampMixin):
    """Une execution Trends. request_hash sert a la deduplication (single-flight)."""

    __tablename__ = "trend_jobs"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    # Utilisateur declencheur (SET NULL si l'utilisateur est supprime)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # quick | deep
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    provider_primary: Mapped[str] = mapped_column(Text, nullable=False)
    # Fournisseur reellement utilise (rempli apres execution — peut differer si fallback)
    provider_effective: Mapped[str | None] = mapped_column(Text, nullable=True)
    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    request_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    params_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Progression (expose par GET /jobs/{id})
    steps_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    steps_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    snapshots: Mapped[list["TrendSnapshot"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    report: Mapped["TrendReport | None"] = relationship(
        back_populates="job", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (
        # Dedup / reprise : retrouver un job recent par hash de requete.
        Index("ix_trend_jobs_hash_status", "request_hash", "status"),
    )

    def __repr__(self) -> str:
        return f"<TrendJob {self.id} {self.mode} {self.status}>"


class TrendSnapshot(Base, UUIDMixin):
    """Resultat brut normalise d'un job. Immutable : created_at seul."""

    __tablename__ = "trend_snapshots"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trend_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trend_categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    country: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(Text, nullable=False)
    timeframe: Mapped[str] = mapped_column(Text, nullable=False)
    # Schema interne unique : {timeseries, top_queries, rising_queries,
    # related_topics, regions, metadata} (normalisation fournisseur)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    job: Mapped["TrendJob"] = relationship(back_populates="snapshots")

    def __repr__(self) -> str:
        return f"<TrendSnapshot {self.id}>"


class TrendKeyword(Base, UUIDMixin):
    """Keywords deroules d'un snapshot (tri/filtre/export sans reparser le JSON — P4).

    Immutable : created_at seul.
    """

    __tablename__ = "trend_keywords"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trend_snapshots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    keyword: Mapped[str] = mapped_column(Text, nullable=False)
    cluster: Mapped[str | None] = mapped_column(Text, nullable=True)
    # top | rising | related | seed
    source_kind: Mapped[str] = mapped_column(Text, nullable=False)
    interest_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    growth_score: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    breakout: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provider_meta_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<TrendKeyword {self.keyword} ({self.source_kind})>"


class TrendReport(Base, UUIDMixin):
    """Synthese lisible par le CRM. Un rapport par job. Immutable : created_at seul."""

    __tablename__ = "trend_reports"

    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trend_jobs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    summary_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Signaux structures : market_pulse, rising_queries, top_queries, clusters, regions
    insights_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    opportunity_score: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    job: Mapped["TrendJob"] = relationship(back_populates="report")

    def __repr__(self) -> str:
        return f"<TrendReport {self.id} score={self.opportunity_score}>"
