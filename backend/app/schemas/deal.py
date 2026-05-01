# =============================================================================
# FGA CRM - Schemas Deal
# =============================================================================


from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.deal import DEAL_STAGES, PRICING_TYPES

# Valeurs autorisees (DC1)
DEAL_PRIORITIES = {"low", "medium", "high", "urgent"}
DEAL_PRICING_TYPES = set(PRICING_TYPES)


class DealCreate(BaseModel):
    """Schema de creation d'un deal — validation stage/priority/pricing (DC1)."""

    title: str = Field(..., min_length=1, max_length=255)
    stage: str = Field("new", max_length=50)
    amount: float | None = Field(None, ge=0)
    currency: str = Field("EUR", max_length=3)
    probability: int = Field(0, ge=0, le=100)
    priority: str = Field("medium", max_length=20)
    expected_close_date: str | None = Field(None, max_length=10)
    company_id: str | None = Field(None, max_length=36)
    contact_id: str | None = Field(None, max_length=36)
    description: str | None = Field(None, max_length=5000)
    # Raison de perte (utilise pour la page Lost — saisie libre, bornee a 255 (DC1))
    loss_reason: str | None = Field(None, max_length=255)

    # Pricing recurrent (DC1 — bornes ge/le, default safe one_shot)
    pricing_type: str = Field("one_shot", max_length=20)
    recurring_amount: float | None = Field(None, ge=0)
    commitment_months: int | None = Field(None, ge=1, le=120)

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v not in DEAL_STAGES:
            raise ValueError(
                f"Stage invalide. Valeurs autorisees : {', '.join(DEAL_STAGES)}"
            )
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in DEAL_PRIORITIES:
            raise ValueError(
                f"Priorite invalide. Valeurs autorisees : {', '.join(sorted(DEAL_PRIORITIES))}"
            )
        return v

    @field_validator("pricing_type")
    @classmethod
    def validate_pricing_type(cls, v: str) -> str:
        if v not in DEAL_PRICING_TYPES:
            raise ValueError(
                f"Pricing type invalide. Valeurs autorisees : {', '.join(PRICING_TYPES)}"
            )
        return v

    @model_validator(mode="after")
    def validate_recurring_required(self) -> "DealCreate":
        """Cross-field : un pricing recurrent doit avoir un recurring_amount.

        Sans cette validation, un deal recurrent sans recurring_amount serait
        silencieusement ignore par le calcul MRR du dashboard (DC2).
        """
        if self.pricing_type != "one_shot" and self.recurring_amount is None:
            raise ValueError(
                "recurring_amount est obligatoire pour un pricing recurrent"
            )
        return self


class DealUpdate(BaseModel):
    """Schema de mise a jour partielle d'un deal."""

    title: str | None = Field(None, min_length=1, max_length=255)
    stage: str | None = Field(None, max_length=50)
    amount: float | None = Field(None, ge=0)
    currency: str | None = Field(None, max_length=3)
    probability: int | None = Field(None, ge=0, le=100)
    priority: str | None = Field(None, max_length=20)
    expected_close_date: str | None = Field(None, max_length=10)
    company_id: str | None = Field(None, max_length=36)
    contact_id: str | None = Field(None, max_length=36)
    description: str | None = Field(None, max_length=5000)
    # Raison de perte (PATCH — autoriser la mise a None pour reset)
    loss_reason: str | None = Field(None, max_length=255)

    # Pricing recurrent (PATCH — tous optionnels)
    pricing_type: str | None = Field(None, max_length=20)
    recurring_amount: float | None = Field(None, ge=0)
    commitment_months: int | None = Field(None, ge=1, le=120)

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str | None) -> str | None:
        if v is not None and v not in DEAL_STAGES:
            raise ValueError(
                f"Stage invalide. Valeurs autorisees : {', '.join(DEAL_STAGES)}"
            )
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str | None) -> str | None:
        if v is not None and v not in DEAL_PRIORITIES:
            raise ValueError(
                f"Priorite invalide. Valeurs autorisees : {', '.join(sorted(DEAL_PRIORITIES))}"
            )
        return v

    @field_validator("pricing_type")
    @classmethod
    def validate_pricing_type(cls, v: str | None) -> str | None:
        if v is not None and v not in DEAL_PRICING_TYPES:
            raise ValueError(
                f"Pricing type invalide. Valeurs autorisees : {', '.join(PRICING_TYPES)}"
            )
        return v


class DealStageUpdate(BaseModel):
    """Schema pour le changement de stage uniquement."""

    stage: str = Field(..., max_length=50)

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: str) -> str:
        if v not in DEAL_STAGES:
            raise ValueError(
                f"Stage invalide. Valeurs autorisees : {', '.join(DEAL_STAGES)}"
            )
        return v


class DealResponse(BaseModel):
    """Schema de reponse pour un deal."""

    id: str
    title: str
    stage: str
    amount: float | None
    currency: str
    probability: int
    priority: str
    expected_close_date: str | None
    actual_close_date: str | None
    position: int
    company_id: str | None
    contact_id: str | None
    owner_id: str | None
    description: str | None
    created_at: str

    # Champs derives des relations (DC6 — populer via selectinload pour eviter N+1)
    loss_reason: str | None = None
    owner_name: str | None = None
    company_name: str | None = None

    # Pricing recurrent
    pricing_type: str
    recurring_amount: float | None
    commitment_months: int | None

    class Config:
        from_attributes = True


class DealListResponse(BaseModel):
    """Schema de reponse paginee pour les deals."""

    items: list[DealResponse]
    total: int
    page: int
    size: int
    pages: int


class DealsStatsResponse(BaseModel):
    """Stats agregees pour un sous-ensemble de deals (filtres list partages).

    Tous les montants sont en EUR (ou la devise par defaut). Le MRR est normalise
    en mois (annual/12, quarterly/3, etc.) — voir PERIOD_TO_MONTHS.
    """

    count: int
    total_amount: float
    one_shot_amount: float
    mrr: float
    arr: float
    recurring_count: int
