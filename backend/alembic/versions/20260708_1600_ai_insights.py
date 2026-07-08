"""ai_insights

Workflow IA 3 (spec workflows-ia) — syntheses hebdo du pipeline :
- table ai_insights : syntheses generees par le LLM (org-scopees), la plus
  recente par org/period_days est la synthese courante (cache 24 h).

Additif (nouvelle table) -> prod-safe.

Revision ID: ai_insights_001
Revises: ai_qualification_001
Create Date: 2026-07-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "ai_insights_001"
down_revision = "ai_qualification_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_insights",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("period_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("payload_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_ai_insights_organization_id", "ai_insights", ["organization_id"])
    op.create_index("ix_ai_insights_generated_at", "ai_insights", ["generated_at"])


def downgrade() -> None:
    op.drop_table("ai_insights")
