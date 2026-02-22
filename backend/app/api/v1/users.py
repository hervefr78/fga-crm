# =============================================================================
# FGA CRM - User Management Routes (admin only)
# =============================================================================

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import VALID_ROLES, UserActiveToggle, UserRoleUpdate

router = APIRouter()


# Reutiliser le UserResponse de auth.py (DC8)
from app.api.v1.auth import UserResponse  # noqa: E402


class UserListResponse(UserResponse):
    """Alias pour la liste."""
    pass


# ---------- Endpoints ----------


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    search: str | None = Query(None, max_length=255),
    role: str | None = None,
    is_active: str | None = None,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Lister tous les utilisateurs (admin only)."""
    query = select(User)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            (User.full_name.ilike(search_filter))
            | (User.email.ilike(search_filter))
        )
    if role:
        if role not in VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"Role invalide. Valeurs : {', '.join(sorted(VALID_ROLES))}")
        query = query.where(User.role == role)
    if is_active == "true":
        query = query.where(User.is_active == True)  # noqa: E712
    elif is_active == "false":
        query = query.where(User.is_active == False)  # noqa: E712

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(User.created_at.desc()).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    users = result.scalars().all()

    return {
        "items": [
            UserResponse(
                id=str(u.id), email=u.email, full_name=u.full_name,
                role=u.role, is_active=u.is_active, avatar_url=u.avatar_url,
                created_at=u.created_at.isoformat() if u.created_at else None,
            )
            for u in users
        ],
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size,
    }


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Detail d'un utilisateur (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouve")

    return UserResponse(
        id=str(target.id), email=target.email, full_name=target.full_name,
        role=target.role, is_active=target.is_active, avatar_url=target.avatar_url,
        created_at=target.created_at.isoformat() if target.created_at else None,
    )


@router.patch("/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    data: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Changer le role d'un utilisateur (admin only)."""
    # Guard : impossible de changer son propre role
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Impossible de modifier votre propre role")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouve")

    # Guard : impossible de retirer le dernier admin
    if target.role == "admin" and data.role != "admin":
        admin_count = (await db.execute(
            select(func.count()).select_from(select(User).where(User.role == "admin").subquery())
        )).scalar() or 0
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Impossible de retirer le dernier administrateur")

    target.role = data.role
    await db.flush()
    await db.refresh(target)

    return UserResponse(
        id=str(target.id), email=target.email, full_name=target.full_name,
        role=target.role, is_active=target.is_active, avatar_url=target.avatar_url,
        created_at=target.created_at.isoformat() if target.created_at else None,
    )


@router.patch("/{user_id}/deactivate", response_model=UserResponse)
async def toggle_user_active(
    user_id: uuid.UUID,
    data: UserActiveToggle,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Activer/desactiver un utilisateur (admin only)."""
    # Guard : impossible de se desactiver soi-meme
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Impossible de vous desactiver vous-meme")

    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Utilisateur non trouve")

    target.is_active = data.is_active
    await db.flush()
    await db.refresh(target)

    return UserResponse(
        id=str(target.id), email=target.email, full_name=target.full_name,
        role=target.role, is_active=target.is_active, avatar_url=target.avatar_url,
        created_at=target.created_at.isoformat() if target.created_at else None,
    )
