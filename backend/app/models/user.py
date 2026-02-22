# =============================================================================
# FGA CRM - User Model
# =============================================================================

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
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
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    owned_companies: Mapped[list["Company"]] = relationship(back_populates="owner", lazy="selectin")
    owned_deals: Mapped[list["Deal"]] = relationship(back_populates="owner", lazy="selectin")
    activities: Mapped[list["Activity"]] = relationship(back_populates="user", lazy="selectin")
    tasks: Mapped[list["Task"]] = relationship(back_populates="assigned_to_user", lazy="selectin")
    webauthn_credentials: Mapped[list["WebAuthnCredential"]] = relationship(back_populates="user", cascade="all, delete-orphan", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_manager(self) -> bool:
        return self.role in ("admin", "manager")
