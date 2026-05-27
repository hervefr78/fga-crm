"""service_auth_api_keys

Revision ID: ecc9c759d74d
Revises: a3f8c1d92e4b
Create Date: 2026-05-27 10:00:00.000000

Ajoute :
- Colonne users.is_service (service accounts MCP, Nomo-IA…)
- Table api_keys (SHA-256, scopes JSONB, expiration, revocation)

Standard : SERVICE_AUTH_STANDARD.md (prefix crm_)
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op  # noqa: I001

# revision identifiers
revision = "ecc9c759d74d"
down_revision = "a3f8c1d92e4b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Colonne users.is_service — service accounts non-humains
    op.add_column(
        "users",
        sa.Column(
            "is_service",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # 2. Table api_keys
    op.create_table(
        "api_keys",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("scopes", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
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

    # Index sur key_hash (unique) + index partiel actives uniquement (comme spec)
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"], unique=True)
    op.create_index(
        "idx_api_keys_hash_active",
        "api_keys",
        ["key_hash"],
        unique=False,
        postgresql_where=sa.text("is_active = TRUE"),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_column("users", "is_service")
