# =============================================================================
# FGA CRM - Tests module GEO (API CRUD + RBAC + scorer + pipeline)
# =============================================================================
"""Couverture :
- CRUD brands/prompts + RBAC (sales bloque, manager lecture, admin ecriture)
- /runs/trigger : validation engine non configure / prompts inconnus
- scorer.compute_daily_metrics : formules visibility/sov/sentiment/reco
- pipeline.execute_geo_run : matching marque + guard anti-doublon (collecteur/
  extracteur mockes — aucun appel reseau)
"""

from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import GeoBrand, GeoPrompt, GeoRun
from app.schemas.geo import (
    ExtractionResult,
    GeoSentiment,
    MarqueTrouvee,
)
from app.services.geo import pipeline as geo_pipeline
from app.services.geo.collector import CollectorResult
from app.services.geo.scorer import compute_daily_metrics

# ---------------------------------------------------------------------------
# Helpers API
# ---------------------------------------------------------------------------

async def _create_brand(client: AsyncClient, headers: dict, **kwargs) -> dict:
    payload = {"slug": "fga", "name": "Fast Growth Advisor", **kwargs}
    resp = await client.post("/api/v1/geo/brands", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_prompt(
    client: AsyncClient, headers: dict, brand_id: str, **kwargs
) -> dict:
    payload = {
        "text": "Quel est le meilleur cabinet de conseil growth ?",
        "intent": "comparatif",
        **kwargs,
    }
    resp = await client.post(
        f"/api/v1/geo/brands/{brand_id}/prompts", json=payload, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# CRUD Brands
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_and_get_brand(client: AsyncClient, auth_headers: dict):
    brand = await _create_brand(client, auth_headers, aliases=["FGA", "Fast Growth"])
    assert brand["slug"] == "fga"
    assert brand["aliases"] == ["FGA", "Fast Growth"]
    assert brand["is_owned"] is False
    assert brand["active"] is True

    resp = await client.get(f"/api/v1/geo/brands/{brand['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == brand["id"]


@pytest.mark.asyncio
async def test_create_brand_duplicate_slug(client: AsyncClient, auth_headers: dict):
    await _create_brand(client, auth_headers)
    resp = await client.post(
        "/api/v1/geo/brands",
        json={"slug": "fga", "name": "Autre"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_soft_delete_brand(client: AsyncClient, auth_headers: dict):
    brand = await _create_brand(client, auth_headers)
    resp = await client.delete(
        f"/api/v1/geo/brands/{brand['id']}", headers=auth_headers
    )
    assert resp.status_code == 204
    # Soft delete : n'apparait plus dans la liste (active=False)
    listing = await client.get("/api/v1/geo/brands", headers=auth_headers)
    assert all(b["id"] != brand["id"] for b in listing.json())


@pytest.mark.asyncio
async def test_list_brands_filter_is_owned(client: AsyncClient, auth_headers: dict):
    await _create_brand(client, auth_headers, slug="owned", is_owned=True)
    await _create_brand(client, auth_headers, slug="compet", name="X", is_owned=False)
    resp = await client.get("/api/v1/geo/brands?is_owned=true", headers=auth_headers)
    assert resp.status_code == 200
    slugs = {b["slug"] for b in resp.json()}
    assert slugs == {"owned"}


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sales_blocked_on_geo(client: AsyncClient, sales_headers: dict):
    resp = await client.get("/api/v1/geo/brands", headers=sales_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_manager_can_read_not_write(
    client: AsyncClient, auth_headers: dict, manager_headers: dict
):
    brand = await _create_brand(client, auth_headers)
    # Manager : lecture OK
    read = await client.get("/api/v1/geo/brands", headers=manager_headers)
    assert read.status_code == 200
    # Manager : ecriture interdite (admin only)
    write = await client.post(
        "/api/v1/geo/brands",
        json={"slug": "x", "name": "X"},
        headers=manager_headers,
    )
    assert write.status_code == 403
    # Manager : delete interdit
    dele = await client.delete(
        f"/api/v1/geo/brands/{brand['id']}", headers=manager_headers
    )
    assert dele.status_code == 403


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_and_list_prompts(client: AsyncClient, auth_headers: dict):
    brand = await _create_brand(client, auth_headers)
    prompt = await _create_prompt(client, auth_headers, brand["id"])
    assert prompt["intent"] == "comparatif"
    assert prompt["brand_id"] == brand["id"]

    resp = await client.get(
        f"/api/v1/geo/brands/{brand['id']}/prompts", headers=auth_headers
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_update_prompt_intent(client: AsyncClient, auth_headers: dict):
    brand = await _create_brand(client, auth_headers)
    prompt = await _create_prompt(client, auth_headers, brand["id"])
    resp = await client.put(
        f"/api/v1/geo/brands/{brand['id']}/prompts/{prompt['id']}",
        json={"intent": "informationnel", "priority": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["intent"] == "informationnel"
    assert resp.json()["priority"] is True


@pytest.mark.asyncio
async def test_create_prompt_invalid_intent(client: AsyncClient, auth_headers: dict):
    brand = await _create_brand(client, auth_headers)
    resp = await client.post(
        f"/api/v1/geo/brands/{brand['id']}/prompts",
        json={"text": "Test", "intent": "n_importe_quoi"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Runs trigger — validations
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_trigger_engine_not_configured(client: AsyncClient, auth_headers: dict):
    """perplexity non configure en test (pas de cle) -> 422."""
    brand = await _create_brand(client, auth_headers)
    prompt = await _create_prompt(client, auth_headers, brand["id"])
    resp = await client.post(
        "/api/v1/geo/runs/trigger",
        json={
            "brand_id": brand["id"],
            "engine": "perplexity",
            "prompt_ids": [prompt["id"]],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "non configure" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_trigger_engine_configured_unknown_prompt(
    client: AsyncClient, auth_headers: dict, monkeypatch
):
    """Engine configure mais prompt_id inconnu -> 422 (prompts hors marque)."""
    from app.config import settings

    monkeypatch.setattr(settings, "perplexity_api_key", "test-key")
    brand = await _create_brand(client, auth_headers)
    resp = await client.post(
        "/api/v1/geo/runs/trigger",
        json={
            "brand_id": brand["id"],
            "engine": "perplexity",
            "prompt_ids": [str(uuid4())],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "inconnus" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Health (admin only)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_unconfigured(client: AsyncClient, auth_headers: dict):
    """Sans cles API, tous les moteurs sont 'unconfigured'."""
    resp = await client.get("/api/v1/geo/health", headers=auth_headers)
    assert resp.status_code == 200
    statuses = {h["engine"]: h["status"] for h in resp.json()}
    assert statuses["perplexity"] == "unconfigured"
    assert statuses["gemini"] == "unconfigured"


# ---------------------------------------------------------------------------
# Scorer — formules
# ---------------------------------------------------------------------------

async def _seed_brand(db: AsyncSession) -> GeoBrand:
    brand = GeoBrand(slug="fga", name="FGA", aliases=["Fast Growth"])
    db.add(brand)
    await db.flush()
    prompt = GeoPrompt(brand_id=brand.id, text="q", intent="comparatif")
    db.add(prompt)
    await db.flush()
    return brand, prompt


def _make_run(brand, prompt, **kwargs) -> GeoRun:
    base = {
        "prompt_id": prompt.id,
        "brand_id": brand.id,
        "engine": "perplexity",
        "run_index": 1,
        "run_at": datetime.now(UTC),
        "citations": [],
        "brands_found": [],
        "brand_mentioned": False,
    }
    base.update(kwargs)
    return GeoRun(**base)


@pytest.mark.asyncio
async def test_scorer_visibility_and_reco(db_session: AsyncSession):
    brand, prompt = await _seed_brand(db_session)
    today = datetime.now(UTC).date()

    # 3 runs : 2 mentions (1 reco), 1 non mentionne
    db_session.add(
        _make_run(
            brand, prompt, run_index=1,
            brand_mentioned=True, brand_position=1, brand_recommended=True,
            brand_sentiment="positif",
            brands_found=[{"nom": "FGA", "rang": 1}, {"nom": "Autre", "rang": 2}],
        )
    )
    db_session.add(
        _make_run(
            brand, prompt, run_index=2,
            brand_mentioned=True, brand_position=2, brand_recommended=False,
            brand_sentiment="neutre",
            brands_found=[{"nom": "Autre", "rang": 1}, {"nom": "FGA", "rang": 2}],
        )
    )
    db_session.add(
        _make_run(
            brand, prompt, run_index=3,
            brand_mentioned=False,
            brands_found=[{"nom": "Autre", "rang": 1}],
        )
    )
    await db_session.commit()

    metrics = await compute_daily_metrics(
        db_session, brand.id, today, "perplexity"
    )
    assert metrics is not None
    assert metrics.runs_total == 3
    # 2 mentions / 3 runs * 100 = 66.67
    assert float(metrics.visibility_rate) == pytest.approx(66.67, abs=0.01)
    # sov = 2 mentions / 5 brands_found * 100 = 40.0
    assert float(metrics.sov) == pytest.approx(40.0, abs=0.01)
    # reco = 1 / 2 mentions * 100 = 50.0
    assert float(metrics.reco_rate) == pytest.approx(50.0, abs=0.01)
    # sentiment_avg = (positif(1) + neutre(0)) / 2 = 0.5
    assert float(metrics.sentiment_avg) == pytest.approx(0.5, abs=0.01)


@pytest.mark.asyncio
async def test_scorer_no_runs_returns_none(db_session: AsyncSession):
    brand, _ = await _seed_brand(db_session)
    await db_session.commit()
    metrics = await compute_daily_metrics(
        db_session, brand.id, date(2020, 1, 1), "perplexity"
    )
    assert metrics is None


# ---------------------------------------------------------------------------
# Pipeline — matching + guard anti-doublon (mocks)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_run_matches_brand(db_session: AsyncSession, monkeypatch):
    brand, prompt = await _seed_brand(db_session)
    await db_session.commit()

    # Mock collecteur : retourne une reponse brute fixe
    class _FakeCollector:
        async def collect(self, prompt_text, country="FR", language="fr"):
            return CollectorResult(
                raw_answer="FGA est recommande, devant Autre.",
                citations=[{"url": "https://x.fr/a", "domain": "x.fr", "rank": 1}],
                model_version="sonar",
                engine="perplexity",
            )

    monkeypatch.setattr(
        geo_pipeline, "get_collector", lambda engine: _FakeCollector()
    )

    # Mock extracteur : FGA en rang 1, recommande, positif
    async def _fake_extract(raw_answer, *, max_chars=2000):
        return ExtractionResult(
            marques=[
                MarqueTrouvee(
                    nom="FGA", rang=1, recommandee=True,
                    sentiment=GeoSentiment.positif, justification="recommande",
                ),
                MarqueTrouvee(
                    nom="Autre", rang=2, recommandee=False,
                    sentiment=GeoSentiment.neutre, justification="cite",
                ),
            ]
        )

    monkeypatch.setattr(geo_pipeline, "extraire_marques", _fake_extract)

    result = await geo_pipeline.execute_geo_run(
        db_session, prompt.id, brand.id, "perplexity", run_index=1
    )
    assert result.success is True
    assert result.run_id is not None

    run = await db_session.get(GeoRun, result.run_id)
    assert run.brand_mentioned is True
    assert run.brand_position == 1
    assert run.brand_recommended is True
    assert run.brand_sentiment == "positif"
    assert len(run.brands_found) == 2


@pytest.mark.asyncio
async def test_pipeline_guard_anti_doublon(db_session: AsyncSession, monkeypatch):
    brand, prompt = await _seed_brand(db_session)
    await db_session.commit()

    call_count = {"n": 0}

    class _FakeCollector:
        async def collect(self, prompt_text, country="FR", language="fr"):
            call_count["n"] += 1
            return CollectorResult(raw_answer="x", model_version="m", engine="perplexity")

    async def _fake_extract(raw_answer, *, max_chars=2000):
        return ExtractionResult(marques=[])

    monkeypatch.setattr(geo_pipeline, "get_collector", lambda e: _FakeCollector())
    monkeypatch.setattr(geo_pipeline, "extraire_marques", _fake_extract)

    r1 = await geo_pipeline.execute_geo_run(
        db_session, prompt.id, brand.id, "perplexity", run_index=1
    )
    # Deuxieme appel identique le meme jour : doublon ignore, pas de re-collecte
    r2 = await geo_pipeline.execute_geo_run(
        db_session, prompt.id, brand.id, "perplexity", run_index=1
    )
    assert r1.success and r2.success
    assert r1.run_id == r2.run_id
    assert call_count["n"] == 1  # le collecteur n'a ete appele qu'une fois


@pytest.mark.asyncio
async def test_pipeline_no_match_brand_not_mentioned(
    db_session: AsyncSession, monkeypatch
):
    brand, prompt = await _seed_brand(db_session)
    await db_session.commit()

    class _FakeCollector:
        async def collect(self, prompt_text, country="FR", language="fr"):
            return CollectorResult(raw_answer="x", model_version="m", engine="perplexity")

    async def _fake_extract(raw_answer, *, max_chars=2000):
        return ExtractionResult(
            marques=[
                MarqueTrouvee(
                    nom="Concurrent", rang=1, recommandee=True,
                    sentiment=GeoSentiment.positif, justification="x",
                )
            ]
        )

    monkeypatch.setattr(geo_pipeline, "get_collector", lambda e: _FakeCollector())
    monkeypatch.setattr(geo_pipeline, "extraire_marques", _fake_extract)

    result = await geo_pipeline.execute_geo_run(
        db_session, prompt.id, brand.id, "perplexity", run_index=1
    )
    assert result.success is True
    run = await db_session.get(GeoRun, result.run_id)
    assert run.brand_mentioned is False
    assert run.brand_position is None
