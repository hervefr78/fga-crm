"""Tests de l'orchestrateur Trends (run_job : normalisation, scoring, persist)."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trends import (
    TrendCategory,
    TrendJob,
    TrendKeyword,
    TrendReport,
    TrendSnapshot,
)
from app.services.trends import cache, orchestrator


@pytest.fixture(autouse=True)
def _no_redis(monkeypatch: pytest.MonkeyPatch):
    """Neutralise le cache Redis (best-effort) pour des tests deterministes."""

    async def _get(_hash):
        return None

    async def _set(_hash, _payload, _ttl):
        return None

    monkeypatch.setattr(cache, "get_cached_report", _get)
    monkeypatch.setattr(cache, "set_cached_report", _set)


async def _make_job(db: AsyncSession, *, mode: str = "quick", seeds=None) -> TrendJob:
    import uuid as _uuid

    from app.models.organization import Organization

    org = Organization(id=_uuid.uuid4(), name="Trends Org", slug=f"trends-{_uuid.uuid4().hex[:8]}")
    db.add(org)
    cat = TrendCategory(provider="mock", slug="marketing-digital", label="Marketing Digital")
    db.add(cat)
    await db.flush()
    request_hash = cache.compute_request_hash(
        mode=mode, category_id=str(cat.id), country="FR", language="fr",
        timeframe="today 12-m", seed_terms=seeds or [],
    )
    job = TrendJob(
        mode=mode, provider_primary="mock", status="queued", request_hash=request_hash,
        organization_id=org.id,
        params_json={
            "request_hash": request_hash, "category_id": str(cat.id),
            "category_slug": cat.slug, "category_label": cat.label,
            "country": "FR", "language": "fr", "timeframe": "today 12-m",
            "seed_terms": seeds or [], "refresh": False,
        },
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def test_run_job_completes_and_persists(db_session: AsyncSession):
    job = await _make_job(db_session, seeds=["prospection"])
    await orchestrator.run_job(db_session, job)

    refreshed = await db_session.get(TrendJob, job.id)
    assert refreshed.status == "completed"
    assert refreshed.provider_effective == "mock"
    assert refreshed.steps_done == refreshed.steps_total

    report = (
        await db_session.execute(select(TrendReport).where(TrendReport.job_id == job.id))
    ).scalar_one()
    assert report.opportunity_score is not None
    assert 0 <= float(report.opportunity_score) <= 100
    assert report.summary_md
    signals = report.insights_json["signals"]
    assert set(signals) >= {"market_pulse", "timeseries", "rising_queries", "top_queries", "regions"}
    assert report.insights_json["meta"]["cached"] is False


async def test_run_job_persists_snapshot_and_keywords(db_session: AsyncSession):
    job = await _make_job(db_session, seeds=["growth"])
    await orchestrator.run_job(db_session, job)

    snaps = (
        await db_session.execute(
            select(func.count()).select_from(TrendSnapshot).where(TrendSnapshot.job_id == job.id)
        )
    ).scalar()
    assert snaps == 1
    kws = (await db_session.execute(select(func.count()).select_from(TrendKeyword))).scalar()
    assert kws > 0


async def test_quick_mode_has_no_topics(db_session: AsyncSession):
    job = await _make_job(db_session, mode="quick")
    await orchestrator.run_job(db_session, job)
    report = (
        await db_session.execute(select(TrendReport).where(TrendReport.job_id == job.id))
    ).scalar_one()
    # Les related_topics ne sont collectes qu'en mode deep.
    assert report.insights_json["signals"]["related_topics"] == []


async def test_deep_mode_has_topics(db_session: AsyncSession):
    job = await _make_job(db_session, mode="deep")
    await orchestrator.run_job(db_session, job)
    report = (
        await db_session.execute(select(TrendReport).where(TrendReport.job_id == job.id))
    ).scalar_one()
    assert len(report.insights_json["signals"]["related_topics"]) > 0


async def test_run_job_failure_sets_failed_status(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    job = await _make_job(db_session)

    async def _boom(**_kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(orchestrator, "_collect_signals", _boom)
    await orchestrator.run_job(db_session, job)  # ne doit pas lever

    refreshed = await db_session.get(TrendJob, job.id)
    assert refreshed.status == "failed"
    assert refreshed.error and "provider down" in refreshed.error


async def test_run_job_is_idempotent_on_completed(db_session: AsyncSession):
    # Un retry (Celery redelivery) sur un job deja complete doit etre un no-op :
    # ni 2e report (job_id unique -> IntegrityError), ni bascule en failed.
    job = await _make_job(db_session, seeds=["idem"])
    await orchestrator.run_job(db_session, job)
    assert (await db_session.get(TrendJob, job.id)).status == "completed"

    # 2e execution du MEME job (simule le retry).
    reloaded = await db_session.get(TrendJob, job.id)
    await orchestrator.run_job(db_session, reloaded)

    refreshed = await db_session.get(TrendJob, job.id)
    assert refreshed.status == "completed"  # pas de bascule en failed
    reports = (
        await db_session.execute(
            select(func.count()).select_from(TrendReport).where(TrendReport.job_id == job.id)
        )
    ).scalar()
    assert reports == 1  # un seul report, pas de doublon


async def test_request_hash_order_sensitive():
    # L'ordre des seeds est significatif : deux ordres -> deux hash distincts
    # (sinon dedup/cache incoherents avec le contenu produit).
    h1 = cache.compute_request_hash(
        mode="quick", category_id="c", country="FR", language="fr",
        timeframe="today 12-m", seed_terms=["a", "b"],
    )
    h2 = cache.compute_request_hash(
        mode="quick", category_id="c", country="FR", language="fr",
        timeframe="today 12-m", seed_terms=["b", "a"],
    )
    assert h1 != h2


async def test_opportunity_score_bounds():
    # Score borne 0-100 meme avec des signaux extremes.
    signals = {
        "market_pulse": {"interest_index": 100.0},
        "rising_queries": [{"growth": 999999, "breakout": True}],
        "regions": [{"value": 100}],
    }
    score = orchestrator._opportunity_score(signals)
    assert 0 <= score <= 100


async def test_opportunity_score_empty_signals():
    signals = {
        "market_pulse": {"interest_index": 0.0},
        "rising_queries": [],
        "regions": [],
    }
    assert orchestrator._opportunity_score(signals) == 0.0
