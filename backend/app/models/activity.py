# =============================================================================
# FGA CRM - Activity Model
# =============================================================================

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.company import Company
    from app.models.deal import Deal
    from app.models.user import User

# Activity types
ACTIVITY_TYPES = ["email", "call", "meeting", "note", "linkedin", "task"]


class Activity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "activities"

    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # email, call, meeting, note, linkedin
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)  # duration, direction, etc.

    # Foreign keys
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=True, index=True
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Relationships
    contact: Mapped[Optional["Contact"]] = relationship(back_populates="activities")
    company: Mapped[Optional["Company"]] = relationship(back_populates="activities")
    deal: Mapped[Optional["Deal"]] = relationship(back_populates="activities")
    user: Mapped["User"] = relationship(back_populates="activities")

    def __repr__(self) -> str:
        return f"<Activity {self.type}: {self.subject}>"
