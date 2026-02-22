# =============================================================================
# FGA CRM - Models Package
# =============================================================================

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.user import User
from app.models.webauthn_credential import WebAuthnCredential
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.activity import Activity
from app.models.task import Task
from app.models.tag import Tag, TagAssignment

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "User",
    "WebAuthnCredential",
    "Company",
    "Contact",
    "Deal",
    "Activity",
    "Task",
    "Tag",
    "TagAssignment",
]
