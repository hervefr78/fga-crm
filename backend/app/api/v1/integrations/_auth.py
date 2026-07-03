# =============================================================================
# FGA CRM - Integrations API : dependances d'auth partagees
# =============================================================================

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import security_optional
from app.db.session import get_db


async def _require_nomo_api_key(
    x_nomo_api_key: str | None = Header(None),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Auth Nomo-IA : accepte l'ancien header OU le nouveau Bearer crm_xxx.

    Transition : les deux méthodes coexistent pendant la migration.
    Supprimer le fallback X-Nomo-API-Key après 2026-07-01 (1 mois post-migration).
    """
    # Nouveau standard : Bearer crm_xxx
    if credentials and credentials.credentials.startswith("crm_"):
        from app.services.api_keys import validate_api_key
        result = await validate_api_key(db, credentials.credentials)
        if result is not None:
            return  # Clé valide
        raise HTTPException(status_code=401, detail="API key invalide ou expirée")

    # Héritage : X-Nomo-API-Key header (deprecated — supprimer après 2026-07-01)
    if settings.nomo_api_key and x_nomo_api_key == settings.nomo_api_key:
        return

    if not settings.nomo_api_key:
        raise HTTPException(status_code=503, detail="Nomo-IA integration not configured")
    raise HTTPException(status_code=401, detail="Authentification requise (Bearer crm_xxx ou X-Nomo-API-Key)")


async def _require_plein_phare_api_key(
    x_pleinphare_api_key: str | None = Header(None, alias="X-PleinPhare-API-Key"),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Auth Plein Phare : accepte l'ancien header OU le nouveau Bearer crm_xxx.

    Transition : les deux méthodes coexistent pendant la migration.
    Supprimer le fallback X-PleinPhare-API-Key après 2026-07-01 (1 mois post-migration).
    """
    # Nouveau standard : Bearer crm_xxx
    if credentials and credentials.credentials.startswith("crm_"):
        from app.services.api_keys import validate_api_key
        result = await validate_api_key(db, credentials.credentials)
        if result is not None:
            return  # Clé valide
        raise HTTPException(status_code=401, detail="API key invalide ou expirée")

    # Héritage : X-PleinPhare-API-Key header (deprecated — supprimer après 2026-07-01)
    if settings.plein_phare_api_key and x_pleinphare_api_key == settings.plein_phare_api_key:
        return

    if not settings.plein_phare_api_key:
        raise HTTPException(status_code=503, detail="Plein Phare integration not configured")
    raise HTTPException(status_code=401, detail="Authentification requise (Bearer crm_xxx ou X-PleinPhare-API-Key)")
