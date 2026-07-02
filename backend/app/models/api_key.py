# =============================================================================
# FGA CRM - Modele ApiKey (Service Authentication Standard 2026-05)
# =============================================================================
# Chaque clé API est associée à un service account (User.is_service=True).
# La clé brute n'est JAMAIS stockée — uniquement son SHA-256 (key_hash).
# Préfixe de clé : crm_<32_bytes_hex>
# Doc : ~/Documents/Claude/docs/SERVICE_AUTH_STANDARD.md

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class ApiKey(UUIDMixin, OrgScopedMixin, TimestampMixin, Base):
    """Clé API pour accès service-to-service."""

    __tablename__ = "api_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Ex : ["read:*"] ou ["write:contacts", "write:companies"]
    scopes: Mapped[list] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relation vers le service account (User avec is_service=True)
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], lazy="selectin")
