"""Tests P2 (DB) : SuppressionService + ProvenanceService."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrichment import EnrichmentProvenance
from app.services.enrichment.provenance import record_provenance
from app.services.enrichment.suppression import add_suppression, is_suppressed


async def test_suppression_email_and_domain(db_session: AsyncSession, test_org):
    oid = test_org.id
    assert await is_suppressed(db_session, organization_id=oid, email="x@acme.fr") is False
    await add_suppression(db_session, reason="opt_out", organization_id=oid, email="X@Acme.fr")
    await add_suppression(db_session, reason="manual", organization_id=oid, domain="Blocked.com")
    # match insensible a la casse (stocke en lower)
    assert await is_suppressed(db_session, organization_id=oid, email="x@acme.fr") is True
    assert await is_suppressed(db_session, organization_id=oid, domain="blocked.com") is True
    assert await is_suppressed(db_session, organization_id=oid, email="autre@acme.fr") is False


async def test_suppression_scoped_by_org(db_session: AsyncSession, test_org):
    """L'opt-out d'une org ne s'applique PAS a une autre org (pas de contamination)."""
    import uuid

    from app.models.organization import Organization

    other = Organization(id=uuid.uuid4(), name="Autre", slug=f"o-{uuid.uuid4().hex[:8]}")
    db_session.add(other)
    await db_session.flush()

    await add_suppression(db_session, reason="opt_out", organization_id=test_org.id, email="p@x.fr")
    assert await is_suppressed(db_session, organization_id=test_org.id, email="p@x.fr") is True
    assert await is_suppressed(db_session, organization_id=other.id, email="p@x.fr") is False


async def test_suppression_no_criteria_returns_false(db_session: AsyncSession, test_org):
    assert await is_suppressed(db_session, organization_id=test_org.id) is False


async def test_provenance_record_adds_row(db_session: AsyncSession):
    await record_provenance(
        db_session, entity_type="email", field="email", source="mock",
        source_detail="mock.email_finder",
    )
    await db_session.commit()
    n = (
        await db_session.execute(select(func.count()).select_from(EnrichmentProvenance))
    ).scalar()
    assert n == 1
    ev = (await db_session.execute(select(EnrichmentProvenance))).scalar_one()
    assert ev.legal_basis == "legitimate_interest"
    assert ev.source == "mock"
