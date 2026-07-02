# =============================================================================
# FGA CRM - Authentication Dependencies
# =============================================================================

import uuid
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import decode_token
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User

# Bearer pour les utilisateurs humains (JWT)
# auto_error=False : on gere l'absence de credentials nous-memes (401 explicite dans
# get_current_user), sinon HTTPBearer renvoie un 403 au lieu d'un 401 sur header manquant.
security = HTTPBearer(auto_error=False)

# Bearer optionnel — utilisé pour la validation de clés API service
security_optional = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Mode dev : bypass auth, retourner le premier admin
    if settings.auth_bypass:
        result = await db.execute(
            select(User).where(User.role == "admin").limit(1)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AUTH_BYPASS actif mais aucun admin en base. Creer un user d'abord.",
            )
        return user

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    # Soft-delete tenant : org desactivee (is_active=false) -> acces bloque.
    org_active = await db.scalar(
        select(Organization.is_active).where(Organization.id == user.organization_id)
    )
    if org_active is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organisation desactivee")

    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def get_current_manager(user: User = Depends(get_current_user)) -> User:
    if not user.is_manager:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Manager access required")
    return user


# =============================================================================
# Service Authentication (API Keys — standard 2026-05)
# =============================================================================


async def get_service_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security_optional),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Valide une API key service et retourne le User associé.

    Lit l'en-tête : Authorization: Bearer crm_<32bytes_hex>
    Stocke les scopes dans request.state.api_key_scopes pour un contrôle fin.
    Retourne 401 si la clé est absente, invalide ou expirée.
    """
    from app.services.api_keys import (
        validate_api_key,  # import tardif pour éviter les cycles
    )

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key service requise (Authorization: Bearer crm_xxx)",
        )

    raw_key = credentials.credentials
    result = await validate_api_key(db, raw_key)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key invalide, révoquée ou expirée",
        )

    api_key, user = result

    # Soft-delete tenant : cle d'un service account dont l'org est desactivee -> 403.
    org_active = await db.scalar(
        select(Organization.is_active).where(Organization.id == user.organization_id)
    )
    if org_active is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organisation desactivee")

    # Stocker les scopes pour require_service_scope
    request.state.api_key_scopes = list(api_key.scopes or [])
    request.state.api_key_name = api_key.name

    return user


def require_service_scope(scope: str) -> Callable[..., Coroutine[Any, Any, User]]:
    """Factory de dépendance FastAPI qui vérifie qu'un scope est présent.

    Usage :
        @router.get("/secret", dependencies=[Depends(require_service_scope("read:deals"))])
    """
    async def _check(
        request: Request,
        user: User = Depends(get_service_user),
    ) -> User:
        scopes: list[str] = getattr(request.state, "api_key_scopes", [])
        # Wildcard : "read:*" donne accès à tout ce qui commence par "read:"
        resource = scope.split(":")[0] if ":" in scope else scope
        wildcard = f"{resource}:*"
        if scope not in scopes and wildcard not in scopes and "read:*" not in scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Scope '{scope}' requis pour cette ressource",
            )
        return user

    return _check
