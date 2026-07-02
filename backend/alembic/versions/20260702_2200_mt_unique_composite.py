"""multi_tenant_unique_composite

Remplace les contraintes UNIQUE GLOBALES (bug d'isolation multi-tenant) par des
contraintes composites (organization_id, X) :
- companies.domain           : ix_companies_domain (unique global) -> (org, domain)
- companies.startup_radar_id : unique global            -> (org, startup_radar_id)
- contacts.startup_radar_id  : unique global            -> (org, startup_radar_id)

Sans ce fix, deux organisations ne peuvent pas avoir une societe avec le meme
domaine / le meme lead Startup Radar : l'INSERT leve IntegrityError (bug hunt
2026-07-02, findings #1 et #2).

Sens du changement = LOOSENING (global -> composite) : toute donnee existante
unique globalement est trivialement unique par (org, X). Migration prod-safe,
aucun doublon a resoudre au prealable.

Revision ID: mt_unique_composite_001
Revises: enrichment_bulk_001
Create Date: 2026-07-02
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "mt_unique_composite_001"
down_revision = "enrichment_bulk_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop des contraintes/index uniques GLOBAUX
    op.drop_index("ix_companies_domain", table_name="companies")
    op.drop_constraint("companies_startup_radar_id_key", "companies", type_="unique")
    op.drop_constraint("contacts_startup_radar_id_key", "contacts", type_="unique")

    # 2. Creation des contraintes uniques COMPOSITES (organization_id, X).
    #    domain/startup_radar_id nullables -> NULL distincts (plusieurs par org OK).
    op.create_unique_constraint(
        "uq_companies_org_domain", "companies", ["organization_id", "domain"]
    )
    op.create_unique_constraint(
        "uq_companies_org_startup_radar_id", "companies", ["organization_id", "startup_radar_id"]
    )
    op.create_unique_constraint(
        "uq_contacts_org_startup_radar_id", "contacts", ["organization_id", "startup_radar_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_contacts_org_startup_radar_id", "contacts", type_="unique")
    op.drop_constraint("uq_companies_org_startup_radar_id", "companies", type_="unique")
    op.drop_constraint("uq_companies_org_domain", "companies", type_="unique")

    op.create_unique_constraint("contacts_startup_radar_id_key", "contacts", ["startup_radar_id"])
    op.create_unique_constraint("companies_startup_radar_id_key", "companies", ["startup_radar_id"])
    op.create_index("ix_companies_domain", "companies", ["domain"], unique=True)
