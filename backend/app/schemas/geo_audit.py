# =============================================================================
# FGA CRM - Schemas GEO Audit-visibility (integration Startup Radar)
# =============================================================================
"""Contrat d'API de la mesure de visibilite a la demande.

Cf. docs/integrations/SR-GEO-visibility-API-contract.md. Toutes les entrees sont
bornees (DC1). SR fabrique les prompts et les envoie ; le CRM mesure et renvoie.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

# Bornes (DC1)
MAX_COMPANY_LEN = 255
MAX_DOMAIN_LEN = 255
MAX_ALIAS_LEN = 255
MAX_ALIASES = 10
MAX_PROMPT_LEN = 1000
MAX_PROMPTS = 5
MAX_GEO_LEN = 8


class AuditVisibilityRequest(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=MAX_COMPANY_LEN)
    domain: str = Field(..., min_length=1, max_length=MAX_DOMAIN_LEN)
    aliases: list[Annotated[str, Field(max_length=MAX_ALIAS_LEN)]] = Field(
        default_factory=list, max_length=MAX_ALIASES
    )
    prompts: list[Annotated[str, Field(min_length=1, max_length=MAX_PROMPT_LEN)]] = Field(
        ..., min_length=1, max_length=MAX_PROMPTS
    )
    country: str = Field("FR", max_length=MAX_GEO_LEN)
    language: str = Field("fr", max_length=MAX_GEO_LEN)
    refresh: bool = False

    def clean_prompts(self) -> list[str]:
        out = [(p or "").strip()[:MAX_PROMPT_LEN] for p in self.prompts]
        return [p for p in out if p][:MAX_PROMPTS]

    def clean_aliases(self) -> list[str]:
        out = [(a or "").strip()[:MAX_ALIAS_LEN] for a in self.aliases]
        return [a for a in out if a][:MAX_ALIASES]


class AuditVisibilityCreateResponse(BaseModel):
    audit_id: UUID
    status: str
    cache_hit: bool = False


class AuditCompetitor(BaseModel):
    name: str
    mentions: int


class AuditPerPrompt(BaseModel):
    prompt: str
    mentioned: bool
    position: int | None = None


class AuditVisibilityResult(BaseModel):
    visible: bool
    runs_total: int
    runs_completed: int
    mentions: int
    visibility_rate: float
    best_position: int | None
    recommended: bool
    sentiment: str | None
    competitors_found: list[AuditCompetitor] = Field(default_factory=list)
    per_prompt: list[AuditPerPrompt] = Field(default_factory=list)
    summary: str


class AuditVisibilityStatusResponse(BaseModel):
    audit_id: UUID
    status: str
    engine: str
    company_name: str
    domain: str
    created_at: datetime
    result: AuditVisibilityResult | None = None
