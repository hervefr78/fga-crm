# =============================================================================
# FGA CRM - Schemas Company
# =============================================================================

from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Valeurs autorisees (DC1)
SIZE_RANGES = {"1-10", "11-50", "51-200", "201-500", "500+"}


class CompanyCreate(BaseModel):
    """Schema de creation d'une entreprise — tous les strings bornes (DC1)."""

    name: str = Field(..., min_length=1, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    website: Optional[str] = Field(None, max_length=500)
    industry: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    size_range: Optional[str] = Field(None, max_length=50)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=50)
    country: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)

    @field_validator("size_range")
    @classmethod
    def validate_size_range(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in SIZE_RANGES:
            raise ValueError(
                f"Taille invalide. Valeurs autorisees : {', '.join(sorted(SIZE_RANGES))}"
            )
        return v


class CompanyUpdate(BaseModel):
    """Schema de mise a jour partielle d'une entreprise."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    website: Optional[str] = Field(None, max_length=500)
    industry: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)
    size_range: Optional[str] = Field(None, max_length=50)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    phone: Optional[str] = Field(None, max_length=50)
    country: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)

    @field_validator("size_range")
    @classmethod
    def validate_size_range(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in SIZE_RANGES:
            raise ValueError(
                f"Taille invalide. Valeurs autorisees : {', '.join(sorted(SIZE_RANGES))}"
            )
        return v


class CompanyResponse(BaseModel):
    """Schema de reponse pour une entreprise."""

    id: str
    name: str
    domain: Optional[str]
    website: Optional[str]
    industry: Optional[str]
    description: Optional[str]
    size_range: Optional[str]
    linkedin_url: Optional[str]
    phone: Optional[str]
    country: Optional[str]
    city: Optional[str]
    owner_id: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


class CompanyListResponse(BaseModel):
    """Schema de reponse paginee pour les entreprises."""

    items: list[CompanyResponse]
    total: int
    page: int
    size: int
    pages: int
