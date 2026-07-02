"""multi_tenant_soft_delete

Revision ID: mt_softdelete_001
Revises: mt_contract_001
Create Date: 2026-07-02 20:00:00.000000

Passe les FK organization_id de CASCADE -> RESTRICT : on ne supprime jamais
physiquement une organisation qui porte des donnees. La desactivation d'un tenant
se fait en soft-delete (Organization.is_active = false), applique a l'auth.
"""

from alembic import op  # noqa: I001

# revision identifiers
revision = "mt_softdelete_001"
down_revision = "mt_contract_001"
branch_labels = None
depends_on = None

# Tables portant une FK organization_id -> organizations (les modules geo/trends/mcp
# n'ont PAS de FK, juste une colonne indexee).
_FK_TABLES = (
    "users",
    "companies",
    "contacts",
    "deals",
    "activities",
    "tasks",
    "tags",
    "email_templates",
    "api_keys",
)


def _recreate_fk(table: str, ondelete: str) -> None:
    name = f"fk_{table}_organization_id"
    op.drop_constraint(name, table, type_="foreignkey")
    op.create_foreign_key(
        name, table, "organizations", ["organization_id"], ["id"], ondelete=ondelete
    )


def upgrade() -> None:
    for table in _FK_TABLES:
        _recreate_fk(table, "RESTRICT")


def downgrade() -> None:
    for table in _FK_TABLES:
        _recreate_fk(table, "CASCADE")
