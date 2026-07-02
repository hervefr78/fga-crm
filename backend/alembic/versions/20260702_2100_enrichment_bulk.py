"""enrichment_bulk

Revision ID: enrichment_bulk_001
Revises: enrichment_001
Create Date: 2026-07-02 21:00:00.000000

Bulk Icypeas (async/webhook) : un bulk = plusieurs items soumis en une fois
(POST /bulk-search), resolus via callback webhook. `enrichment_bulks` = le bulk
(file Icypeas -> job/org + compteurs) ; `enrichment_bulk_items` = le contexte
societe+personne stocke a la soumission, resolu quand le callback arrive.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op  # noqa: I001

# revision identifiers
revision = "enrichment_bulk_001"
down_revision = "enrichment_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "enrichment_bulks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("enrichment_jobs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("file", sa.Text(), nullable=False),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'submitted'")),
        sa.Column("total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("done", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("found", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_enrichment_bulks_organization_id", "enrichment_bulks", ["organization_id"])
    op.create_index("ix_enrichment_bulks_file", "enrichment_bulks", ["file"])

    op.create_table(
        "enrichment_bulk_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("bulk_id", UUID(as_uuid=True), sa.ForeignKey("enrichment_bulks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("context_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("certainty", sa.Text(), nullable=True),
        sa.Column("contact_id", UUID(as_uuid=True), sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_enrichment_bulk_items_organization_id", "enrichment_bulk_items", ["organization_id"])
    op.create_index("ix_enrichment_bulk_items_external_id", "enrichment_bulk_items", ["external_id"])
    op.create_index("ix_enrichment_bulk_items_bulk_ext", "enrichment_bulk_items", ["bulk_id", "external_id"])


def downgrade() -> None:
    op.drop_table("enrichment_bulk_items")
    op.drop_table("enrichment_bulks")
