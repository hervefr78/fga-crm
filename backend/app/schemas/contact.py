# =============================================================================
# FGA CRM - Schemas Contact
# =============================================================================

from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Valeurs autorisees (DC1 — validation contre Set)
CONTACT_STATUSES = {"new", "contacted", "qualified", "unqualified", "nurturing"}
JOB_LEVELS = {"C-Level", "VP", "Director", "Manager", "IC", "Other"}


class ContactCreate(BaseModel):
    """Schema de creation d'un contact — tous les strings bornes (DC1)."""

    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    title: Optional[str] = Field(None, max_length=255)
    job_level: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=255)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    company_id: Optional[str] = Field(None, max_length=36)
    source: Optional[str] = Field(None, max_length=100)
    status: str = Field("new", max_length=50)
    is_decision_maker: bool = False

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in CONTACT_STATUSES:
            raise ValueError(
                f"Statut invalide. Valeurs autorisees : {', '.join(sorted(CONTACT_STATUSES))}"
            )
        return v

    @field_validator("job_level")
    @classmethod
    def validate_job_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in JOB_LEVELS:
            raise ValueError(
                f"Niveau invalide. Valeurs autorisees : {', '.join(sorted(JOB_LEVELS))}"
            )
        return v


class ContactUpdate(BaseModel):
    """Schema de mise a jour partielle d'un contact."""

    first_name: Optional[str] = Field(None, min_length=1, max_length=255)
    last_name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    title: Optional[str] = Field(None, max_length=255)
    job_level: Optional[str] = Field(None, max_length=50)
    department: Optional[str] = Field(None, max_length=255)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    company_id: Optional[str] = Field(None, max_length=36)
    source: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, max_length=50)
    is_decision_maker: Optional[bool] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in CONTACT_STATUSES:
            raise ValueError(
                f"Statut invalide. Valeurs autorisees : {', '.join(sorted(CONTACT_STATUSES))}"
            )
        return v

    @field_validator("job_level")
    @classmethod
    def validate_job_level(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in JOB_LEVELS:
            raise ValueError(
                f"Niveau invalide. Valeurs autorisees : {', '.join(sorted(JOB_LEVELS))}"
            )
        return v


class ContactResponse(BaseModel):
    """Schema de reponse pour un contact."""

    id: str
    first_name: str
    last_name: str
    full_name: str
    email: Optional[str]
    email_status: Optional[str]
    phone: Optional[str]
    title: Optional[str]
    job_level: Optional[str]
    department: Optional[str]
    is_decision_maker: bool
    linkedin_url: Optional[str]
    status: str
    lead_score: int
    source: Optional[str]
    company_id: Optional[str]
    owner_id: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class ContactListResponse(BaseModel):
    """Schema de reponse paginee pour les contacts."""

    items: list[ContactResponse]
    total: int
    page: int
    size: int
    pages: int
