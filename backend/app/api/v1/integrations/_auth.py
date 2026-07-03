# =============================================================================
# FGA CRM - Integrations API : dependances d'auth partagees
# =============================================================================

import uuid

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import security_optional
from app.db.session import get_db
from app.models.user import User


async def require_nomo_key_user(
    x_nomo_api_key: str | None = Header(None),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Auth Nomo-IA : accepte l'ancien header OU le nouveau Bearer crm_xxx.

    Retourne :
    - le `User` proprietaire de la cle API (chemin Bearer crm_xxx) -> l'org de ce
      user fait foi pour l'isolation multi-tenant (DC18 — FIX #6) ;
    - `None` pour le fallback legacy header (secret partage, sans org) : l'appelant
      retombe alors sur le premier admin actif (comportement historique, deprecie).

    Transition : les deux methodes coexistent pendant la migration.
    Supprimer le fallback X-Nomo-API-Key apres 2026-07-01 (1 mois post-migration).
    """
    # Nouveau standard : Bearer crm_xxx
    if credentials and credentials.credentials.startswith("crm_"):
        from app.services.api_keys import validate_api_key
        result = await validate_api_key(db, credentials.credentials)
        if result is not None:
            _, key_user = result
            return key_user  # cle valide -> user (et donc org) de la cle
        raise HTTPException(status_code=401, detail="API key invalide ou expirée")

    # Héritage : X-Nomo-API-Key header (deprecated — supprimer après 2026-07-01)
    if settings.nomo_api_key and x_nomo_api_key == settings.nomo_api_key:
        return None

    if not settings.nomo_api_key:
        raise HTTPException(status_code=503, detail="Nomo-IA integration not configured")
    raise HTTPException(status_code=401, detail="Authentification requise (Bearer crm_xxx ou X-Nomo-API-Key)")


async def require_plein_phare_key_user(
    x_pleinphare_api_key: str | None = Header(None, alias="X-PleinPhare-API-Key"),
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Auth Plein Phare : accepte l'ancien header OU le nouveau Bearer crm_xxx.

    Retourne le `User` de la cle API (chemin Bearer) ou `None` (fallback legacy).
    Voir `require_nomo_key_user` pour la semantique complete (DC18 — FIX #6).

    Transition : les deux methodes coexistent pendant la migration.
    Supprimer le fallback X-PleinPhare-API-Key apres 2026-07-01 (1 mois post-migration).
    """
    # Nouveau standard : Bearer crm_xxx
    if credentials and credentials.credentials.startswith("crm_"):
        from app.services.api_keys import validate_api_key
        result = await validate_api_key(db, credentials.credentials)
        if result is not None:
            _, key_user = result
            return key_user  # cle valide -> user (et donc org) de la cle
        raise HTTPException(status_code=401, detail="API key invalide ou expirée")

    # Héritage : X-PleinPhare-API-Key header (deprecated — supprimer après 2026-07-01)
    if settings.plein_phare_api_key and x_pleinphare_api_key == settings.plein_phare_api_key:
        return None

    if not settings.plein_phare_api_key:
        raise HTTPException(status_code=503, detail="Plein Phare integration not configured")
    raise HTTPException(status_code=401, detail="Authentification requise (Bearer crm_xxx ou X-PleinPhare-API-Key)")


async def resolve_integration_owner(
    db: AsyncSession, key_user: User | None
) -> tuple[User, uuid.UUID]:
    """Resout (owner, org_id) pour un webhook d'integration service-to-service.

    - `key_user` non None (Bearer crm_xxx) : owner = user de la cle, org = son org.
      La destination des ecritures suit STRICTEMENT l'org de la cle authentifiee
      (fin de la fuite cross-org vers l'org du premier admin global — DC18/FIX #6).
    - `key_user` None (legacy header, secret partage sans org) : fallback historique
      sur le premier admin actif global (comportement conserve pour ne pas casser
      les integrations non encore migrees vers une cle crm_xxx).
    """
    if key_user is not None:
        return key_user, key_user.organization_id

    owner = await db.scalar(
        select(User).where(User.role == "admin", User.is_active.is_(True)).limit(1)
    )
    if owner is None:
        raise HTTPException(status_code=503, detail="No admin user found in CRM")
    return owner, owner.organization_id
