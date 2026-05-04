# =============================================================================
# FGA CRM - Schemas AI Next-Action (mock simple, pas de LLM)
# =============================================================================

from pydantic import BaseModel, Field

# Types d'action autorises (DC1 — borne pour l'UI)
NEXT_ACTION_TYPES = {"compose_email", "create_task", "snooze", "view"}


class NextActionAction(BaseModel):
    """Action proposee par la suggestion (bouton CTA)."""

    label: str = Field(..., min_length=1, max_length=120)
    type: str = Field(..., max_length=32)  # "compose_email", "create_task", "snooze", "view"


class NextActionResponse(BaseModel):
    """Suggestion d'action sur une entite (Company / Contact / Deal).

    Logique cote backend = regles simples basees sur les attributs de l'entite.
    Pas d'appel LLM (cf. ADR a venir si on branche un vrai modele plus tard).
    """

    title: str = Field(..., min_length=1, max_length=200)
    body: str = Field(..., min_length=1, max_length=1000)
    primary_action: NextActionAction | None = None
    secondary_action: NextActionAction | None = None
