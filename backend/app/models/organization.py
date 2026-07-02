# =============================================================================
# FGA CRM - Organization Model (multi-tenant, socle Compass)
# =============================================================================
"""Tenant racine. Chaque entite metier appartient a une organisation
(`OrgScopedMixin`). L'existant mono-tenant est backfille vers l'org par defaut
ci-dessous lors de la migration d'isolation."""

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin

# Org par defaut : recoit toutes les donnees existantes (deploiement mono-tenant
# FGA historique). UUID fixe -> backfill deterministe et identique dev/prod.
DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-0000000000fa")
DEFAULT_ORG_NAME = "Fast Growth Advisor"
DEFAULT_ORG_SLUG = "fga"


class Organization(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Organization {self.slug}>"
