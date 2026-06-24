"""geo_organization_id

Revision ID: geo_org_id_001
Revises: geo_module_001
Create Date: 2026-06-24 11:00:00.000000

Ajoute la colonne organization_id (UUID nullable, sans FK pour l'instant) sur les
4 tables GEO pour preparer l'isolation multi-tenant.

La colonne est nullable et sans contrainte FK sur une table organizations (qui
n'existe pas encore). Quand la table organizations sera creee, une migration
dediee ajoutera la FK et une contrainte NOT NULL apres backfill.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op  # noqa: I001

# revision identifiers
revision = "geo_org_id_001"
down_revision = "geo_module_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    org_col = sa.Column(
        "organization_id",
        UUID(as_uuid=True),
        nullable=True,
    )

    for table in ("geo_brands", "geo_prompts", "geo_runs", "geo_metrics_daily"):
        op.add_column(table, org_col)
        op.create_index(
            f"ix_{table}_organization_id",
            table,
            ["organization_id"],
        )


def downgrade() -> None:
    for table in ("geo_metrics_daily", "geo_runs", "geo_prompts", "geo_brands"):
        op.drop_index(f"ix_{table}_organization_id", table_name=table)
        op.drop_column(table, "organization_id")
