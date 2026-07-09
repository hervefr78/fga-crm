# =============================================================================
# FGA CRM - Modele LeadSignal (Lead Engine — Signal Inbox)
# =============================================================================
"""Signal de generation de leads detecte par le scan periodique
(docs/LEAD_ENGINE_VISION.md §2). Regle metier structurante :

- ``mmf_gap`` (audit SR < seuil) = SEUL declencheur d'outreach (play P1) ;
- ``funding_detected`` (levee recente) = qualificateur de solvabilite, ne
  declenche qu'un AUDIT du message (play P2) — jamais un contact.

Dedup temporelle : un ``dedup_key`` (ex: ``mmf:{company_id}``) deja emis dans
la fenetre ``lead_engine_dedup_days`` ne redeclenche pas, quel que soit le
statut du signal precedent (un signal ignore est memorise — pas de re-nag).
"""

import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, OrgScopedMixin, TimestampMixin, UUIDMixin

# Types de signaux (DC8 — source unique)
SIGNAL_TYPES = ["funding_detected", "mmf_gap"]

# Statuts + transitions valides (DC5 — machine a etats exhaustive)
SIGNAL_STATUSES = ["new", "actioned", "ignored"]
SIGNAL_TRANSITIONS: dict[str, list[str]] = {
    "new": ["actioned", "ignored"],
    "actioned": [],               # terminal : l'action a ete lancee
    "ignored": ["new"],           # re-ouverture possible (reconsidere)
}


class LeadSignal(Base, UUIDMixin, OrgScopedMixin, TimestampMixin):
    __tablename__ = "lead_signals"

    # funding_detected | mmf_gap
    signal_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # Societe concernee — CASCADE : un signal sans societe n'a pas de sens
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Contexte du signal : {company_name, startup_radar_id, funding_date,
    #  funding_amount, funding_series, audit_score, action{kind, at}}
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # new | actioned | ignored
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="new", index=True
    )
    # Cle de dedup temporelle : "funding:{company_id}" / "mmf:{company_id}"
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        # Lookup de dedup du detecteur : WHERE org + dedup_key + created_at recent
        Index("ix_lead_signals_org_dedup", "organization_id", "dedup_key"),
    )

    def __repr__(self) -> str:
        return f"<LeadSignal {self.signal_type} {self.status}>"
