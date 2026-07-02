"""multi_tenant_aux_tables

Revision ID: mt_aux_001
Revises: mt_tables_001
Create Date: 2026-07-02 18:00:00.000000

Phase EXPAND (auxiliaires) :
- `organization_id` (nullable + FK + index) sur tags/email_templates/api_keys + backfill.
- Backfill des tables modules (geo_*, trend_jobs, mcp_tool_usage) qui avaient deja
  une colonne organization_id nullable jamais peuplee -> org par defaut.

NOT NULL applique au CONTRACT final.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op  # noqa: I001

# revision identifiers
revision = "mt_aux_001"
down_revision = "mt_tables_001"
branch_labels = None
depends_on = None

_DEFAULT_ORG_ID = "00000000-0000-0000-0000-0000000000fa"

# Tables ou la colonne organization_id est AJOUTEE (nouvelles).
_NEW_ORG_TABLES = ("tags", "email_templates", "api_keys")

# Tables modules ou la colonne existe deja (nullable) -> simple backfill.
_EXISTING_ORG_TABLES = (
    "geo_brands", "geo_prompts", "geo_runs", "geo_metrics_daily",
    "geo_audit_jobs", "trend_jobs", "mcp_tool_usage",
)


def _backfill(table: str) -> None:
    # table vient de constantes internes, pas d'input externe -> pas d'injection.
    op.execute(
        sa.text(
            f"UPDATE {table} SET organization_id = :id WHERE organization_id IS NULL"  # noqa: S608
        ).bindparams(id=_DEFAULT_ORG_ID)
    )


def upgrade() -> None:
    for table in _NEW_ORG_TABLES:
        op.add_column(table, sa.Column("organization_id", UUID(as_uuid=True), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_organization_id",
            table,
            "organizations",
            ["organization_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_organization_id", table, ["organization_id"])
        _backfill(table)

    for table in _EXISTING_ORG_TABLES:
        _backfill(table)


def downgrade() -> None:
    for table in reversed(_NEW_ORG_TABLES):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organization_id", table, type_="foreignkey")
        op.drop_column(table, "organization_id")
