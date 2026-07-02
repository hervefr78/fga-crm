# =============================================================================
# FGA CRM - Auth Routes
# =============================================================================

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.organization import Organization
from app.models.user import User

router = APIRouter()


def _slugify(name: str) -> str:
    """Slug d'org unique : base alphanumerique + suffixe court (evite les collisions)."""
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:80] or "org"
    return f"{base}-{uuid.uuid4().hex[:6]}"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    # Nom de l'organisation creee a l'inscription (defaut derive du nom complet).
    organization_name: str | None = Field(None, max_length=255)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UpdateProfileRequest(BaseModel):
    full_name: str | None = Field(None, min_length=1, max_length=255)
    avatar_url: str | None = Field(None, max_length=500)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    organization_id: str | None = None
    is_superadmin: bool = False
    avatar_url: str | None = None
    created_at: str | None = None

    class Config:
        from_attributes = True


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id), email=user.email, full_name=user.full_name,
        role=user.role, is_active=user.is_active,
        organization_id=str(user.organization_id) if user.organization_id else None,
        is_superadmin=user.is_superadmin,
        avatar_url=user.avatar_url,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    # Multi-tenant : chaque inscription cree une NOUVELLE organisation dont le
    # user devient admin. L'ajout d'autres users se fait via un admin dans l'org.
    org_name = (data.organization_name or "").strip() or f"{data.full_name.strip()} — Organisation"
    org = Organization(name=org_name, slug=_slugify(org_name))
    db.add(org)
    await db.flush()  # obtenir org.id avant de creer le user

    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role="admin",
        organization_id=org.id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return _user_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account deactivated")

    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    return TokenResponse(
        access_token=create_access_token({"sub": str(user.id)}),
        refresh_token=create_refresh_token({"sub": str(user.id)}),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return _user_response(user)


@router.put("/me", response_model=UserResponse)
async def update_profile(
    data: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    update_data = data.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=422, detail="Aucun champ a mettre a jour")

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)

    return _user_response(user)


@router.post("/change-password", status_code=200)
async def change_password(
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Mot de passe actuel incorrect")

    user.hashed_password = hash_password(data.new_password)
    await db.flush()

    return {"message": "Mot de passe modifie avec succes"}
