"""enrichment_module

Revision ID: enrichment_001
Revises: geo_audit_001
Create Date: 2026-07-02 10:00:00.000000

Feature d'enrichissement d'emails B2B (brique Compass). Tables d'ETAT
d'enrichissement (jobs, provenance RGPD, suppression, verifications email).
Ne duplique pas companies/contacts (source de verite CRM).
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op  # noqa: I001

# revision identifiers
revision = "enrichment_001"
down_revision = "geo_audit_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1. enrichment_jobs
    # -----------------------------------------------------------------
    op.create_table(
        "enrichment_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("target_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("stats_json", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_enrichment_jobs_organization_id", "enrichment_jobs", ["organization_id"])
    op.create_index("ix_enrichment_jobs_org_status", "enrichment_jobs", ["organization_id", "status"])

    # -----------------------------------------------------------------
    # 2. enrichment_provenance (immuable — created_at seul)
    # -----------------------------------------------------------------
    op.create_table(
        "enrichment_provenance",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column(
            "contact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_detail", sa.Text(), nullable=True),
        sa.Column("legal_basis", sa.Text(), nullable=False, server_default=sa.text("'legitimate_interest'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_enrichment_provenance_organization_id", "enrichment_provenance", ["organization_id"])
    op.create_index("ix_enrichment_provenance_contact", "enrichment_provenance", ["contact_id"])

    # -----------------------------------------------------------------
    # 3. enrichment_suppression
    # -----------------------------------------------------------------
    op.create_table(
        "enrichment_suppression",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("domain", sa.Text(), nullable=True),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_enrichment_suppression_organization_id", "enrichment_suppression", ["organization_id"])
    op.create_index("ix_enrichment_suppression_email", "enrichment_suppression", ["email"])
    op.create_index("ix_enrichment_suppression_domain", "enrichment_suppression", ["domain"])

    # -----------------------------------------------------------------
    # 4. enrichment_email_verifications
    # -----------------------------------------------------------------
    op.create_table(
        "enrichment_email_verifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "contact_id",
            UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("domain_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("deliverable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_enrichment_email_verifications_organization_id", "enrichment_email_verifications", ["organization_id"])
    op.create_index("ix_enrichment_email_verifications_email", "enrichment_email_verifications", ["email"])


def downgrade() -> None:
    op.drop_table("enrichment_email_verifications")
    op.drop_table("enrichment_suppression")
    op.drop_table("enrichment_provenance")
    op.drop_table("enrichment_jobs")
