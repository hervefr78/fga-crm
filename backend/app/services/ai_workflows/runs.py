# =============================================================================
# FGA CRM - Workflows IA : journal d'audit (ai_workflow_runs)
# =============================================================================
"""Trace chaque appel IA (ok / parse_error / api_error) avec tokens et version
de prompt. Ne commit PAS : l'appelant gere la transaction (le run est committe
avec le resultat, ou seul en cas d'echec)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_workflow import AiWorkflowRun

_MAX_ERROR_LEN = 2000


def record_run(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    workflow: str,
    prompt_version: str,
    model: str,
    status: str,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    error: str | None = None,
) -> AiWorkflowRun:
    run = AiWorkflowRun(
        organization_id=organization_id,
        workflow=workflow,
        target_type=target_type,
        target_id=target_id,
        prompt_version=prompt_version,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        status=status,
        error=(error or None) and str(error)[:_MAX_ERROR_LEN],
    )
    db.add(run)
    return run
