"""Tests P2 (DB) : SuppressionService + ProvenanceService."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrichment import EnrichmentProvenance
from app.services.enrichment.provenance import record_provenance
from app.services.enrichment.suppression import add_suppression, is_suppressed


async def test_suppression_email_and_domain(db_session: AsyncSession):
    assert await is_suppressed(db_session, email="x@acme.fr") is False
    await add_suppression(db_session, reason="opt_out", email="X@Acme.fr")
    await add_suppression(db_session, reason="manual", domain="Blocked.com")
    # match insensible a la casse (stocke en lower)
    assert await is_suppressed(db_session, email="x@acme.fr") is True
    assert await is_suppressed(db_session, domain="blocked.com") is True
    assert await is_suppressed(db_session, email="autre@acme.fr") is False


async def test_suppression_no_criteria_returns_false(db_session: AsyncSession):
    assert await is_suppressed(db_session) is False


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
