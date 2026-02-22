# =============================================================================
# FGA CRM - Schemas communs
# =============================================================================

from pydantic import BaseModel, Field


class PaginatedParams(BaseModel):
    """Parametres de pagination bornes (DC1)."""

    page: int = Field(1, ge=1, description="Numero de page")
    size: int = Field(25, ge=1, le=100, description="Nombre d'elements par page")
