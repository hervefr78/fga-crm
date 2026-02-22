# =============================================================================
# FGA CRM - Schemas Activity
# =============================================================================


from pydantic import BaseModel, Field, field_validator

# Valeurs autorisees (DC1 — validation contre Set)
ACTIVITY_TYPES = {"email", "call", "meeting", "note", "linkedin", "task", "audit"}


class ActivityCreate(BaseModel):
    """Schema de creation d'une activite — tous les strings bornes (DC1)."""

    type: str = Field(..., min_length=1, max_length=50)
    subject: str | None = Field(None, max_length=500)
    content: str | None = Field(None, max_length=10000)
    contact_id: str | None = Field(None, max_length=36)
    company_id: str | None = Field(None, max_length=36)
    deal_id: str | None = Field(None, max_length=36)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ACTIVITY_TYPES:
            raise ValueError(
                f"Type invalide. Valeurs autorisees : {', '.join(sorted(ACTIVITY_TYPES))}"
            )
        return v


class ActivityUpdate(BaseModel):
    """Schema de mise a jour partielle d'une activite."""

    type: str | None = Field(None, max_length=50)
    subject: str | None = Field(None, max_length=500)
    content: str | None = Field(None, max_length=10000)
    contact_id: str | None = Field(None, max_length=36)
    company_id: str | None = Field(None, max_length=36)
    deal_id: str | None = Field(None, max_length=36)

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ACTIVITY_TYPES:
            raise ValueError(
                f"Type invalide. Valeurs autorisees : {', '.join(sorted(ACTIVITY_TYPES))}"
            )
        return v


class ActivityResponse(BaseModel):
    """Schema de reponse pour une activite."""

    id: str
    type: str
    subject: str | None
    content: str | None
    metadata_: dict | None = None
    contact_id: str | None
    company_id: str | None
    deal_id: str | None
    user_id: str
    created_at: str

    class Config:
        from_attributes = True


class ActivityListResponse(BaseModel):
    """Schema de reponse paginee pour les activites."""

    items: list[ActivityResponse]
    total: int
    page: int
    size: int
    pages: int
