# =============================================================================
# FGA CRM - Company Model
# =============================================================================

import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.contact import Contact
    from app.models.deal import Deal
    from app.models.user import User


class Company(Base, UUIDMixin, OrgScopedMixin, TimestampMixin):
    __tablename__ = "companies"

    # Core info
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Unicite du domaine SCOPEE par organisation (multi-tenant) : voir __table_args__.
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classification
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    size_range: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 1-10, 11-50, 51-200, 201-500, 500+
    revenue_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address_line: Mapped[str | None] = mapped_column(String(500), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Contact info
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Social
    linkedin_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Flexible data
    address: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    custom_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    # Ownership
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Derniere modification — qui a modifie
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Startup Radar link — unicite SCOPEE par organisation (voir __table_args__).
    startup_radar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Provenance du lead (plein-phare, manual, import, linkedin, etc.)
    lead_source: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # N° de TVA intracommunautaire
    vat_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Funding (synced from Startup Radar multi-source pipeline)
    siren: Mapped[str | None] = mapped_column(String(9), nullable=True, index=True)
    funding_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    funding_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)  # euros
    funding_series: Mapped[str | None] = mapped_column(String(50), nullable=True)
    funding_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    owner: Mapped[Optional["User"]] = relationship(back_populates="owned_companies", foreign_keys=[owner_id])
    contacts: Mapped[list["Contact"]] = relationship(back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    deals: Mapped[list["Deal"]] = relationship(back_populates="company", lazy="selectin")
    activities: Mapped[list["Activity"]] = relationship(back_populates="company", lazy="selectin")

    # Isolation multi-tenant : unicite domaine/startup_radar_id SCOPEE par org
    # (jamais globale — sinon deux organisations ne peuvent pas avoir le meme
    # domaine/SR-id, collision cross-org). domain/startup_radar_id nullables ->
    # les NULL restent distincts (plusieurs societes sans domaine par org).
    __table_args__ = (
        UniqueConstraint("organization_id", "domain", name="uq_companies_org_domain"),
        UniqueConstraint("organization_id", "startup_radar_id", name="uq_companies_org_startup_radar_id"),
    )

    def __repr__(self) -> str:
        return f"<Company {self.name}>"
