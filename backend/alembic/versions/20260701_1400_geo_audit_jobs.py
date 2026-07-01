"""geo_audit_jobs

Revision ID: geo_audit_001
Revises: trends_module_001
Create Date: 2026-07-01 14:00:00.000000

Table de tracking des mesures de visibilite GEO a la demande (integration
Startup Radar) : SR envoie company/domain/prompts, le CRM mesure sur Perplexity
via une marque ephemere et agrege le resultat. request_hash = deduplication.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op  # noqa: I001

# revision identifiers
revision = "geo_audit_001"
down_revision = "trends_module_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "geo_audit_jobs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("engine", sa.Text(), nullable=False, server_default=sa.text("'perplexity'")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column(
            "brand_id",
            UUID(as_uuid=True),
            sa.ForeignKey("geo_brands.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("params_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
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
    )
    op.create_index("ix_geo_audit_jobs_organization_id", "geo_audit_jobs", ["organization_id"])
    op.create_index("ix_geo_audit_jobs_domain", "geo_audit_jobs", ["domain"])
    op.create_index("ix_geo_audit_jobs_request_hash", "geo_audit_jobs", ["request_hash"])
    op.create_index("ix_geo_audit_jobs_hash_status", "geo_audit_jobs", ["request_hash", "status"])


def downgrade() -> None:
    op.drop_table("geo_audit_jobs")
