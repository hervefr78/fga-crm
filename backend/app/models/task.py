# =============================================================================
# FGA CRM - Task Model
# =============================================================================

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.contact import Contact
    from app.models.deal import Deal
    from app.models.user import User


class Task(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tasks"

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[str] = mapped_column(String(50), default="todo", nullable=False)  # todo, call, email, meeting
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)  # low, medium, high, urgent
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Foreign keys
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    deal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    assigned_to_user: Mapped[Optional["User"]] = relationship(back_populates="tasks", lazy="selectin")
    contact: Mapped[Optional["Contact"]] = relationship(lazy="selectin")
    deal: Mapped[Optional["Deal"]] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return f"<Task {self.title}>"
