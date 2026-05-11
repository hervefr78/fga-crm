"""Add funding multi-source fields synced from Startup Radar

Ajoute :
- Company : siren, funding_date, funding_amount, funding_series, funding_sources
- Contact : enrichment_source, email_pattern_used, linkedin_url_status
- Task : company_id (permet de rattacher une task directement a une company,
  utilise pour la task "Qualifier la levee" sans contact specifique)

Revision ID: a3f8c1d92e4b
Revises: daa19e2fefdb
Create Date: 2026-05-11 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a3f8c1d92e4b"
down_revision: Union[str, None] = "daa19e2fefdb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Company : funding fields ---
    op.add_column("companies", sa.Column("siren", sa.String(length=9), nullable=True))
    op.create_index(op.f("ix_companies_siren"), "companies", ["siren"], unique=False)

    op.add_column("companies", sa.Column("funding_date", sa.Date(), nullable=True))
    op.create_index(
        op.f("ix_companies_funding_date"), "companies", ["funding_date"], unique=False,
    )

    op.add_column("companies", sa.Column("funding_amount", sa.BigInteger(), nullable=True))
    op.create_index(
        op.f("ix_companies_funding_amount"), "companies", ["funding_amount"], unique=False,
    )

    op.add_column("companies", sa.Column("funding_series", sa.String(length=50), nullable=True))
    op.add_column(
        "companies",
        sa.Column("funding_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # --- Contact : enrichment fields ---
    op.add_column(
        "contacts", sa.Column("enrichment_source", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "contacts", sa.Column("email_pattern_used", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "contacts", sa.Column("linkedin_url_status", sa.String(length=20), nullable=True),
    )

    # --- Task : ajout company_id (FK companies.id, ON DELETE SET NULL) ---
    op.add_column("tasks", sa.Column("company_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_company_id_companies",
        "tasks",
        "companies",
        ["company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_tasks_company_id"), "tasks", ["company_id"], unique=False)


def downgrade() -> None:
    # Task
    op.drop_index(op.f("ix_tasks_company_id"), table_name="tasks")
    op.drop_constraint("fk_tasks_company_id_companies", "tasks", type_="foreignkey")
    op.drop_column("tasks", "company_id")

    # Contact
    op.drop_column("contacts", "linkedin_url_status")
    op.drop_column("contacts", "email_pattern_used")
    op.drop_column("contacts", "enrichment_source")

    # Company
    op.drop_column("companies", "funding_sources")
    op.drop_column("companies", "funding_series")
    op.drop_index(op.f("ix_companies_funding_amount"), table_name="companies")
    op.drop_column("companies", "funding_amount")
    op.drop_index(op.f("ix_companies_funding_date"), table_name="companies")
    op.drop_column("companies", "funding_date")
    op.drop_index(op.f("ix_companies_siren"), table_name="companies")
    op.drop_column("companies", "siren")
