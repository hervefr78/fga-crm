# =============================================================================
# FGA CRM - Schemas Workflows IA (scoring)
# =============================================================================
"""Sortie LLM stricte (validee AVANT toute ecriture — DC3) + reponse API.
Bornes DC1 : la validation Pydantic s'applique localement au parse meme si les
contraintes sont retirees du JSON schema envoye a OpenAI (mode strict)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Version du prompt de scoring (auditabilite — stockee dans ai_score_meta et runs)
SCORING_PROMPT_VERSION = "scoring-v1"


class DealScoreOutput(BaseModel):
    """Sortie structuree du LLM pour le scoring d'un deal."""

    score: int = Field(..., ge=0, le=100)
    tier: Literal["A", "B", "C"]
    fit_points: int = Field(..., ge=0, le=50)
    intent_points: int = Field(..., ge=0, le=30)
    message_points: int = Field(..., ge=0, le=20)
    rationale: str = Field(..., max_length=800)
    missing_signals: list[str] = Field(default_factory=list, max_length=10)
    recommended_product: Literal["audit-999", "founder-499", "advisory"] | None = None


class DealScoreResponse(BaseModel):
    """Reponse de POST /deals/{id}/score."""

    deal_id: str
    score: int
    tier: str
    rationale: str
    missing_signals: list[str]
    recommended_product: str | None
    scored_at: str                 # ISO datetime
    cached: bool                   # True si score existant (< TTL) retourne sans appel LLM
    meta: dict                     # {model, prompt_version}
