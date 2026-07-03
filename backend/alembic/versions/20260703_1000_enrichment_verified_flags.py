"""enrichment_verified_flags

Flags de provenance Icypeas (Feature B — enrichissement des contacts existants) :
- contacts.email_verified_by_icypeas  : email trouve/verifie par Icypeas
- companies.domain_verified_by_icypeas : domaine valide via un email pro Icypeas

Additif (colonnes NOT NULL avec server_default false) -> prod-safe.

Revision ID: enrichment_verified_flags_001
Revises: mt_unique_composite_001
Create Date: 2026-07-03
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "enrichment_verified_flags_001"
down_revision = "mt_unique_composite_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contacts",
        sa.Column(
            "email_verified_by_icypeas", sa.Boolean(), nullable=False, server_default="false"
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "domain_verified_by_icypeas", sa.Boolean(), nullable=False, server_default="false"
        ),
    )


def downgrade() -> None:
    op.drop_column("companies", "domain_verified_by_icypeas")
    op.drop_column("contacts", "email_verified_by_icypeas")
