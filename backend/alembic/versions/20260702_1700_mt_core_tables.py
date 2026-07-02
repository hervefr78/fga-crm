"""multi_tenant_core_tables

Revision ID: mt_tables_001
Revises: mt_core_001
Create Date: 2026-07-02 17:00:00.000000

Phase EXPAND (2/2 pour le coeur CRM) : ajoute `organization_id` (nullable) aux
tables metier companies/contacts/deals/activities/tasks + FK + index, et backfill
l'existant vers l'org par defaut. Passage NOT NULL au CONTRACT final.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op  # noqa: I001

# revision identifiers
revision = "mt_tables_001"
down_revision = "mt_core_001"
branch_labels = None
depends_on = None

_DEFAULT_ORG_ID = "00000000-0000-0000-0000-0000000000fa"
_TABLES = ("companies", "contacts", "deals", "activities", "tasks")


def upgrade() -> None:
    for table in _TABLES:
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
        # table vient de _TABLES (constante), pas d'input externe -> pas d'injection.
        op.execute(
            sa.text(
                f"UPDATE {table} SET organization_id = :id WHERE organization_id IS NULL"  # noqa: S608
            ).bindparams(id=_DEFAULT_ORG_ID)
        )


def downgrade() -> None:
    for table in reversed(_TABLES):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_constraint(f"fk_{table}_organization_id", table, type_="foreignkey")
        op.drop_column(table, "organization_id")
