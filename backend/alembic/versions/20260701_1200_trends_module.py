"""trends_module

Revision ID: trends_module_001
Revises: mcp_usage_001
Create Date: 2026-07-01 12:00:00.000000

Ajoute le module Trends (signal de demande de marche) :
- trend_categories (referentiel categories + mapping fournisseur)
- trend_category_seeds (seeds par categorie — Deep Research P4)
- trend_jobs (executions quick|deep, dedup via request_hash)
- trend_snapshots (resultat brut normalise, immutable)
- trend_keywords (keywords deroules — P4)
- trend_reports (synthese lisible, un par job)
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op  # noqa: I001

# revision identifiers
revision = "trends_module_001"
down_revision = "mcp_usage_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. trend_categories
    # -----------------------------------------------------------------
    op.create_table(
        "trend_categories",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("provider_category_id", sa.Text(), nullable=True),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("parent_slug", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
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
    op.create_index("ix_trend_categories_slug", "trend_categories", ["slug"], unique=True)

    # -----------------------------------------------------------------
    # 2. trend_category_seeds
    # -----------------------------------------------------------------
    op.create_table(
        "trend_category_seeds",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trend_categories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("term", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False, server_default=sa.text("'fr'")),
        sa.Column("country", sa.Text(), nullable=False, server_default=sa.text("'FR'")),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
    op.create_index(
        "ix_trend_category_seeds_category_id", "trend_category_seeds", ["category_id"]
    )

    # -----------------------------------------------------------------
    # 3. trend_jobs
    # -----------------------------------------------------------------
    op.create_table(
        "trend_jobs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("provider_primary", sa.Text(), nullable=False),
        sa.Column("provider_effective", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("params_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("steps_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("steps_done", sa.Integer(), nullable=False, server_default=sa.text("0")),
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
    op.create_index("ix_trend_jobs_organization_id", "trend_jobs", ["organization_id"])
    op.create_index("ix_trend_jobs_request_hash", "trend_jobs", ["request_hash"])
    op.create_index("ix_trend_jobs_hash_status", "trend_jobs", ["request_hash", "status"])

    # -----------------------------------------------------------------
    # 4. trend_snapshots (immutable — created_at seul)
    # -----------------------------------------------------------------
    op.create_table(
        "trend_snapshots",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trend_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trend_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("timeframe", sa.Text(), nullable=False),
        sa.Column("payload_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_trend_snapshots_job_id", "trend_snapshots", ["job_id"])

    # -----------------------------------------------------------------
    # 5. trend_keywords (immutable — created_at seul)
    # -----------------------------------------------------------------
    op.create_table(
        "trend_keywords",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "snapshot_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trend_snapshots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keyword", sa.Text(), nullable=False),
        sa.Column("cluster", sa.Text(), nullable=True),
        sa.Column("source_kind", sa.Text(), nullable=False),
        sa.Column("interest_score", sa.Numeric(6, 2), nullable=True),
        sa.Column("growth_score", sa.Numeric(8, 2), nullable=True),
        sa.Column("breakout", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "provider_meta_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_trend_keywords_snapshot_id", "trend_keywords", ["snapshot_id"])

    # -----------------------------------------------------------------
    # 6. trend_reports (un par job — created_at seul)
    # -----------------------------------------------------------------
    op.create_table(
        "trend_reports",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("trend_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("summary_md", sa.Text(), nullable=True),
        sa.Column("insights_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("opportunity_score", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_trend_reports_job_id", "trend_reports", ["job_id"], unique=True)


def downgrade() -> None:
    op.drop_table("trend_reports")
    op.drop_table("trend_keywords")
    op.drop_table("trend_snapshots")
    op.drop_table("trend_jobs")
    op.drop_table("trend_category_seeds")
    op.drop_table("trend_categories")
