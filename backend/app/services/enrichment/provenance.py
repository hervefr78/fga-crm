# =============================================================================
# FGA CRM - Enrichissement : traçabilite RGPD (provenance)
# =============================================================================
"""ProvenanceService (spec §11.4) : enregistre l'origine de chaque donnee
(nom/email/titre/linkedin) avec base legale + horodatage. Reponse immediate a
« d'ou vient ma donnee ? ». N'commit PAS (l'orchestrateur gere la transaction)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrichment import (
    LEGAL_BASIS_LEGITIMATE_INTEREST,
    EnrichmentProvenance,
)


async def record_provenance(
    db: AsyncSession,
    *,
    entity_type: str,          # person | email
    field: str,                # name | email | title | linkedin
    source: str,
    contact_id: uuid.UUID | None = None,
    source_detail: str | None = None,
    organization_id=None,
    legal_basis: str = LEGAL_BASIS_LEGITIMATE_INTEREST,
) -> None:
    """Ajoute un evenement de provenance (add seul — commit par l'appelant)."""
    db.add(EnrichmentProvenance(
        organization_id=organization_id,
        entity_type=entity_type,
        contact_id=contact_id,
        field=field,
        source=source,
        source_detail=source_detail,
        legal_basis=legal_basis,
    ))
