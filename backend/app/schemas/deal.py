# =============================================================================
# FGA CRM - Schemas Deal
# =============================================================================

from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.models.deal import DEAL_STAGES

# Valeurs autorisees (DC1)
DEAL_PRIORITIES = {"low", "medium", "high", "urgent"}


class DealCreate(BaseModel):
    """Schema de creation d'un deal — validation stage/priority (DC1)."""

    title: str = Field(..., min_length=1, max_length=255)
    stage: str = Field("new", max_length=50)
    amount: Optional[float] = Field(None, ge=0)
    currency: str = Field("EUR", max_length=3)
    probability: int = Field(0, ge=0, le=100)
    priority: str = Field("medium", max_length=20)
    expected_close_date: Optional[str] = Field(None, max_length=10)
    company_id: Optional[str] = Field(None, max_length=36)
    contact_id: Optional[str] = Field(None, max_length=36)
    description: Optional[str] = Field(None, max_length=5000)

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


class DealUpdate(BaseModel):
    """Schema de mise a jour partielle d'un deal."""

    title: Optional[str] = Field(None, min_length=1, max_length=255)
    stage: Optional[str] = Field(None, max_length=50)
    amount: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = Field(None, max_length=3)
    probability: Optional[int] = Field(None, ge=0, le=100)
    priority: Optional[str] = Field(None, max_length=20)
    expected_close_date: Optional[str] = Field(None, max_length=10)
    company_id: Optional[str] = Field(None, max_length=36)
    contact_id: Optional[str] = Field(None, max_length=36)
    description: Optional[str] = Field(None, max_length=5000)

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in DEAL_STAGES:
            raise ValueError(
                f"Stage invalide. Valeurs autorisees : {', '.join(DEAL_STAGES)}"
            )
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in DEAL_PRIORITIES:
            raise ValueError(
                f"Priorite invalide. Valeurs autorisees : {', '.join(sorted(DEAL_PRIORITIES))}"
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
    amount: Optional[float]
    currency: str
    probability: int
    priority: str
    expected_close_date: Optional[str]
    company_id: Optional[str]
    contact_id: Optional[str]
    owner_id: Optional[str]
    description: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class DealListResponse(BaseModel):
    """Schema de reponse paginee pour les deals."""

    items: list[DealResponse]
    total: int
    page: int
    size: int
    pages: int
