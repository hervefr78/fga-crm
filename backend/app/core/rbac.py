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
