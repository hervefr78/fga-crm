"""geo_module

Revision ID: geo_module_001
Revises: ecc9c759d74d
Create Date: 2026-06-24 10:00:00.000000

Ajoute le module GEO (Generative Engine Optimization) :
- Table geo_brands (marques suivies + concurrents decouverts)
- Table geo_prompts (univers de prompts par marque)
- Table geo_runs (une ligne par execution)
- Table geo_metrics_daily (agregats pre-calcules)
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op  # noqa: I001

# revision identifiers
revision = "geo_module_001"
down_revision = "ecc9c759d74d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. geo_brands
    # -----------------------------------------------------------------
    op.create_table(
        "geo_brands",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("aliases", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_owned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
    op.create_index("ix_geo_brands_slug", "geo_brands", ["slug"], unique=True)

    # -----------------------------------------------------------------
    # 2. geo_prompts
    # -----------------------------------------------------------------
    op.create_table(
        "geo_prompts",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "brand_id",
            UUID(as_uuid=True),
            sa.ForeignKey("geo_brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("persona", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=False, server_default=sa.text("'FR'")),
        sa.Column("language", sa.Text(), nullable=False, server_default=sa.text("'fr'")),
        sa.Column("tags", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("priority", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
    op.create_index("ix_geo_prompts_brand_id", "geo_prompts", ["brand_id"])

    # -----------------------------------------------------------------
    # 3. geo_runs (immutable — created_at seul, pas d'updated_at)
    # -----------------------------------------------------------------
    op.create_table(
        "geo_runs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "prompt_id",
            UUID(as_uuid=True),
            sa.ForeignKey("geo_prompts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            UUID(as_uuid=True),
            sa.ForeignKey("geo_brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_index", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("engine", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column(
            "run_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("raw_answer", sa.Text(), nullable=True),
        sa.Column("citations", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("brands_found", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("brand_mentioned", sa.Boolean(), nullable=True),
        sa.Column("brand_position", sa.Integer(), nullable=True),
        sa.Column("brand_sentiment", sa.Text(), nullable=True),
        sa.Column("brand_recommended", sa.Boolean(), nullable=True),
        sa.Column("appearance", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_geo_runs_brand_engine_run_at",
        "geo_runs",
        ["brand_id", "engine", "run_at"],
    )
    op.create_index(
        "ix_geo_runs_prompt_run_at",
        "geo_runs",
        ["prompt_id", "run_at"],
    )
    # Contrainte unique anti-doublon : (prompt_id, engine, run_index, run_at::date)
    # Index fonctionnel (cast date) — non exprimable cote modele SQLAlchemy portable.
    op.execute(
        "CREATE UNIQUE INDEX uq_geo_runs_prompt_engine_idx_day "
        "ON geo_runs (prompt_id, engine, run_index, ((run_at AT TIME ZONE 'UTC')::date))"
    )

    # -----------------------------------------------------------------
    # 4. geo_metrics_daily
    # -----------------------------------------------------------------
    op.create_table(
        "geo_metrics_daily",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column(
            "brand_id",
            UUID(as_uuid=True),
            sa.ForeignKey("geo_brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("engine", sa.Text(), nullable=False),
        sa.Column("visibility_rate", sa.Numeric(6, 2), nullable=True),
        sa.Column("sov", sa.Numeric(6, 2), nullable=True),
        sa.Column("sov_weighted", sa.Numeric(6, 2), nullable=True),
        sa.Column("sentiment_avg", sa.Numeric(4, 2), nullable=True),
        sa.Column("reco_rate", sa.Numeric(6, 2), nullable=True),
        sa.Column("runs_total", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "day", "brand_id", "engine", name="uq_geo_metrics_day_brand_engine"
        ),
    )
    op.create_index("ix_geo_metrics_daily_brand_id", "geo_metrics_daily", ["brand_id"])


def downgrade() -> None:
    op.drop_table("geo_metrics_daily")
    op.execute("DROP INDEX IF EXISTS uq_geo_runs_prompt_engine_idx_day")
    op.drop_table("geo_runs")
    op.drop_table("geo_prompts")
    op.drop_table("geo_brands")
