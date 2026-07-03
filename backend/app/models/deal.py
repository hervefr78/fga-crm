# =============================================================================
# FGA CRM - Deal Model
# =============================================================================

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.company import Company
    from app.models.contact import Contact
    from app.models.user import User

# Pipeline stages
DEAL_STAGES = ["new", "contacted", "meeting", "proposal", "negotiation", "won", "lost"]

# Categories pour separer pipeline / signes / perdus dans l'UI (DC8 — source unique)
PIPELINE_STAGES = ["new", "contacted", "meeting", "proposal", "negotiation"]
SIGNED_STAGES = ["won"]
LOST_STAGES = ["lost"]
DEAL_CATEGORIES: dict[str, list[str]] = {
    "pipeline": PIPELINE_STAGES,
    "signed": SIGNED_STAGES,
    "lost": LOST_STAGES,
}

# Types de pricing supportes (one-shot ou recurrent)
PRICING_TYPES = ["one_shot", "monthly", "quarterly", "biannual", "annual"]

# Conversion d'une periode recurrente en nombre de mois (pour normaliser le MRR)
PERIOD_TO_MONTHS: dict[str, int] = {"monthly": 1, "quarterly": 3, "biannual": 6, "annual": 12}


class Deal(Base, UUIDMixin, OrgScopedMixin, TimestampMixin):
    __tablename__ = "deals"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pipeline
    stage: Mapped[str] = mapped_column(String(50), default="new", nullable=False, index=True)
    stage_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Financials
    amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    probability: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100

    # Dates
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Close info
    loss_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)  # low, medium, high, urgent

    # Position in kanban
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Pricing recurrent (DC1 borne en schema, default safe one_shot)
    pricing_type: Mapped[str] = mapped_column(
        String(20), default="one_shot", nullable=False, index=True
    )
    recurring_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    commitment_months: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Flexible
    custom_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    # Foreign keys
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Relationships
    company: Mapped[Optional["Company"]] = relationship(back_populates="deals")
    contact: Mapped[Optional["Contact"]] = relationship(back_populates="deals")
    owner: Mapped[Optional["User"]] = relationship(back_populates="owned_deals")
    # lazy="select" (lazy-on-access) : collection jamais serialisee depuis l'objet
    # Deal (reponses via champs explicites / selectinload cible). Evite l'eager-load.
    activities: Mapped[list["Activity"]] = relationship(back_populates="deal", lazy="select")

    def __repr__(self) -> str:
        return f"<Deal {self.title} ({self.stage})>"
