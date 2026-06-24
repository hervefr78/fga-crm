# =============================================================================
# FGA CRM - Draft Review Schemas (proxy compass-core)
# =============================================================================
# DraftReview est le miroir EXACT du DraftRecord expose par compass-core
# (compass-core/app/schemas/draft.py). Tout changement de contrat cote
# compass-core doit etre repercute ici.

from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

# Marques acceptees (miroir compass-core Brand).
Brand = Literal["fga", "nomo", "ppd"]

# Statuts acceptes pour une mise a jour de review depuis le CRM.
ReviewStatus = Literal["approved", "rejected", "to-review"]


class DraftReview(BaseModel):
    """Reponse API — shape identique a compass-core DraftRecord.

    On garde `populate_by_name=True` et l'alias `metadata`/`record_metadata`
    pour accepter la reponse JSON de compass-core telle quelle.
    """

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    draft_id: str | None = None
    lead_id: str
    type: str
    content: str
    status: str = "to-review"
    brand: Brand
    sequence_day: int | None = None
    voice_pack_used: str | None = None
    voice_check_passed: bool = False
    published_url: str | None = None
    created_by: str = "mcp"
    created_at: datetime | None = None
    # JSON key = `metadata` (contrat fga_mcp / compass-core). Accepte aussi
    # `record_metadata` par robustesse.
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("metadata", "record_metadata"),
    )


class DraftStatusUpdateIn(BaseModel):
    """Corps de PATCH /drafts-review/{id}/status.

    Seul `status` est accepte cote client. Le `reviewer` est impose
    server-side (current_user.email) — il N'EST PAS lu du body (DC18).
    `extra="forbid"` rejette un `reviewer` client-fourni en 422.
    """

    model_config = ConfigDict(extra="forbid")

    status: ReviewStatus
