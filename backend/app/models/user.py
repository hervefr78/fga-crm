# =============================================================================
# FGA CRM - User Model
# =============================================================================

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.company import Company
    from app.models.deal import Deal
    from app.models.task import Task
    from app.models.webauthn_credential import WebAuthnCredential


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="sales", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Service accounts (mcp@crm.internal, nomo-ia@crm.internal) — ne peuvent pas se connecter via UI
    is_service: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    # Multi-tenant : org d'appartenance (NOT NULL depuis le contract mt_contract_001).
    # RESTRICT : soft-delete des orgs (Organization.is_active=false), pas de wipe physique.
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Super-admin cross-org (staff FGA/Compass) : bypass le filtre tenant.
    is_superadmin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    # lazy="select" (lazy-on-access) : ces collections ne sont jamais serialisees
    # depuis l'objet User (reponses construites via champs explicites / selectinload
    # cible). Evite un eager-load massif a chaque chargement d'un User.
    owned_companies: Mapped[list["Company"]] = relationship(back_populates="owner", foreign_keys="[Company.owner_id]", lazy="select")
    owned_deals: Mapped[list["Deal"]] = relationship(back_populates="owner", lazy="select")
    activities: Mapped[list["Activity"]] = relationship(back_populates="user", lazy="select")
    tasks: Mapped[list["Task"]] = relationship(back_populates="assigned_to_user", lazy="select")
    webauthn_credentials: Mapped[list["WebAuthnCredential"]] = relationship(back_populates="user", cascade="all, delete-orphan", lazy="select")

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_manager(self) -> bool:
        return self.role in ("admin", "manager")
