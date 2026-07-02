# =============================================================================
# FGA CRM - Modeles Enrichissement d'emails B2B (feature Compass)
# =============================================================================
"""Modeles de la feature d'enrichissement d'emails B2B (brique Compass).

Ne DUPLIQUE pas companies/contacts (source de verite CRM) : la sortie du pipeline
cree/enrichit des `contacts`. Ces tables ne portent que l'ETAT propre a
l'enrichissement (jobs, provenance RGPD, suppression, verifications email).

Multi-tenant : `organization_id` present des le depart (nullable — convention
GEO/Trends ; deviendra reel avec le multi-tenant Compass).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

# Enums applicatifs (source unique — DC8). Colonnes Text ; enums Pydantic cote schemas.
ENRICHMENT_ROLES = ["CTO", "CPO", "CMO", "FOUNDER", "OTHER"]
DOMAIN_TYPES = ["pro", "personal", "generic"]
VERIFICATION_STATUSES = ["valid", "catch_all", "risky", "invalid"]
ENRICHMENT_SOURCES = [
    "plein_phare", "startup_radar", "crm", "icypeas",
    "unipile", "millionverifier", "manual", "mock",
]
SUPPRESSION_REASONS = ["opt_out", "bounce", "manual", "bloctel"]
ENRICHMENT_MODES = ["company", "batch", "icp"]
ENRICHMENT_JOB_STATUSES = ["queued", "running", "done", "failed"]
LEGAL_BASIS_LEGITIMATE_INTEREST = "legitimate_interest"


class EnrichmentJob(Base, UUIDMixin, TimestampMixin):
    """Une execution d'enrichissement (mode company | batch | icp)."""

    __tablename__ = "enrichment_jobs"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # company | batch | icp
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    # TargetSpec serialise (siren | sirens[] | icpFilter)
    target_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # queued | running | done | failed
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    # compteurs : people_found, emails_found, valid_count, credits_spent...
    stats_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_enrichment_jobs_org_status", "organization_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<EnrichmentJob {self.id} {self.mode} {self.status}>"


class EnrichmentProvenance(Base, UUIDMixin):
    """Traçabilité RGPD : d'ou vient chaque donnee (nom/email/titre). Immuable."""

    __tablename__ = "enrichment_provenance"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    # person | email
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    # name | email | title | linkedin
    field: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    legal_basis: Mapped[str] = mapped_column(
        Text, nullable=False, default=LEGAL_BASIS_LEGITIMATE_INTEREST
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_enrichment_provenance_contact", "contact_id"),
    )

    def __repr__(self) -> str:
        return f"<EnrichmentProvenance {self.field} <- {self.source}>"


class EnrichmentSuppression(Base, UUIDMixin, TimestampMixin):
    """Liste d'exclusion : opt-out / bounce / manuel / bloctel."""

    __tablename__ = "enrichment_suppression"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    email: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    domain: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # opt_out | bounce | manual | bloctel
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return f"<EnrichmentSuppression {self.email or self.domain} ({self.reason})>"


class EnrichmentEmailVerification(Base, UUIDMixin, TimestampMixin):
    """Statut de verification d'un email rattache a un contact."""

    __tablename__ = "enrichment_email_verifications"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True
    )
    email: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    # pro | personal | generic
    domain_type: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    # valid | catch_all | risky | invalid
    status: Mapped[str] = mapped_column(Text, nullable=False)
    deliverable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    verified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<EnrichmentEmailVerification {self.email} {self.status}>"
