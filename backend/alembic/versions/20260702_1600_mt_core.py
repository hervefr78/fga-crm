"""multi_tenant_core

Revision ID: mt_core_001
Revises: geo_audit_001
Create Date: 2026-07-02 16:00:00.000000

Socle multi-tenant (Compass) — phase EXPAND :
- table `organizations` + org par defaut "Fast Growth Advisor" (UUID fixe).
- `users.organization_id` (nullable) backfille vers l'org par defaut.
- `users.is_superadmin` : les admins existants (staff FGA) deviennent super-admins.

Les colonnes restent nullable ici ; la migration CONTRACT finale les passera
NOT NULL une fois tous les writers (routes/syncs) garantis.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op  # noqa: I001

# revision identifiers
revision = "mt_core_001"
down_revision = "geo_audit_001"
branch_labels = None
depends_on = None

_DEFAULT_ORG_ID = "00000000-0000-0000-0000-0000000000fa"
_DEFAULT_ORG_NAME = "Fast Growth Advisor"
_DEFAULT_ORG_SLUG = "fga"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # Org par defaut : recoit tout l'existant mono-tenant.
    op.execute(
        sa.text(
            "INSERT INTO organizations (id, name, slug, is_active) "
            "VALUES (:id, :name, :slug, true)"
        ).bindparams(id=_DEFAULT_ORG_ID, name=_DEFAULT_ORG_NAME, slug=_DEFAULT_ORG_SLUG)
    )

    # users : rattachement a l'org + flag super-admin.
    op.add_column("users", sa.Column("organization_id", UUID(as_uuid=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_superadmin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_foreign_key(
        "fk_users_organization_id",
        "users",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])

    # Backfill : tous les users existants -> org par defaut ; admins -> super-admin.
    op.execute(
        sa.text("UPDATE users SET organization_id = :id WHERE organization_id IS NULL").bindparams(
            id=_DEFAULT_ORG_ID
        )
    )
    # UN seul super-admin par org (l'admin le plus ancien), pas tous les admins.
    op.execute(sa.text(
        "UPDATE users SET is_superadmin = true WHERE id IN ("
        "  SELECT DISTINCT ON (organization_id) id FROM users "
        "  WHERE role = 'admin' ORDER BY organization_id, created_at ASC"
        ")"
    ))


def downgrade() -> None:
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_constraint("fk_users_organization_id", "users", type_="foreignkey")
    op.drop_column("users", "is_superadmin")
    op.drop_column("users", "organization_id")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_table("organizations")
