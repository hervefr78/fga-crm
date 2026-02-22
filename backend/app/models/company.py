# =============================================================================
# FGA CRM - Company Model
# =============================================================================

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.contact import Contact
    from app.models.deal import Deal
    from app.models.user import User


class Company(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "companies"

    # Core info
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Classification
    industry: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    size_range: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 1-10, 11-50, 51-200, 201-500, 500+
    revenue_range: Mapped[str | None] = mapped_column(String(50), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)

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

    # Startup Radar link
    startup_radar_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)

    # Relationships
    owner: Mapped[Optional["User"]] = relationship(back_populates="owned_companies")
    contacts: Mapped[list["Contact"]] = relationship(back_populates="company", cascade="all, delete-orphan", lazy="selectin")
    deals: Mapped[list["Deal"]] = relationship(back_populates="company", lazy="selectin")
    activities: Mapped[list["Activity"]] = relationship(back_populates="company", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Company {self.name}>"
