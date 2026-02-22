# =============================================================================
# FGA CRM - EmailTemplate Model
# =============================================================================

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class EmailTemplate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "email_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)

    # Ownership
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # Relationships
    owner: Mapped["User"] = relationship()

    def __repr__(self) -> str:
        return f"<EmailTemplate {self.name}>"
