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
    # Action lancee cote client (tracee dans payload_json.action) :
    # audit (P2) | contacts (enrichissement P1) | qualify (P3) | outreach (envoi P1)
    action_kind: Literal["audit", "contacts", "qualify", "outreach"] | None = Field(default=None)


class LeadScanResponse(BaseModel):
    """Resultat d'un scan manuel (org de l'utilisateur)."""

    created: dict[str, int]  # {funding_detected: n, mmf_gap: n, inbound_new: n}


# ---------------------------------------------------------------------------
# Draft d'outreach (workflow outreach-v1) — stocke sur le signal
# ---------------------------------------------------------------------------

class LeadDraftRequest(BaseModel):
    """Cible du draft. Sans contact_id : meilleur contact email de la societe."""

    contact_id: str | None = Field(None, max_length=36)


class LeadDraftResponse(BaseModel):
    """Draft genere (a valider par l'humain — jamais envoye automatiquement)."""

    signal_id: str
    contact_id: str
    contact_name: str
    contact_email: str
    subject: str
    body: str
    angle_rationale: str
    generated_at: str              # ISO datetime
    meta: dict                     # {model, prompt_version}


# ---------------------------------------------------------------------------
# Queue priorisee (ecran 1) + funnel par play
# ---------------------------------------------------------------------------

class LeadQueueItem(BaseModel):
    """Lead priorise : profondeur du MMF gap x fraicheur des fonds."""

    signal: LeadSignalResponse
    contacts_with_email: int       # decideurs joignables sur la societe
    has_draft: bool                # un draft outreach-v1 est deja pret


class LeadQueueResponse(BaseModel):
    items: list[LeadQueueItem]
    total: int


class PlayFunnel(BaseModel):
    """Compteurs du funnel d'un play (fenetre 30 j)."""

    detected: int
    actioned: int                  # action principale lancee (audit/enrich/qualify)
    drafted: int                   # draft outreach genere (P1 uniquement)
    sent: int                      # draft envoye via le composer (P1 uniquement)


class LeadFunnelResponse(BaseModel):
    p1_mmf_gap: PlayFunnel
    p2_funding: PlayFunnel
    p3_inbound: PlayFunnel
    period_days: int
