# =============================================================================
# FGA CRM - Schemas User Management (admin)
# =============================================================================

from pydantic import BaseModel, EmailStr, Field, field_validator

# ---------- Constantes ----------

VALID_ROLES = {"admin", "manager", "sales"}

# ---------- Schemas ----------


class UserCreate(BaseModel):
    """Creation d'un membre par un admin (dans SON org). L'org vient du serveur."""

    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    role: str = Field("sales", max_length=50)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"Role invalide. Valeurs autorisees : {', '.join(sorted(VALID_ROLES))}")
        return v


class UserRoleUpdate(BaseModel):
    role: str = Field(..., max_length=50)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in VALID_ROLES:
            raise ValueError(f"Role invalide. Valeurs autorisees : {', '.join(sorted(VALID_ROLES))}")
        return v


class UserActiveToggle(BaseModel):
    is_active: bool


class UserLookupResponse(BaseModel):
    """Reponse minimale (id + full_name) pour les dropdowns/filtres frontend.

    Pas de role, pas d'email, pas d'avatar — DC6 : selectinload ciblee, pas de
    leak de donnees sensibles vers les sales.
    """

    id: str
    full_name: str

    class Config:
        from_attributes = True
