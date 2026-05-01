# =============================================================================
# FGA CRM - Schemas Company
# =============================================================================


from pydantic import BaseModel, Field, field_validator

# Valeurs autorisees (DC1)
SIZE_RANGES = {"1-10", "11-50", "51-200", "201-500", "500+"}


class CompanyCreate(BaseModel):
    """Schema de creation d'une entreprise — tous les strings bornes (DC1)."""

    name: str = Field(..., min_length=1, max_length=255)
    domain: str | None = Field(None, max_length=255)
    website: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=5000)
    size_range: str | None = Field(None, max_length=50)
    linkedin_url: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=50)
    address_line: str | None = Field(None, max_length=500)
    postal_code: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    startup_radar_id: str | None = Field(None, max_length=255)
    lead_source: str | None = Field(None, max_length=100)
    vat_number: str | None = Field(None, max_length=50)

    @field_validator("size_range")
    @classmethod
    def validate_size_range(cls, v: str | None) -> str | None:
        if v is not None and v not in SIZE_RANGES:
            raise ValueError(
                f"Taille invalide. Valeurs autorisees : {', '.join(sorted(SIZE_RANGES))}"
            )
        return v


class CompanyUpdate(BaseModel):
    """Schema de mise a jour partielle d'une entreprise."""

    name: str | None = Field(None, min_length=1, max_length=255)
    domain: str | None = Field(None, max_length=255)
    website: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=5000)
    size_range: str | None = Field(None, max_length=50)
    linkedin_url: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=50)
    address_line: str | None = Field(None, max_length=500)
    postal_code: str | None = Field(None, max_length=20)
    city: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=100)
    vat_number: str | None = Field(None, max_length=50)

    @field_validator("size_range")
    @classmethod
    def validate_size_range(cls, v: str | None) -> str | None:
        if v is not None and v not in SIZE_RANGES:
            raise ValueError(
                f"Taille invalide. Valeurs autorisees : {', '.join(sorted(SIZE_RANGES))}"
            )
        return v


class CompanyResponse(BaseModel):
    """Schema de reponse pour une entreprise."""

    id: str
    name: str
    domain: str | None
    website: str | None
    industry: str | None
    description: str | None
    size_range: str | None
    linkedin_url: str | None
    phone: str | None
    address_line: str | None = None
    postal_code: str | None = None
    city: str | None
    country: str | None
    startup_radar_id: str | None = None
    lead_source: str | None = None
    vat_number: str | None = None
    owner_id: str | None
    owner_name: str | None = None
    created_at: str
    updated_at: str | None = None
    updated_by_name: str | None = None
    # Audits SR (liste entreprises)
    has_audit_messaging: bool = False
    has_audit_detailed: bool = False
    has_audit_geo: bool = False
    audit_score: int | None = None

    class Config:
        from_attributes = True


class CompanyListResponse(BaseModel):
    """Schema de reponse paginee pour les entreprises."""

    items: list[CompanyResponse]
    total: int
    page: int
    size: int
    pages: int
