# =============================================================================
# FGA CRM - Enrichissement : liste d'exclusion (opt-out / bounce)
# =============================================================================
"""SuppressionService (spec §11.5) : consulte avant enrichissement ET avant
safe_to_send. Bloque toute donnee opt-out/bounce."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrichment import EnrichmentSuppression


async def is_suppressed(
    db: AsyncSession,
    *,
    email: str | None = None,
    domain: str | None = None,
    linkedin_url: str | None = None,
) -> bool:
    """True si l'un des identifiants figure dans la liste d'exclusion."""
    conds = []
    if email:
        conds.append(EnrichmentSuppression.email == email.strip().lower())
    if domain:
        conds.append(EnrichmentSuppression.domain == domain.strip().lower())
    if linkedin_url:
        conds.append(EnrichmentSuppression.linkedin_url == linkedin_url.strip())
    if not conds:
        return False
    row = (
        await db.execute(select(EnrichmentSuppression.id).where(or_(*conds)).limit(1))
    ).first()
    return row is not None


async def add_suppression(
    db: AsyncSession,
    *,
    reason: str,
    organization_id=None,
    email: str | None = None,
    domain: str | None = None,
    linkedin_url: str | None = None,
) -> None:
    """Ajoute une entree d'exclusion (opt_out | bounce | manual | bloctel)."""
    db.add(EnrichmentSuppression(
        organization_id=organization_id,
        email=(email or "").strip().lower() or None,
        domain=(domain or "").strip().lower() or None,
        linkedin_url=(linkedin_url or "").strip() or None,
        reason=reason,
    ))
    await db.commit()
