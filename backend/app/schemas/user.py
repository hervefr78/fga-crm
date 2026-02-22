# =============================================================================
# FGA CRM - Schemas User Management (admin)
# =============================================================================

from pydantic import BaseModel, Field, field_validator

# ---------- Constantes ----------

VALID_ROLES = {"admin", "manager", "sales"}

# ---------- Schemas ----------


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
