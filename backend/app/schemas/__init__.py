# =============================================================================
# FGA CRM - Schemas (re-exports)
# =============================================================================

from app.schemas.activity import (
    ActivityCreate,
    ActivityListResponse,
    ActivityResponse,
    ActivityUpdate,
)
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
from app.schemas.task import (
    TaskCompletionToggle,
    TaskCreate,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
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
    "TaskCreate",
    "TaskUpdate",
    "TaskCompletionToggle",
    "TaskResponse",
    "TaskListResponse",
    "ActivityCreate",
    "ActivityUpdate",
    "ActivityResponse",
    "ActivityListResponse",
]
