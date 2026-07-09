# =============================================================================
# FGA CRM - Schemas Lead Engine (Signal Inbox)
# =============================================================================
"""Contrats API du module Lead Engine (docs/LEAD_ENGINE_VISION.md §3.2).

Le detecteur cree les signaux ; l'API les liste et gere leurs transitions
(new -> actioned | ignored, ignored -> new). L'action elle-meme (audit SR,
recherche de decideurs) est orchestree cote client sur les endpoints existants.
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LeadSignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    signal_type: str
    status: str
    company_id: uuid.UUID | None
    # {company_name, startup_radar_id, funding_date, funding_amount,
    #  funding_series, audit_score?, action?{kind, at}}
    payload_json: dict
    created_at: datetime
    updated_at: datetime


class LeadSignalStats(BaseModel):
    """KPI de l'inbox : backlog courant + activite 7 jours."""

    new_total: int
    new_funding: int
    new_mmf: int
    actioned_7d: int
    ignored_7d: int


class LeadSignalListResponse(BaseModel):
    items: list[LeadSignalResponse]
    total: int
    page: int
    size: int
    stats: LeadSignalStats


class LeadSignalUpdateRequest(BaseModel):
    """Transition de statut (DC5 : validee contre SIGNAL_TRANSITIONS)."""

    status: Literal["actioned", "ignored", "new"]
    # Action lancee cote client (tracee dans payload_json.action) : audit | contacts
    action_kind: Literal["audit", "contacts"] | None = Field(default=None)


class LeadScanResponse(BaseModel):
    """Resultat d'un scan manuel (org de l'utilisateur)."""

    created: dict[str, int]  # {funding_detected: n, mmf_gap: n}
