# =============================================================================
# FGA CRM - Contact Model
# =============================================================================

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User
    from app.models.deal import Deal
    from app.models.activity import Activity
    from app.models.task import Task


class Contact(Base, UUIDMixin, TimestampMixin):
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

    # Relationships
    company: Mapped[Optional["Company"]] = relationship(back_populates="contacts")
    deals: Mapped[List["Deal"]] = relationship(back_populates="contact", lazy="selectin")
    activities: Mapped[List["Activity"]] = relationship(back_populates="contact", lazy="selectin")
    tasks: Mapped[List["Task"]] = relationship(back_populates="contact", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Contact {self.first_name} {self.last_name}>"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()
