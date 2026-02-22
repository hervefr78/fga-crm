# =============================================================================
# FGA CRM - Schemas Recherche Globale
# =============================================================================

from pydantic import BaseModel


class SearchResultItem(BaseModel):
    """Un resultat de recherche globale."""
    id: str
    label: str
    sub: str | None = None


class GlobalSearchResponse(BaseModel):
    """Reponse de la recherche globale multi-entites."""
    contacts: list[SearchResultItem]
    companies: list[SearchResultItem]
    deals: list[SearchResultItem]
