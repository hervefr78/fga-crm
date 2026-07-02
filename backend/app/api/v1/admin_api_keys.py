# =============================================================================
# FGA CRM - Endpoints admin : gestion des API keys service-to-service
# =============================================================================
# POST   /api/v1/admin/api-keys          — créer (raw_key retournée UNE SEULE FOIS)
# GET    /api/v1/admin/api-keys          — lister
# DELETE /api/v1/admin/api-keys/{id}     — révoquer (soft delete)
# POST   /api/v1/admin/api-keys/service-accounts — créer un service account
#
# Accès : admin uniquement (get_current_admin)

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin
from app.core.rbac import apply_tenant_filter, check_tenant_access
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.user import User
from app.services.api_keys import (
    create_api_key,
    get_or_create_service_account,
    revoke_api_key,
)

router = APIRouter()


# --- Schemas ---


class CreateApiKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Identifiant lisible, ex: 'mcp-prod'")
    user_id: uuid.UUID = Field(..., description="UUID du service account associé")
    scopes: list[str] = Field(default_factory=list, description="Ex: ['read:*'] ou ['write:contacts']")
    expires_at: datetime | None = Field(None, description="Expiration ISO (None = pas d'expiration)")


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    user_id: uuid.UUID
    scopes: list[str]
    is_active: bool
    last_used_at: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None
    created_at: str

    model_config = {"from_attributes": True}


class CreateApiKeyResponse(BaseModel):
    """Retournée UNE SEULE FOIS — contient la clé brute."""

    id: uuid.UUID
    name: str
    key: str  # raw_key : crm_<64chars_hex>


class CreateServiceAccountRequest(BaseModel):
    email: EmailStr = Field(..., description="Ex: mcp@crm.internal")
    full_name: str = Field(..., min_length=1, max_length=255)


class ServiceAccountOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_service: bool

    model_config = {"from_attributes": True}


# --- Endpoints ---


@router.post("", response_model=CreateApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: CreateApiKeyRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> CreateApiKeyResponse:
    """Crée une API key pour un service account. La clé brute est retournée UNE SEULE FOIS."""
    # Le service account cible doit appartenir a l'org de l'admin (anti cross-org).
    sa_result = await db.execute(select(User).where(User.id == body.user_id))
    service_account = sa_result.scalar_one_or_none()
    if not service_account:
        raise HTTPException(status_code=404, detail="Service account introuvable")
    check_tenant_access(service_account, admin)

    # create_api_key derive l'org depuis le user proprietaire (DC18) -> pas de tag ici.
    api_key, raw_key = await create_api_key(
        db=db,
        user_id=body.user_id,
        name=body.name,
        scopes=body.scopes,
        expires_at=body.expires_at,
    )
    await db.commit()
    return CreateApiKeyResponse(id=api_key.id, name=api_key.name, key=raw_key)


@router.get("", response_model=list[ApiKeyOut])
async def list_keys(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> list[ApiKeyOut]:
    """Liste les API keys de l'org de l'admin (actives et révoquées, bypass super-admin)."""
    # NB : le service list_api_keys(db) ne filtre pas par org — on requete ici
    # directement avec apply_tenant_filter pour garantir l'isolation (DC18).
    keys_q = apply_tenant_filter(
        select(ApiKey).order_by(ApiKey.created_at.desc()), ApiKey, admin
    )
    keys = list((await db.execute(keys_q)).scalars().all())
    return [
        ApiKeyOut(
            id=k.id,
            name=k.name,
            user_id=k.user_id,
            scopes=list(k.scopes or []),
            is_active=k.is_active,
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            revoked_at=k.revoked_at.isoformat() if k.revoked_at else None,
            created_at=k.created_at.isoformat(),
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def revoke_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> None:
    """Révoque une API key (soft-delete : is_active=False + revoked_at)."""
    # Verifier l'appartenance a l'org AVANT de reveler l'existence de la cle (DC18).
    key_result = await db.execute(select(ApiKey).where(ApiKey.id == key_id))
    api_key = key_result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status_code=404, detail="Clé API introuvable ou déjà révoquée")
    check_tenant_access(api_key, admin)  # 404 si cle d'une autre org

    found = await revoke_api_key(db, key_id)
    if not found:
        raise HTTPException(status_code=404, detail="Clé API introuvable ou déjà révoquée")
    await db.commit()


@router.post(
    "/service-accounts",
    response_model=ServiceAccountOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_service_account(
    body: CreateServiceAccountRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> ServiceAccountOut:
    """Crée (ou retourne) un service account.

    Les service accounts ont is_service=True et ne peuvent pas se connecter via l'UI.
    Associer ensuite une API key via POST /admin/api-keys.
    """
    # Nouveau compte -> cree dans l'org de l'admin (DC18). Compte existant dans une
    # autre org -> refuse (check_tenant_access, anti-collision cross-org).
    user = await get_or_create_service_account(
        db, body.email, body.full_name, admin.organization_id
    )
    check_tenant_access(user, admin)
    await db.commit()
    return ServiceAccountOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_service=user.is_service,
    )
