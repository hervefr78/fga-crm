"""ai_qualification

Workflow IA 2 (spec workflows-ia) — qualification SPICED des contacts inbound :
- contacts.ai_qualification : grille SPICED complete + rationale (JSONB)
- contacts.ai_routing : fast_track | standard | human_review (indexe — file de revue)
- contacts.ai_qualified_at : date de derniere qualification

Additif (colonnes nullable) -> prod-safe.

Revision ID: ai_qualification_001
Revises: ai_scoring_001
Create Date: 2026-07-08
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = "ai_qualification_001"
down_revision = "ai_scoring_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contacts", sa.Column("ai_qualification", JSONB(), nullable=True))
    op.add_column("contacts", sa.Column("ai_routing", sa.String(20), nullable=True))
    op.create_index("ix_contacts_ai_routing", "contacts", ["ai_routing"])
    op.add_column(
        "contacts", sa.Column("ai_qualified_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_index("ix_contacts_ai_routing", table_name="contacts")
    for col in ("ai_qualified_at", "ai_routing", "ai_qualification"):
        op.drop_column("contacts", col)
