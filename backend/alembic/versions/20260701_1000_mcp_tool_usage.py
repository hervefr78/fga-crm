"""mcp_tool_usage

Revision ID: mcp_usage_001
Revises: geo_org_id_001
Create Date: 2026-07-01 10:00:00.000000

Ajoute la table mcp_tool_usage : agregat quotidien de la conso API Anthropic
par (organization_id, jour, tool MCP, modele). Tokens bruts stockes (BigInteger),
cout calcule a la lecture. Alimentee par le MCP via POST /mcp-usage/ingest.

Ecrite a la main (pas d'autogenerate). down_revision = tete actuelle de la
chaine (geo_org_id_001).
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op  # noqa: I001

# revision identifiers
revision = "mcp_usage_001"
down_revision = "geo_org_id_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mcp_tool_usage",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "input_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "output_tokens", sa.BigInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "cache_read_tokens",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "cache_write_tokens",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "organization_id",
            "day",
            "tool_name",
            "model",
            name="uq_mcp_usage_org_day_tool_model",
        ),
    )

    # Index isolation multi-tenant future (comme GEO)
    op.create_index(
        "ix_mcp_tool_usage_organization_id",
        "mcp_tool_usage",
        ["organization_id"],
    )
    # Index sur tool_name seul (filtre frequent)
    op.create_index(
        "ix_mcp_tool_usage_tool_name",
        "mcp_tool_usage",
        ["tool_name"],
    )
    # Index composite (tool, jour) pour les requetes filtrees par tool sur une fenetre
    op.create_index(
        "ix_mcp_usage_tool_day",
        "mcp_tool_usage",
        ["tool_name", "day"],
    )


def downgrade() -> None:
    op.drop_index("ix_mcp_usage_tool_day", table_name="mcp_tool_usage")
    op.drop_index("ix_mcp_tool_usage_tool_name", table_name="mcp_tool_usage")
    op.drop_index("ix_mcp_tool_usage_organization_id", table_name="mcp_tool_usage")
    op.drop_table("mcp_tool_usage")
