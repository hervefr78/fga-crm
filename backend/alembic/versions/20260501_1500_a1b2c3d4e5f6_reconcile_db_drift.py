"""reconcile DB drift — colonnes Company manquantes

Contexte : la DB de dev (et potentiellement prod) a ete creee historiquement
via Base.metadata.create_all() avant que les colonnes lead_source et
vat_number ne soient ajoutees au modele Company. La baseline alembic
daa19e2fefdb les contient mais n'a jamais ete appliquee sur ces DB.

Cette migration ajoute les colonnes/indexes manquants de maniere idempotente
(IF NOT EXISTS). Elle est sans effet sur une DB qui a deja les colonnes
(creee proprement via une baseline neuve).

Revision ID: a1b2c3d4e5f6
Revises: eb85b5950356
Create Date: 2026-05-01 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'eb85b5950356'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Idempotent — IF NOT EXISTS evite un crash si la DB a deja la colonne
    # (cas d'une DB recreee proprement depuis la baseline).
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS lead_source VARCHAR(100)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_companies_lead_source ON companies (lead_source)")
    op.execute("ALTER TABLE companies ADD COLUMN IF NOT EXISTS vat_number VARCHAR(50)")


def downgrade() -> None:
    # Pas de DROP : si on annule cette reconciliation, on remet la DB dans
    # l'etat drift (modele a les colonnes, DB ne les a pas). C'est un no-op
    # volontaire — la reconciliation est forward-only.
    pass
