"""multi_tenant_contract

Revision ID: mt_contract_001
Revises: mt_aux_001
Create Date: 2026-07-02 19:00:00.000000

Phase CONTRACT : passe organization_id NOT NULL sur les tables ou TOUS les writers
taggent desormais l'org (users + coeur CRM + tags/templates/apikeys + top-level
modules). Prerequis : les migrations expand (mt_core/mt_tables/mt_aux) ont backfille
l'existant vers l'org par defaut.

Laissees NULLABLE volontairement (sous-entites creees par des tasks Celery, isolees
via leur parent) : geo_runs, geo_metrics_daily, trend_snapshots, trend_keywords,
trend_reports, et les referentiels globaux trend_categories/trend_category_seeds.
geo_brands/geo_prompts restent nullable tant que la task d'audit cree une marque
ephemere sans org (a propager dans une passe dediee).
"""

import sqlalchemy as sa

from alembic import op  # noqa: I001

# revision identifiers
revision = "mt_contract_001"
down_revision = "mt_aux_001"
branch_labels = None
depends_on = None

_NOT_NULL_TABLES = (
    "users",
    "companies",
    "contacts",
    "deals",
    "activities",
    "tasks",
    "tags",
    "email_templates",
    "api_keys",
    "trend_jobs",
    "geo_audit_jobs",
    "mcp_tool_usage",
)


def upgrade() -> None:
    for table in _NOT_NULL_TABLES:
        op.alter_column(table, "organization_id", existing_type=sa.dialects.postgresql.UUID(), nullable=False)


def downgrade() -> None:
    for table in _NOT_NULL_TABLES:
        op.alter_column(table, "organization_id", existing_type=sa.dialects.postgresql.UUID(), nullable=True)
