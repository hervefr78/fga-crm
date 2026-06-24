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
    # Funding multi-source (Phase B 2026-05)
    funding_activities_created: int = Field(
        0, description="Nombre d'Activity 'funding_detected' crees"
    )
    qualification_tasks_created: int = Field(
        0, description="Nombre de Task 'qualification' creees pour qualifier la levee"
    )
    errors: list[str] = Field(default_factory=list, description="Erreurs rencontrees")


class CompanyAuditResponse(BaseModel):
    """Resultat du lancement d'un audit avance sur une entreprise."""

    audits_created: int = Field(0, description="Nombre d'audits crees")
    audits_skipped: int = Field(0, description="Nombre d'audits deja existants")
    errors: list[str] = Field(default_factory=list, description="Erreurs rencontrees")


class SyncStatusResponse(BaseModel):
    """Statut de la full sync Startup Radar (stocke dans Redis).

    `status` (DC5 — etats exhaustifs) :
    - idle       : aucune sync n'a jamais tourne
    - running    : une sync est en cours (le frontend poll)
    - completed  : derniere sync terminee (resultat dans last_result)
    - failed     : derniere sync a echoue (detail dans error)
    """

    has_synced: bool = Field(False, description="True si une sync s'est deja terminee")
    status: str = Field("idle", description="idle | running | completed | failed")
    started_at: str | None = Field(None, description="ISO — debut de la sync en cours/derniere")
    finished_at: str | None = Field(None, description="ISO — fin de la derniere sync")
    error: str | None = Field(None, description="Message d'erreur si status=failed")
    last_result: SyncResultResponse | None = Field(None, description="Dernier resultat de sync")


class SyncEnqueuedResponse(BaseModel):
    """Reponse 202 du lancement d'une full sync (tache de fond)."""

    status: str = Field("running", description="Statut initial du job")
    job_id: str = Field(..., description="Identifiant du job de sync")
    started_at: str = Field(..., description="ISO — horodatage du lancement")
