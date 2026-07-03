# =============================================================================
# FGA CRM - Contact Model
# =============================================================================

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.company import Company
    from app.models.deal import Deal
    from app.models.task import Task


class Contact(Base, UUIDMixin, OrgScopedMixin, TimestampMixin):
    __tablename__ = "contacts"

    # Company link
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Identity
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    email_status: Mapped[str | None] = mapped_column(String(50), nullable=True)  # valid, invalid, risky, unknown
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Professional
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)  # CEO, CTO, VP Sales...
    job_level: Mapped[str | None] = mapped_column(String(50), nullable=True)  # C-Level, VP, Director, Manager, IC, Other
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Sales, Marketing, Engineering...
    is_decision_maker: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # LinkedIn
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    linkedin_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # CRM status
    status: Mapped[str] = mapped_column(
        String(50), default="new", server_default="new", nullable=False, index=True
    )  # new, contacted, qualified, unqualified, nurturing

    # Lead scoring (0-100, AI-computed)
    lead_score: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)

    # Source & Tracking
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)  # linkedin, website, referral, event, import...
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Flexible data
    custom_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    tags: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)

    # Ownership
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Derniere modification — qui a modifie
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Integration — Startup Radar. Unicite SCOPEE par org (voir __table_args__).
    startup_radar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Enrichment metadata (synced from Startup Radar multi-source pipeline)
    # enrichment_source : sirene, scraping, scraped_founders, manual, etc.
    enrichment_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # email_pattern_used : first.last, f.last, firstlast, etc. (uniquement si email genere heuristiquement)
    email_pattern_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # linkedin_url_status : candidate (genere auto), verified (verifie manuellement), invalid
    linkedin_url_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # True si l'email a ete trouve/verifie par Icypeas (vs saisi/importe manuellement).
    email_verified_by_icypeas: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False
    )

    # Relationships
    company: Mapped[Optional["Company"]] = relationship(back_populates="contacts")
    # lazy="select" (lazy-on-access) : collections jamais serialisees depuis l'objet
    # Contact (reponses via champs explicites / selectinload cible). Evite l'eager-load.
    deals: Mapped[list["Deal"]] = relationship(back_populates="contact", lazy="select")
    activities: Mapped[list["Activity"]] = relationship(back_populates="contact", lazy="select")
    tasks: Mapped[list["Task"]] = relationship(back_populates="contact", lazy="select")

    # Isolation multi-tenant : unicite startup_radar_id SCOPEE par org (jamais
    # globale — sinon deux orgs ne peuvent pas importer le meme lead SR).
    __table_args__ = (
        UniqueConstraint("organization_id", "startup_radar_id", name="uq_contacts_org_startup_radar_id"),
    )

    def __repr__(self) -> str:
        return f"<Contact {self.first_name} {self.last_name}>"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
