# =============================================================================
# FGA CRM - Models Package
# =============================================================================

from app.models.activity import Activity
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.email_template import EmailTemplate
from app.models.tag import Tag, TagAssignment
from app.models.task import Task
from app.models.user import User
from app.models.webauthn_credential import WebAuthnCredential

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "User",
    "WebAuthnCredential",
    "Company",
    "Contact",
    "Deal",
    "EmailTemplate",
    "Activity",
    "Task",
    "Tag",
    "TagAssignment",
]
