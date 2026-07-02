"""Tests C2 (bug hunt) : fiabilite du webhook bulk — fresh en mode bulk (#5),
isolation d'un item defaillant par savepoint (#1), parse robuste (#11)."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrichment import EnrichmentBulk, EnrichmentBulkItem, EnrichmentJob
from app.services.enrichment import bulk_callback, freshness
from app.services.enrichment.adapters.icypeas import parse_bulk_callback


async def _seed(db: AsyncSession, org_id, file_id: str, exts: list[str]) -> EnrichmentBulk:
    job = EnrichmentJob(mode="batch", status="awaiting_results", target_json={}, organization_id=org_id)
    db.add(job)
    await db.flush()
    bulk = EnrichmentBulk(
        file=file_id, task="email-search", status="awaiting_results", total=len(exts),
        organization_id=org_id, job_id=job.id,
    )
    db.add(bulk)
    await db.flush()
    for ext in exts:
        db.add(EnrichmentBulkItem(
            bulk_id=bulk.id, external_id=ext, organization_id=org_id, status="pending",
            context_json={"company": {"siren": "123", "name": "FGA", "domain": "acme.fr"},
                          "person": {"first_name": "A", "last_name": "B"}},
        ))
    await db.commit()
    return bulk


def _found(ext: str, email: str) -> dict:
    return {"results": {"firstname": "A", "lastname": "B",
                        "emails": [{"email": email, "certainty": "ultra_sure"}]},
            "status": "DEBITED", "userData": {"externalId": ext}}


@pytest.mark.asyncio
async def test_parse_bulk_callback_skips_non_dict():
    # #11 : un element non-dict ne doit pas crasher (AttributeError -> 500)
    data = {"file": "X", "results": ["oops", 42, None, _found("ext-1", "a@acme.fr")]}
    parsed = parse_bulk_callback(data)
    assert len(parsed) == 1
    assert parsed[0]["external_id"] == "ext-1"


@pytest.mark.asyncio
async def test_bulk_callback_marks_person_fresh(db_session: AsyncSession, test_org, monkeypatch):
    # #5 : le mode bulk doit marquer la personne fraiche (sinon re-run re-facture tout)
    touched: list[str] = []

    async def fake_touch(key, ttl, *, client=None):
        touched.append(key)

    monkeypatch.setattr(freshness, "touch", fake_touch)
    await _seed(db_session, test_org.id, "F1", ["ext-1"])

    res = await bulk_callback.process_bulk_callback(db_session, {"file": "F1", "results": [_found("ext-1", "a@acme.fr")]})
    assert res["found"] == 1
    # person_key = person:{org}:{siren}:{first}.{last} en minuscules
    assert any("123" in k and "a.b" in k for k in touched)


@pytest.mark.asyncio
async def test_bulk_callback_isolates_failing_item(db_session: AsyncSession, test_org, monkeypatch):
    # #1 : un item qui plante est marque 'error' et n'annule pas les autres (pas de 500)
    async def flaky(db, bulk, item, res):
        if item.external_id == "ext-1":
            raise ValueError("boom")
        item.status = "found"

    monkeypatch.setattr(bulk_callback, "_resolve_item", flaky)
    await _seed(db_session, test_org.id, "F2", ["ext-1", "ext-2"])

    data = {"file": "F2", "results": [_found("ext-1", "a@acme.fr"), _found("ext-2", "c@acme.fr")]}
    res = await bulk_callback.process_bulk_callback(db_session, data)  # ne doit PAS lever

    items = (
        await db_session.execute(
            select(EnrichmentBulkItem).where(EnrichmentBulkItem.external_id.in_(["ext-1", "ext-2"]))
        )
    ).scalars().all()
    by_ext = {i.external_id: i.status for i in items}
    assert by_ext["ext-1"] == "error"
    assert by_ext["ext-2"] == "found"
    assert res["done"] == 2  # les deux resolus (found + error), bulk complet
