"""add source to deal

Revision ID: eb85b5950356
Revises: daa19e2fefdb
Create Date: 2026-05-01 14:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eb85b5950356'
down_revision: Union[str, None] = 'daa19e2fefdb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Champ source d'attribution (ex: "mcp", "import", "manual"...)
    # — borne a 100 chars (DC1), nullable car les deals existants n'ont pas de source.
    op.add_column(
        'deals',
        sa.Column('source', sa.String(length=100), nullable=True),
    )
    op.create_index(op.f('ix_deals_source'), 'deals', ['source'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_deals_source'), table_name='deals')
    op.drop_column('deals', 'source')
