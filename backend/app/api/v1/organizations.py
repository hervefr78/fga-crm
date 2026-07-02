# =============================================================================
# FGA CRM - Organization Routes (org courante du user)
# =============================================================================
"""Gestion de l'organisation courante : consultation (tous) + renommage (admin)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_current_user
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import OrganizationResponse, OrganizationUpdate

router = APIRouter()


def _to_response(org: Organization) -> OrganizationResponse:
    return OrganizationResponse(
        id=str(org.id), name=org.name, slug=org.slug, is_active=org.is_active,
    )


@router.get("/me", response_model=OrganizationResponse)
async def get_my_organization(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrganizationResponse:
    org = await db.get(Organization, user.organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation introuvable")
    return _to_response(org)


@router.patch("/me", response_model=OrganizationResponse)
async def rename_my_organization(
    data: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> OrganizationResponse:
    """Renommer son organisation (admin uniquement)."""
    org = await db.get(Organization, admin.organization_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organisation introuvable")
    org.name = data.name.strip()
    await db.flush()
    await db.refresh(org)
    return _to_response(org)
