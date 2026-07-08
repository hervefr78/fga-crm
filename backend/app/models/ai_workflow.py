# =============================================================================
# FGA CRM - Modele AiWorkflowRun (audit des appels IA)
# =============================================================================
"""Trace chaque appel des workflows IA natifs (scoring, qualification, insights) :
debogage, suivi des couts (tokens), iteration des prompts (prompt_version).
Immutable : created_at seul. Org-scopee (isolation multi-tenant)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin

# Workflows connus (DC8 — source unique)
AI_WORKFLOWS = ["scoring", "qualification", "insights"]

# Statuts d'un run (DC5)
AI_RUN_STATUSES = ["ok", "parse_error", "api_error"]


class AiWorkflowRun(Base, UUIDMixin):
    __tablename__ = "ai_workflow_runs"

    # Isolation multi-tenant (nullable=False : tout run est declenche par un user d'org)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    # scoring | qualification | insights
    workflow: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # deal | contact | pipeline
    target_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    prompt_version: Mapped[str] = mapped_column(String(20), nullable=False)
    model: Mapped[str] = mapped_column(String(50), nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # ok | parse_error | api_error
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AiWorkflowRun {self.workflow} {self.status}>"
