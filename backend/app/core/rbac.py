# =============================================================================
# FGA CRM - RBAC Helpers (centralises — DC8)
# =============================================================================

from fastapi import HTTPException
from sqlalchemy import Select

from app.models.user import User


def apply_ownership_filter(
    query: Select,
    model: type,
    user: User,
    owner_field: str = "owner_id",
) -> Select:
    """Filtrer les listes par proprietaire pour les sales.

    Admin et manager voient toutes les entites (bypass).
    """
    if user.is_manager:  # True pour admin ET manager
        return query
    return query.where(getattr(model, owner_field) == user.id)


def check_entity_access(
    entity: object,
    user: User,
    owner_field: str = "owner_id",
) -> None:
    """Lever 403 si un sales n'est pas proprietaire de l'entite.

    Admin et manager ont acces a tout (bypass).
    """
    if user.is_manager:
        return
    entity_owner = getattr(entity, owner_field)
    if entity_owner != user.id:
        raise HTTPException(
            status_code=403,
            detail="Acces non autorise a cette ressource",
        )


# =============================================================================
# Isolation multi-tenant (row-level) — centralise (DC8)
# =============================================================================
# Applique a TOUS les roles (admin inclus : admin de SON org, pas cross-org).
# Le super-admin (staff FGA/Compass) bypasse le filtre tenant.
# S'imbrique AVANT le filtre d'ownership sales (apply_ownership_filter).


def apply_tenant_filter(query: Select, model: type, user: User) -> Select:
    """Restreindre une liste a l'organisation du user (bypass super-admin)."""
    if user.is_superadmin:
        return query
    return query.where(model.organization_id == user.organization_id)


def check_tenant_access(entity: object, user: User) -> None:
    """Lever 404 si l'entite n'appartient pas a l'org du user.

    404 (pas 403) volontaire : ne pas divulguer l'existence d'une ressource
    d'une autre organisation. Bypass super-admin.
    """
    if user.is_superadmin:
        return
    if getattr(entity, "organization_id", None) != user.organization_id:
        raise HTTPException(status_code=404, detail="Ressource introuvable")
