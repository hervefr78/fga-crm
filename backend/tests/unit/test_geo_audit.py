"""Tests unitaires de l'audit-visibilite GEO (agregation + run_audit_job)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace as NS

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import GeoAuditJob, GeoBrand, GeoPrompt, GeoRun
from app.services.geo import audit as audit_mod
from app.services.geo.audit import (
    _aggregate,
    _build_summary,
    _norm,
    compute_request_hash,
    run_audit_job,
)


def _run(pid, mentioned=False, position=None, reco=False, sentiment=None, found=None):
    return NS(
        brand_mentioned=mentioned, brand_position=position, brand_recommended=reco,
        brand_sentiment=sentiment, prompt_id=pid, brands_found=found or [],
    )


def test_aggregate_invisible_and_competitors():
    p1, p2, p3 = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    runs = [
        _run(p1, found=[{"nom": "HubSpot"}, {"nom": "Asana"}]),
        _run(p2, found=[{"nom": "HubSpot"}, {"nom": "monday.com"}]),
        _run(p3, found=[{"nom": "Notion"}]),
    ]
    res = _aggregate(
        runs, audited_names={_norm("Acme Corp"), _norm("Acme")},
        prompt_text_by_id={p1: "q1", p2: "q2", p3: "q3"}, n_expected=3,
    )
    assert res["visible"] is False
    assert res["visibility_rate"] == 0.0
    assert res["mentions"] == 0
    # HubSpot cite 2x -> en tete ; Acme (auditee) exclue
    assert res["competitors_found"][0] == {"name": "HubSpot", "mentions": 2}
    assert all(c["name"] not in ("Acme", "Acme Corp") for c in res["competitors_found"])
    assert len(res["per_prompt"]) == 3


def test_aggregate_visible_position_sentiment():
    p1, p2 = uuid.uuid4(), uuid.uuid4()
    runs = [
        _run(p1, mentioned=True, position=1, reco=True, sentiment="positif",
             found=[{"nom": "Acme"}, {"nom": "HubSpot"}]),
        _run(p2, found=[{"nom": "HubSpot"}]),
    ]
    res = _aggregate(
        runs, audited_names={_norm("Acme")},
        prompt_text_by_id={p1: "q1", p2: "q2"}, n_expected=2,
    )
    assert res["visible"] is True
    assert res["mentions"] == 1 and res["visibility_rate"] == 50.0
    assert res["best_position"] == 1
    assert res["recommended"] is True
    assert res["sentiment"] == "positif"


def test_request_hash_order_insensitive():
    h1 = compute_request_hash(domain="a.com", engine="perplexity", prompts=["a", "b"], country="FR", language="fr")
    h2 = compute_request_hash(domain="a.com", engine="perplexity", prompts=["b", "a"], country="FR", language="fr")
    assert h1 == h2


def test_build_summary_invisible():
    res = {"mentions": 0, "runs_completed": 3, "visible": False, "best_position": None,
           "visibility_rate": 0.0, "competitors_found": [{"name": "HubSpot", "mentions": 2}]}
    s = _build_summary("Acme", res)
    assert "0/3" in s and "Acme" in s and "HubSpot" in s


async def test_run_audit_job_creates_ephemeral_brand_and_completes(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    # Mock du run : insere des GeoRun synthetiques (pas de reseau).
    async def _fake_batch(db, *, brand_id, engine, prompt_ids, n_runs, country, language):
        for i, pid in enumerate(prompt_ids):
            db.add(GeoRun(
                prompt_id=pid, brand_id=brand_id, run_index=1, engine=engine,
                brand_mentioned=(i == 0), brand_position=(1 if i == 0 else None),
                brand_recommended=(i == 0), brand_sentiment=("positif" if i == 0 else None),
                citations=[], brands_found=[{"nom": "Acme"}] if i == 0 else [{"nom": "HubSpot"}],
            ))
        await db.commit()
        return {"total": len(prompt_ids), "success": len(prompt_ids), "failed": 0}

    monkeypatch.setattr(audit_mod, "execute_geo_batch", _fake_batch)

    job = GeoAuditJob(
        domain="acme.com", company_name="Acme", request_hash="h1", engine="perplexity",
        status="queued",
        params_json={"prompts": ["q1", "q2"], "aliases": ["Acme Corp"], "country": "FR", "language": "fr"},
    )
    db_session.add(job)
    await db_session.commit()

    await run_audit_job(db_session, job)

    refreshed = await db_session.get(GeoAuditJob, job.id)
    assert refreshed.status == "completed"
    assert refreshed.result_json["visible"] is True
    assert refreshed.result_json["mentions"] == 1
    assert refreshed.result_json["summary"]

    # Marque ephemere = is_owned False (invisible du dashboard)
    brand = await db_session.get(GeoBrand, refreshed.brand_id)
    assert brand is not None and brand.is_owned is False
    # 2 prompts crees
    n_prompts = (
        await db_session.execute(
            select(func.count()).select_from(GeoPrompt).where(GeoPrompt.brand_id == brand.id)
        )
    ).scalar()
    assert n_prompts == 2


async def test_run_audit_job_idempotent_on_completed(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    called = {"n": 0}

    async def _fake_batch(db, **kwargs):
        called["n"] += 1
        return {"total": 0, "success": 0, "failed": 0}

    monkeypatch.setattr(audit_mod, "execute_geo_batch", _fake_batch)
    job = GeoAuditJob(domain="x.com", company_name="X", request_hash="h2",
                      engine="perplexity", status="completed", params_json={})
    db_session.add(job)
    await db_session.commit()
    await run_audit_job(db_session, job)  # etat terminal -> no-op
    assert called["n"] == 0
