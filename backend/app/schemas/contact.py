# =============================================================================
# FGA CRM - Schemas Contact
# =============================================================================


from pydantic import BaseModel, Field, field_validator

# Valeurs autorisees (DC1 — validation contre Set)
CONTACT_STATUSES = {"new", "contacted", "qualified", "unqualified", "nurturing"}
JOB_LEVELS = {"C-Level", "VP", "Director", "Manager", "IC", "Other"}


class ContactCreate(BaseModel):
    """Schema de creation d'un contact — tous les strings bornes (DC1)."""

    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    title: str | None = Field(None, max_length=255)
    job_level: str | None = Field(None, max_length=50)
    department: str | None = Field(None, max_length=255)
    linkedin_url: str | None = Field(None, max_length=500)
    company_id: str | None = Field(None, max_length=36)
    source: str | None = Field(None, max_length=100)
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
    def validate_job_level(cls, v: str | None) -> str | None:
        if v is not None and v not in JOB_LEVELS:
            raise ValueError(
                f"Niveau invalide. Valeurs autorisees : {', '.join(sorted(JOB_LEVELS))}"
            )
        return v


class ContactUpdate(BaseModel):
    """Schema de mise a jour partielle d'un contact."""

    first_name: str | None = Field(None, min_length=1, max_length=255)
    last_name: str | None = Field(None, min_length=1, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    title: str | None = Field(None, max_length=255)
    job_level: str | None = Field(None, max_length=50)
    department: str | None = Field(None, max_length=255)
    linkedin_url: str | None = Field(None, max_length=500)
    company_id: str | None = Field(None, max_length=36)
    source: str | None = Field(None, max_length=100)
    status: str | None = Field(None, max_length=50)
    is_decision_maker: bool | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in CONTACT_STATUSES:
            raise ValueError(
                f"Statut invalide. Valeurs autorisees : {', '.join(sorted(CONTACT_STATUSES))}"
            )
        return v

    @field_validator("job_level")
    @classmethod
    def validate_job_level(cls, v: str | None) -> str | None:
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
    email: str | None
    email_status: str | None
    phone: str | None
    title: str | None
    job_level: str | None
    department: str | None
    is_decision_maker: bool
    linkedin_url: str | None
    status: str
    lead_score: int
    source: str | None
    company_id: str | None
    owner_id: str | None
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
