# =============================================================================
# FGA CRM - Schemas Enrichissement (feature Compass)
# =============================================================================
"""Requetes/reponses de l'API d'enrichissement. Bornees (DC1). Modes :
company (1 siren) | batch (sirens[]) | icp (filtre NAF) | source (provenance CRM)
| contacts (contacts existants)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_SIRENS = 500
MAX_NAF = 20
MAX_LIMIT = 1000
MAX_CONTACTS = 1000

# Provenances CRM autorisees pour le mode 'source' (DC1 : Set ferme, aligne sur
# les valeurs ecrites en base par les integrations).
ALLOWED_LEAD_SOURCES = frozenset({"startup_radar", "nomo-ia", "plein-phare"})


class EnrichmentMode(StrEnum):
    company = "company"
    batch = "batch"
    icp = "icp"
    source = "source"      # societes CRM filtrees par provenance (lead_source)
    contacts = "contacts"  # Feature B : enrichir des contacts existants


class IcpFilterInput(BaseModel):
    naf_codes: list[Annotated[str, Field(max_length=8)]] = Field(default_factory=list, max_length=MAX_NAF)
    only_active: bool = True
    min_revenue_eur: int | None = Field(None, ge=0)
    require_domain: bool = True
    limit: int = Field(50, ge=1, le=MAX_LIMIT)


class SourceFilterInput(BaseModel):
    lead_source: str = Field(..., max_length=40)
    limit: int = Field(200, ge=1, le=MAX_LIMIT)

    @field_validator("lead_source")
    @classmethod
    def _lead_source_allowed(cls, v: str) -> str:
        if v not in ALLOWED_LEAD_SOURCES:
            raise ValueError(
                f"lead_source invalide. Valeurs : {', '.join(sorted(ALLOWED_LEAD_SOURCES))}"
            )
        return v


class EnrichmentJobCreateRequest(BaseModel):
    mode: EnrichmentMode
    siren: str | None = Field(None, max_length=9)
    sirens: list[Annotated[str, Field(max_length=9)]] = Field(default_factory=list, max_length=MAX_SIRENS)
    icp_filter: IcpFilterInput | None = None
    # Mode source : societes CRM par provenance
    source_filter: SourceFilterInput | None = None
    # Mode contacts (Feature B)
    contact_ids: list[UUID] = Field(default_factory=list, max_length=MAX_CONTACTS)
    all_missing_email: bool = False
    reverify: bool = False

    def to_target(self) -> dict:
        """Serialise en TargetSpec (stocke dans job.target_json)."""
        return {
            "kind": self.mode.value,
            "siren": self.siren,
            "sirens": self.sirens,
            "icp_filter": self.icp_filter.model_dump() if self.icp_filter else None,
            "source_filter": self.source_filter.model_dump() if self.source_filter else None,
            "contact_ids": [str(c) for c in self.contact_ids],
            "all_missing_email": self.all_missing_email,
            "reverify": self.reverify,
        }


class EnrichmentJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mode: str
    status: str
    stats_json: dict
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class EnrichmentJobListResponse(BaseModel):
    items: list[EnrichmentJobResponse]
    total: int
    page: int
    size: int
