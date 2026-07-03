# =============================================================================
# FGA CRM - Integration Schemas (Startup Radar sync)
# =============================================================================

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


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
    """Resultat de l'import d'un audit avance sur une entreprise."""

    audits_created: int = Field(0, description="Nombre d'audits crees")
    audits_skipped: int = Field(0, description="Nombre d'audits deja existants")
    errors: list[str] = Field(default_factory=list, description="Erreurs rencontrees")


class AuditGenerateResponse(BaseModel):
    """Reponse au declenchement d'un audit SR (genere en arriere-plan cote SR)."""

    status: str = Field(..., description="running")
    message: str = Field("", description="Message informatif")


class AuditGenerateStatusResponse(BaseModel):
    """Statut de generation d'un audit SR (proxy du statut SR).

    `status` (DC5) : idle (aucun en cours) | running | completed | failed.
    """

    status: str = Field("idle", description="idle | running | completed | failed")
    step: str = Field("", description="Etape courante du pipeline SR")
    error: str | None = Field(None, description="Message d'erreur si status=failed")


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


# ---------- Schemas Nomo-IA ----------


class NomoNewSubscriptionRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field("", max_length=255)
    email: str = Field(..., max_length=255)
    phone: str | None = Field(None, max_length=50)
    address_line: str | None = Field(None, max_length=500)
    postal_code: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    plan: str = Field(..., max_length=100)
    amount_eur: float = Field(..., ge=0)
    billing_cycle: str = Field("monthly", max_length=20)
    subscription_date: str = Field(..., max_length=30)


class NomoNewSubscriptionResponse(BaseModel):
    company_id: str
    contact_id: str
    deal_id: str


# ---------- Schemas Plein Phare Digital ----------


class PleinPhareNewOrderRequest(BaseModel):
    """Webhook entrant : nouvelle commande "Rapport Complet" one-shot."""

    email: EmailStr
    first_name: str | None = Field(None, max_length=255)
    last_name: str | None = Field(None, max_length=255)
    company_name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = Field(None, max_length=50)
    address_line: str | None = Field(None, max_length=500)
    postal_code: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=100)
    country: str | None = Field("France", max_length=100)
    amount_eur: float = Field(..., ge=0)
    currency: str = Field("EUR", max_length=3)
    audit_order_id: str = Field(..., min_length=1, max_length=64)
    audit_url: str | None = Field(None, max_length=2048)
    paid_at: datetime
    stripe_session_id: str | None = Field(None, max_length=255)


class PleinPhareCreatedFlags(BaseModel):
    company: bool
    contact: bool
    deal: bool


class PleinPhareNewOrderResponse(BaseModel):
    company_id: str
    contact_id: str
    deal_id: str
    created: PleinPhareCreatedFlags


class PleinPhareRefundRequest(BaseModel):
    audit_order_id: str = Field(..., min_length=1, max_length=64)
    refunded_at: datetime
    reason: str | None = Field(None, max_length=500)


class PleinPhareRefundResponse(BaseModel):
    deal_id: str
    old_stage: str
    new_stage: str
