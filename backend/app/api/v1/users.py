# =============================================================================
# FGA CRM - User Management Routes (admin only)
# =============================================================================

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_admin, get_current_user
from app.core.rbac import apply_tenant_filter, check_tenant_access
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    VALID_ROLES,
    UserActiveToggle,
    UserCreate,
    UserLookupResponse,
    UserRoleUpdate,
)

router = APIRouter()


# Reutiliser le UserResponse + helper de auth.py (DC8)
from app.api.v1.auth import UserResponse, _user_response  # noqa: E402


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Cree un membre DANS l'org de l'admin (l'org vient du serveur, DC18)."""
    exists = await db.scalar(select(User.id).where(User.email == data.email))
    if exists:
        raise HTTPException(status_code=400, detail="Email deja utilise")

    user = User(
        email=data.email,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        role=data.role,
        organization_id=admin.organization_id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return _user_response(user)


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
    """Lister les utilisateurs de l'org de l'admin (bypass super-admin)."""
    query = select(User)
    query = apply_tenant_filter(query, User, admin)

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


# IMPORTANT: declare /lookup AVANT /{user_id} pour que FastAPI ne tente pas
# de parser "lookup" comme un UUID.
@router.get("/lookup", response_model=list[UserLookupResponse])
async def list_users_lookup(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Liste minimale (id + full_name) pour dropdowns/filtres frontend.

    Visibilite (DC6) :
    - admin / manager : tous les users actifs (filtre owner sur Pipeline/Signed/Lost)
    - sales : uniquement leur propre user (un sales ne doit pas voir les autres
      sales, conformement au RBAC ownership de l'app)
    """
    if user.role == "sales":
        return [UserLookupResponse(id=str(user.id), full_name=user.full_name)]

    # DC1 — pas de pagination explicite ici car on attend un nb users < 100 dans
    # un CRM interne. Le `.limit(500)` est un garde-fou defensif (DC1).
    # Isolation multi-tenant : ne lister que les users de l'org du user courant.
    lookup_q = apply_tenant_filter(select(User), User, user)
    result = await db.execute(
        lookup_q
        .where(User.is_active.is_(True))
        .order_by(User.full_name)
        .limit(500)
    )
    users = result.scalars().all()
    return [UserLookupResponse(id=str(u.id), full_name=u.full_name) for u in users]


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
    check_tenant_access(target, admin)  # 404 si user d'une autre org

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
    check_tenant_access(target, admin)  # 404 si user d'une autre org

    # Guard : impossible de retirer le dernier admin de l'org DE LA CIBLE.
    # Compte scope explicitement sur target.organization_id (PAS via le filtre de
    # l'appelant : un super-admin bypasserait et compterait toutes les orgs).
    if target.role == "admin" and data.role != "admin":
        # Compte les admins ACTIFS uniquement (#7) : un admin desactive ne doit pas
        # masquer le fait que la cible est le seul admin operationnel de l'org.
        admin_count = (await db.execute(
            select(func.count()).select_from(User).where(
                User.role == "admin",
                User.is_active.is_(True),
                User.organization_id == target.organization_id,
            )
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
    check_tenant_access(target, admin)  # 404 si user d'une autre org

    # Guard (#7) : ne pas desactiver le dernier admin ACTIF de l'org (sinon plus
    # aucun admin operationnel -> gestion des users verrouillee).
    if target.role == "admin" and not data.is_active:
        active_admins = (await db.execute(
            select(func.count()).select_from(User).where(
                User.role == "admin",
                User.is_active.is_(True),
                User.organization_id == target.organization_id,
            )
        )).scalar() or 0
        if active_admins <= 1:
            raise HTTPException(
                status_code=400, detail="Impossible de desactiver le dernier administrateur actif"
            )

    target.is_active = data.is_active
    await db.flush()
    await db.refresh(target)

    return UserResponse(
        id=str(target.id), email=target.email, full_name=target.full_name,
        role=target.role, is_active=target.is_active, avatar_url=target.avatar_url,
        created_at=target.created_at.isoformat() if target.created_at else None,
    )
