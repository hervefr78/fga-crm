# =============================================================================
# FGA CRM - Schemas Import/Export
# =============================================================================

from pydantic import BaseModel, Field, field_validator

from app.schemas.company import SIZE_RANGES
from app.schemas.contact import CONTACT_STATUSES, JOB_LEVELS

# ---------- Resultats ----------

class ImportRowError(BaseModel):
    """Erreur de validation sur une ligne d'import."""
    row: int
    field: str
    message: str


class ImportResult(BaseModel):
    """Resultat d'un import CSV."""
    imported: int
    errors: list[ImportRowError]


# ---------- Lignes import contacts ----------

class ContactImportRow(BaseModel):
    """Validation d'une ligne d'import contact — memes regles que ContactCreate (DC1)."""

    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    title: str | None = Field(None, max_length=255)
    job_level: str | None = Field(None, max_length=50)
    department: str | None = Field(None, max_length=255)
    linkedin_url: str | None = Field(None, max_length=500)
    source: str | None = Field(None, max_length=100)
    status: str = Field("new", max_length=50)
    is_decision_maker: bool = False

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in CONTACT_STATUSES:
            raise ValueError(f"Statut invalide. Valeurs : {', '.join(sorted(CONTACT_STATUSES))}")
        return v

    @field_validator("job_level")
    @classmethod
    def validate_job_level(cls, v: str | None) -> str | None:
        if v is not None and v not in JOB_LEVELS:
            raise ValueError(f"Niveau invalide. Valeurs : {', '.join(sorted(JOB_LEVELS))}")
        return v


# ---------- Lignes import companies ----------

class CompanyImportRow(BaseModel):
    """Validation d'une ligne d'import entreprise — memes regles que CompanyCreate (DC1)."""

    name: str = Field(..., min_length=1, max_length=255)
    domain: str | None = Field(None, max_length=255)
    website: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=5000)
    size_range: str | None = Field(None, max_length=50)
    linkedin_url: str | None = Field(None, max_length=500)
    phone: str | None = Field(None, max_length=50)
    country: str | None = Field(None, max_length=100)
    city: str | None = Field(None, max_length=100)

    @field_validator("size_range")
    @classmethod
    def validate_size_range(cls, v: str | None) -> str | None:
        if v is not None and v not in SIZE_RANGES:
            raise ValueError(f"Taille invalide. Valeurs : {', '.join(sorted(SIZE_RANGES))}")
        return v


# ---------- Requetes d'import ----------

class ContactImportRequest(BaseModel):
    """Requete d'import contacts — max 1000 lignes (DC1)."""
    rows: list[dict] = Field(..., max_length=1000)


class CompanyImportRequest(BaseModel):
    """Requete d'import entreprises — max 1000 lignes (DC1)."""
    rows: list[dict] = Field(..., max_length=1000)
