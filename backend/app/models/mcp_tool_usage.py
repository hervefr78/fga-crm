# =============================================================================
# FGA CRM - Modele McpToolUsage (conso API MCP par tool)
# =============================================================================
"""Agregat quotidien de la conso API Anthropic par (jour, tool MCP, modele).

Calque sur GeoMetricsDaily : upsert quotidien par dimensions, tokens bruts
stockes, cout calcule A LA LECTURE (une correction de tarif recalcule
l'historique). Alimente par le MCP via POST /mcp-usage/ingest (service-auth).
"""

import uuid
from datetime import date

from sqlalchemy import BigInteger, Date, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class McpToolUsage(UUIDMixin, TimestampMixin, Base):
    """Conso API agregee par (organization, jour, tool, modele)."""

    __tablename__ = "mcp_tool_usage"

    # organization_id : isolation multi-tenant future (comme GEO). Nullable jusqu'a
    # creation de la table organizations. Index pour les futures requetes filtrees.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    # Nom du tool MCP, ex. "unipile_get_messages"
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Modele LLM, ex. "claude-haiku-4-5-20251001" (le pricing depend du modele)
    model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Nb d'appels LLM agreges sur la cle
    calls: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    # Sommes de tokens (BigInteger : peut depasser 2^31 sur de longues periodes)
    input_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    output_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    cache_read_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    cache_write_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "day",
            "tool_name",
            "model",
            name="uq_mcp_usage_org_day_tool_model",
        ),
        # Requetes filtrees par tool sur une fenetre de dates
        Index("ix_mcp_usage_tool_day", "tool_name", "day"),
    )

    def __repr__(self) -> str:
        return f"<McpToolUsage {self.day} {self.tool_name} {self.model}>"
