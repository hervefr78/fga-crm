# =============================================================================
# FGA CRM - Tag Model (polymorphic tagging)
# =============================================================================

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Tag(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    color: Mapped[str] = mapped_column(String(7), default="#6366f1", nullable=False)  # hex color


class TagAssignment(Base, UUIDMixin, TimestampMixin):
    """Polymorphic tag assignment: links tags to companies, contacts, or deals."""
    __tablename__ = "tag_assignments"

    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # company, contact, deal
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
