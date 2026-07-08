"""ai_scoring

Workflows IA natifs (spec workflows-ia) — socle + scoring des deals :
- deals.product : produit vendu (audit-999 | founder-499 | advisory), agregats + scoring
- deals.ai_* : resultat du scoring (score 0-100, tier A/B/C, rationale,
  signaux manquants, date, meta {model, prompt_version})
- table ai_workflow_runs : audit org-scope de chaque appel IA (tokens, statut)

Additif (colonnes nullable + nouvelle table) -> prod-safe.

Revision ID: ai_scoring_001
Revises: geo_brand_slug_composite_001
Create Date: 2026-07-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "ai_scoring_001"
down_revision = "geo_brand_slug_composite_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- deals : product + colonnes de scoring IA ---
    op.add_column("deals", sa.Column("product", sa.String(30), nullable=True))
    op.create_index("ix_deals_product", "deals", ["product"])
    op.add_column("deals", sa.Column("ai_score", sa.Integer(), nullable=True))
    op.add_column("deals", sa.Column("ai_tier", sa.String(1), nullable=True))
    op.create_index("ix_deals_ai_tier", "deals", ["ai_tier"])
    op.add_column("deals", sa.Column("ai_score_rationale", sa.Text(), nullable=True))
    op.add_column("deals", sa.Column("ai_score_missing", JSONB(), nullable=True))
    op.add_column(
        "deals", sa.Column("ai_scored_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("deals", sa.Column("ai_score_meta", JSONB(), nullable=True))

    # --- audit des appels IA (org-scope) ---
    op.create_table(
        "ai_workflow_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("workflow", sa.String(30), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=True),
        sa.Column("target_id", UUID(as_uuid=True), nullable=True),
        sa.Column("prompt_version", sa.String(20), nullable=False),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ai_workflow_runs_organization_id", "ai_workflow_runs", ["organization_id"]
    )
    op.create_index("ix_ai_workflow_runs_workflow", "ai_workflow_runs", ["workflow"])
    op.create_index("ix_ai_workflow_runs_target_id", "ai_workflow_runs", ["target_id"])


def downgrade() -> None:
    op.drop_table("ai_workflow_runs")
    op.drop_index("ix_deals_ai_tier", table_name="deals")
    op.drop_index("ix_deals_product", table_name="deals")
    for col in (
        "ai_score_meta", "ai_scored_at", "ai_score_missing",
        "ai_score_rationale", "ai_tier", "ai_score", "product",
    ):
        op.drop_column("deals", col)
