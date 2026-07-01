# =============================================================================
# FGA CRM - Schemas MCP Usage (conso API MCP)
# =============================================================================
"""Schemas Pydantic v2 du dashboard de conso API MCP.

- Ingest : evenements agreges pousses par le MCP (service-auth).
- Summary : agregat par tool sur une periode + total (JWT admin).
- ByTool : detail d'un tool par (jour, modele) (JWT admin).

Bornes DC1 : tailles de strings, entiers >= 0, batch d'ingest cappe.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

# Taille max du batch d'ingest (DC1 — borne l'input externe).
MAX_INGEST_EVENTS = 1000

# Longueurs alignees sur le modele (String(100)).
MAX_TOOL_NAME_LEN = 100
MAX_MODEL_LEN = 100
MAX_IDEM_KEY_LEN = 64  # le MCP envoie un uuid4().hex (32 chars)


# ---------------------------------------------------------------------------
# Ingest (MCP -> CRM, service-auth)
# ---------------------------------------------------------------------------

class McpUsageIngestEvent(BaseModel):
    """Un evenement d'usage agrege pour une cle (jour, tool, modele)."""

    day: date
    tool_name: str = Field(..., min_length=1, max_length=MAX_TOOL_NAME_LEN)
    model: str = Field(..., min_length=1, max_length=MAX_MODEL_LEN)
    calls: int = Field(0, ge=0)
    input_tokens: int = Field(0, ge=0)
    output_tokens: int = Field(0, ge=0)
    cache_read_tokens: int = Field(0, ge=0)
    cache_write_tokens: int = Field(0, ge=0)


class McpUsageIngestRequest(BaseModel):
    """Batch d'evenements pousse par le MCP.

    `idempotency_key` (optionnel) : cle stable par batch. Si fournie, l'ingest
    dedupe (un batch deja ingere est ignore) -> exactly-once malgre le
    at-least-once du flush MCP (retry apres reponse perdue). Absente -> ancien
    comportement incremental (retro-compatible).
    """

    events: list[McpUsageIngestEvent] = Field(..., min_length=1, max_length=MAX_INGEST_EVENTS)
    idempotency_key: str | None = Field(None, max_length=MAX_IDEM_KEY_LEN)


class McpUsageIngestResponse(BaseModel):
    """Petit resume de l'ingestion."""

    ingested: int


# ---------------------------------------------------------------------------
# Summary (vue generale, JWT admin)
# ---------------------------------------------------------------------------

class McpUsageTotal(BaseModel):
    """Total agrege sur la periode (tous tools confondus)."""

    calls: int
    tokens_in: int
    tokens_out: int
    cache_read: int
    cache_write: int
    cost_eur: float


class ToolUsageSummary(BaseModel):
    """Agregat par tool sur la periode."""

    tool_name: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_eur: float


class McpUsageSummaryResponse(BaseModel):
    date_from: date
    date_to: date
    total: McpUsageTotal
    by_tool: list[ToolUsageSummary]


# ---------------------------------------------------------------------------
# ByTool (detail d'un tool, JWT admin)
# ---------------------------------------------------------------------------

class McpUsageByToolRow(BaseModel):
    """Une ligne de detail : (jour, modele) pour un tool donne."""

    model_config = ConfigDict(from_attributes=True)

    day: date
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    cost_eur: float


class McpUsageByToolResponse(BaseModel):
    tool_name: str
    date_from: date
    date_to: date
    rows: list[McpUsageByToolRow]
