"""lead_signals

Lead Engine V1.1 (docs/LEAD_ENGINE_VISION.md) — Signal Inbox :
- table lead_signals : signaux detectes par le scan periodique (org-scopes,
  dedupliques par dedup_key sur une fenetre glissante).

Additif (nouvelle table) -> prod-safe.

Revision ID: lead_signals_001
Revises: ai_insights_001
Create Date: 2026-07-09
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision = "lead_signals_001"
down_revision = "ai_insights_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lead_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=False),
        sa.Column("signal_type", sa.String(30), nullable=False),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("payload_json", JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="new"),
        sa.Column("dedup_key", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_lead_signals_organization_id", "lead_signals", ["organization_id"])
    op.create_index("ix_lead_signals_signal_type", "lead_signals", ["signal_type"])
    op.create_index("ix_lead_signals_company_id", "lead_signals", ["company_id"])
    op.create_index("ix_lead_signals_status", "lead_signals", ["status"])
    op.create_index("ix_lead_signals_org_dedup", "lead_signals", ["organization_id", "dedup_key"])


def downgrade() -> None:
    op.drop_table("lead_signals")
