# =============================================================================
# FGA CRM - Models Package
# =============================================================================

from app.models.activity import Activity
from app.models.ai_workflow import AiInsight, AiWorkflowRun
from app.models.api_key import ApiKey
from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.email_template import EmailTemplate
from app.models.enrichment import (
    EnrichmentBulk,
    EnrichmentBulkItem,
    EnrichmentEmailVerification,
    EnrichmentJob,
    EnrichmentProvenance,
    EnrichmentSuppression,
)
from app.models.geo import (
    GeoAuditJob,
    GeoBrand,
    GeoMetricsDaily,
    GeoPrompt,
    GeoRun,
)
from app.models.lead_engine import LeadSignal
from app.models.mcp_tool_usage import McpToolUsage
from app.models.organization import Organization
from app.models.tag import Tag, TagAssignment
from app.models.task import Task
from app.models.trends import (
    TrendCategory,
    TrendCategorySeed,
    TrendJob,
    TrendKeyword,
    TrendReport,
    TrendSnapshot,
)
from app.models.user import User
from app.models.webauthn_credential import WebAuthnCredential

__all__ = [
    "Base",
    "TimestampMixin",
    "UUIDMixin",
    "Organization",
    "User",
    "WebAuthnCredential",
    "Company",
    "Contact",
    "Deal",
    "EmailTemplate",
    "EnrichmentJob",
    "EnrichmentProvenance",
    "EnrichmentSuppression",
    "EnrichmentEmailVerification",
    "EnrichmentBulk",
    "EnrichmentBulkItem",
    "Activity",
    "Task",
    "Tag",
    "TagAssignment",
    "ApiKey",
    "GeoBrand",
    "GeoPrompt",
    "GeoRun",
    "GeoMetricsDaily",
    "GeoAuditJob",
    "McpToolUsage",
    "TrendCategory",
    "TrendCategorySeed",
    "TrendJob",
    "TrendSnapshot",
    "TrendKeyword",
    "TrendReport",
    "AiWorkflowRun",
    "AiInsight",
    "LeadSignal",
]
