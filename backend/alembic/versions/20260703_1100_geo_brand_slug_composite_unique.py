"""geo_brand_slug_composite_unique

Remplace l'unicite GLOBALE du slug des marques GEO (bug d'isolation multi-tenant,
FIX #9) par une unicite COMPOSITE (organization_id, slug) :
- geo_brands.slug : index unique global `ix_geo_brands_slug`
                    -> index non-unique `ix_geo_brands_slug`
                       + contrainte unique composite `uq_geo_brands_org_slug`

Sans ce fix, deux organisations ne peuvent pas suivre une marque au meme slug
(ex: deux clients qui suivent "acme") : le second INSERT leve IntegrityError, et
la dedup applicative fuit les marques d'autres orgs.

Sens du changement = LOOSENING (global -> composite) : toute donnee existante
unique globalement reste trivialement unique par (org, slug). Migration prod-safe,
aucun doublon a resoudre au prealable.

Revision ID: geo_brand_slug_composite_001
Revises: enrichment_verified_flags_001
Create Date: 2026-07-03
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "geo_brand_slug_composite_001"
down_revision = "enrichment_verified_flags_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop de l'index UNIQUE GLOBAL sur slug.
    op.drop_index("ix_geo_brands_slug", table_name="geo_brands")
    # 2. Recreation d'un index NON-UNIQUE (le model garde index=True sur slug).
    op.create_index("ix_geo_brands_slug", "geo_brands", ["slug"], unique=False)
    # 3. Contrainte unique COMPOSITE (organization_id, slug).
    op.create_unique_constraint(
        "uq_geo_brands_org_slug", "geo_brands", ["organization_id", "slug"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_geo_brands_org_slug", "geo_brands", type_="unique")
    op.drop_index("ix_geo_brands_slug", table_name="geo_brands")
    op.create_index("ix_geo_brands_slug", "geo_brands", ["slug"], unique=True)
