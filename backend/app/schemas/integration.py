# =============================================================================
# FGA CRM - Integration Schemas (Startup Radar sync)
# =============================================================================

from pydantic import BaseModel, Field


class SyncResultResponse(BaseModel):
    """Resultat d'une synchronisation Startup Radar → CRM."""

    companies_created: int = Field(0, description="Nombre de companies creees (startups)")
    companies_updated: int = Field(0, description="Nombre de companies mises a jour")
    contacts_created: int = Field(0, description="Nombre de contacts crees")
    contacts_updated: int = Field(0, description="Nombre de contacts mis a jour")
    investors_created: int = Field(0, description="Nombre d'investisseurs crees")
    investors_updated: int = Field(0, description="Nombre d'investisseurs mis a jour")
    audits_created: int = Field(0, description="Nombre d'audits importes")
    errors: list[str] = Field(default_factory=list, description="Erreurs rencontrees")


class SyncStatusResponse(BaseModel):
    """Statut de la derniere synchronisation."""

    has_synced: bool = Field(False, description="True si au moins une sync a ete faite")
    last_result: SyncResultResponse | None = Field(None, description="Dernier resultat de sync")
