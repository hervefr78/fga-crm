# =============================================================================
# FGA CRM - Schemas Organization
# =============================================================================

from pydantic import BaseModel, Field


class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    is_active: bool


class OrganizationUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
