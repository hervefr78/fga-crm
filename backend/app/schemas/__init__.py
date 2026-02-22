# =============================================================================
# FGA CRM - Schemas (re-exports)
# =============================================================================

from app.schemas.common import PaginatedParams
from app.schemas.company import (
    CompanyCreate,
    CompanyListResponse,
    CompanyResponse,
    CompanyUpdate,
)
from app.schemas.contact import (
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactUpdate,
)
from app.schemas.deal import (
    DealCreate,
    DealListResponse,
    DealResponse,
    DealStageUpdate,
    DealUpdate,
)

__all__ = [
    "PaginatedParams",
    "ContactCreate",
    "ContactUpdate",
    "ContactResponse",
    "ContactListResponse",
    "CompanyCreate",
    "CompanyUpdate",
    "CompanyResponse",
    "CompanyListResponse",
    "DealCreate",
    "DealUpdate",
    "DealStageUpdate",
    "DealResponse",
    "DealListResponse",
]
