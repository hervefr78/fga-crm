# =============================================================================
# FGA CRM - GEO Routes : deps et helpers partages
# =============================================================================
"""Dependances RBAC et helpers communs du module GEO.

Importes par les sous-routers (brands, prompts, runs, dashboard, gaps, health).
"""

import uuid
from datetime import date

from fastapi import Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.rbac import check_tenant_access
from app.models.geo import GeoBrand, GeoPrompt
from app.models.user import User

# Mapping moteur -> attribut settings de la cle API (DC8 — source unique)
ENGINE_API_KEY_ATTR: dict[str, str] = {
    "perplexity": "perplexity_api_key",
    "openai": "openai_api_key",
    "gemini": "gemini_api_key",
    "claude": "claude_api_key",
    "google_aio": "serpapi_key",
    # "grok" : pas de cle dediee en settings (P3) — considere non configure
}


# ---------------------------------------------------------------------------
# RBAC helpers
# ---------------------------------------------------------------------------

def _require_geo_access(user: User = Depends(get_current_user)) -> User:
    if user.role == "sales":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Module GEO : acces reserve admin et manager",
        )
    return user


def _require_geo_admin(user: User = Depends(get_current_user)) -> User:
    if user.role not in ("admin",):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Module GEO : action reservee aux admins",
        )
    return user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_uuid(value: str, field_name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail=f"{field_name} invalide")


def _parse_iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422, detail=f"{field_name} doit etre une date ISO YYYY-MM-DD"
        )


def _engine_configured(engine: str) -> bool:
    """True si la cle API du moteur est presente dans settings."""
    attr = ENGINE_API_KEY_ATTR.get(engine)
    if attr is None:
        return False
    return bool(getattr(settings, attr, None))


async def _get_brand_or_404(
    db: AsyncSession, brand_id: uuid.UUID, user: User
) -> GeoBrand:
    brand = (
        await db.execute(select(GeoBrand).where(GeoBrand.id == brand_id))
    ).scalar_one_or_none()
    if brand is None:
        raise HTTPException(status_code=404, detail="Marque GEO introuvable")
    # Isolation multi-tenant : 404 si la marque est hors organisation (bypass super-admin)
    check_tenant_access(brand, user)
    return brand


async def _get_prompt_or_404(
    db: AsyncSession, brand_id: uuid.UUID, prompt_id: uuid.UUID, user: User
) -> GeoPrompt:
    prompt = (
        await db.execute(
            select(GeoPrompt).where(
                and_(GeoPrompt.id == prompt_id, GeoPrompt.brand_id == brand_id)
            )
        )
    ).scalar_one_or_none()
    if prompt is None:
        raise HTTPException(status_code=404, detail="Prompt GEO introuvable")
    # Isolation multi-tenant : 404 si le prompt est hors organisation (bypass super-admin)
    check_tenant_access(prompt, user)
    return prompt
