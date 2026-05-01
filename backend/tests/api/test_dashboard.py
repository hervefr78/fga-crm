# =============================================================================
# FGA CRM - Tests API Dashboard — KPI MRR / ARR / one-shot
# =============================================================================

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_won_deal(
    client: AsyncClient,
    headers: dict,
    pricing_type: str = "one_shot",
    amount: float | None = None,
    recurring_amount: float | None = None,
    commitment_months: int | None = None,
) -> str:
    """Creer un deal puis le passer en stage 'won'. Retourne l'id."""
    payload: dict = {
        "title": f"Deal won {pricing_type}",
        "pricing_type": pricing_type,
    }
    if amount is not None:
        payload["amount"] = amount
    if recurring_amount is not None:
        payload["recurring_amount"] = recurring_amount
    if commitment_months is not None:
        payload["commitment_months"] = commitment_months

    resp = await client.post("/api/v1/deals", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    deal_id = resp.json()["id"]

    resp = await client.patch(f"/api/v1/deals/{deal_id}/stage", json={"stage": "won"}, headers=headers)
    assert resp.status_code == 200, resp.text
    return deal_id


async def _create_pipeline_deal(
    client: AsyncClient,
    headers: dict,
    stage: str = "proposal",
    pricing_type: str = "monthly",
    recurring_amount: float | None = None,
) -> str:
    """Creer un deal en stage pipeline. Retourne l'id."""
    payload: dict = {
        "title": f"Pipeline {pricing_type}",
        "stage": stage,
        "pricing_type": pricing_type,
    }
    if recurring_amount is not None:
        payload["recurring_amount"] = recurring_amount

    resp = await client.post("/api/v1/deals", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _get_stats(client: AsyncClient, headers: dict) -> dict:
    """Appeler le dashboard stats et retourner le JSON."""
    resp = await client.get("/api/v1/dashboard/stats", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# MRR won — deals mensuels
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_mrr_won_monthly(client: AsyncClient, auth_headers: dict):
    """2 deals won monthly (300 + 200) → mrr_won=500, arr_won=6000, one_shot_won=0."""
    await _create_won_deal(client, auth_headers, pricing_type="monthly", recurring_amount=300)
    await _create_won_deal(client, auth_headers, pricing_type="monthly", recurring_amount=200)

    stats = await _get_stats(client, auth_headers)
    assert stats["deals_mrr_won"] == 500.0
    assert stats["deals_arr_won"] == 6000.0
    assert stats["deals_one_shot_won"] == 0.0


# ---------------------------------------------------------------------------
# MRR won — periodes mixtes (normalisation en mois)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_mrr_won_mixed_periods(client: AsyncClient, auth_headers: dict):
    """monthly(100) + quarterly(300) + annual(1200) won → mrr=100+100+100=300."""
    await _create_won_deal(client, auth_headers, pricing_type="monthly", recurring_amount=100)
    await _create_won_deal(client, auth_headers, pricing_type="quarterly", recurring_amount=300)
    await _create_won_deal(client, auth_headers, pricing_type="annual", recurring_amount=1200)

    stats = await _get_stats(client, auth_headers)
    # monthly: 100/1=100, quarterly: 300/3=100, annual: 1200/12=100 → total=300
    assert abs(stats["deals_mrr_won"] - 300.0) < 0.01
    assert abs(stats["deals_arr_won"] - 3600.0) < 0.01


@pytest.mark.asyncio
async def test_dashboard_mrr_won_biannual(client: AsyncClient, auth_headers: dict):
    """Deal biannual(600) won → mrr=100 (600/6)."""
    await _create_won_deal(client, auth_headers, pricing_type="biannual", recurring_amount=600)

    stats = await _get_stats(client, auth_headers)
    assert abs(stats["deals_mrr_won"] - 100.0) < 0.01


# ---------------------------------------------------------------------------
# MRR pipeline
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_mrr_pipeline(client: AsyncClient, auth_headers: dict):
    """2 deals pipeline recurrents (monthly 200 + monthly 300) → mrr_pipeline=500."""
    await _create_pipeline_deal(client, auth_headers, stage="proposal", pricing_type="monthly", recurring_amount=200)
    await _create_pipeline_deal(client, auth_headers, stage="negotiation", pricing_type="monthly", recurring_amount=300)

    stats = await _get_stats(client, auth_headers)
    assert stats["deals_mrr_pipeline"] == 500.0


@pytest.mark.asyncio
async def test_dashboard_mrr_pipeline_excludes_won_and_lost(client: AsyncClient, auth_headers: dict):
    """Deals won et lost ne contribuent pas au mrr_pipeline."""
    # Deal won recurrent → ne compte pas dans pipeline
    await _create_won_deal(client, auth_headers, pricing_type="monthly", recurring_amount=1000)
    # Deal perdu recurrent
    payload = {
        "title": "Deal perdu",
        "stage": "lost",
        "pricing_type": "monthly",
        "recurring_amount": 999,
    }
    resp = await client.post("/api/v1/deals", json=payload, headers=auth_headers)
    assert resp.status_code == 201

    stats = await _get_stats(client, auth_headers)
    assert stats["deals_mrr_pipeline"] == 0.0


# ---------------------------------------------------------------------------
# One-shot won
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_one_shot_won(client: AsyncClient, auth_headers: dict):
    """1 deal won one_shot amount=10000 → one_shot_won=10000, mrr_won=0."""
    await _create_won_deal(client, auth_headers, pricing_type="one_shot", amount=10000)

    stats = await _get_stats(client, auth_headers)
    assert stats["deals_one_shot_won"] == 10000.0
    assert stats["deals_mrr_won"] == 0.0


@pytest.mark.asyncio
async def test_dashboard_one_shot_won_cumulative(client: AsyncClient, auth_headers: dict):
    """Somme de plusieurs deals one_shot won."""
    await _create_won_deal(client, auth_headers, pricing_type="one_shot", amount=5000)
    await _create_won_deal(client, auth_headers, pricing_type="one_shot", amount=3000)

    stats = await _get_stats(client, auth_headers)
    assert stats["deals_one_shot_won"] == 8000.0


# ---------------------------------------------------------------------------
# Edge case : recurring_amount null sur deal recurrent — bloque a la creation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_create_recurring_without_amount_blocked(
    client: AsyncClient, auth_headers: dict
):
    """POST pricing_type=monthly sans recurring_amount → 422 (validation cross-field).

    Anciennement, ce scenario etait autorise et le deal etait silencieusement
    ignore au calcul MRR. Le validator empeche desormais cette incoherence en
    amont, garantissant que tout deal recurrent contribue au MRR.
    """
    resp = await client.post("/api/v1/deals", json={
        "title": "Monthly sans montant",
        "pricing_type": "monthly",
    }, headers=auth_headers)
    assert resp.status_code == 422

    # Le MRR reste a 0 puisque aucun deal recurrent n'a ete cree
    stats = await _get_stats(client, auth_headers)
    assert stats["deals_mrr_won"] == 0.0


# ---------------------------------------------------------------------------
# Edge case : pas de deals → tous KPI a 0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_empty_kpi(client: AsyncClient, auth_headers: dict):
    """Sans aucun deal, tous les KPI pricing sont a 0."""
    stats = await _get_stats(client, auth_headers)
    assert stats["deals_mrr_won"] == 0.0
    assert stats["deals_arr_won"] == 0.0
    assert stats["deals_mrr_pipeline"] == 0.0
    assert stats["deals_one_shot_won"] == 0.0


# ---------------------------------------------------------------------------
# RBAC isolation — sales voit uniquement ses propres deals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dashboard_rbac_isolation(
    client: AsyncClient,
    auth_headers: dict,
    sales_headers: dict,
):
    """Deal won monthly cree par admin → sales voit mrr_won=0 (isolation ownership)."""
    # Admin cree un deal won mensuel
    await _create_won_deal(client, auth_headers, pricing_type="monthly", recurring_amount=500)

    # L'admin voit le MRR (il est admin, voit tout)
    admin_stats = await _get_stats(client, auth_headers)
    assert admin_stats["deals_mrr_won"] == 500.0

    # Le sales ne voit pas ce deal (owner_id differ)
    sales_stats = await _get_stats(client, sales_headers)
    assert sales_stats["deals_mrr_won"] == 0.0


@pytest.mark.asyncio
async def test_dashboard_rbac_sales_sees_own_mrr(
    client: AsyncClient,
    sales_headers: dict,
):
    """Sales cree son propre deal won mensuel → il voit son propre mrr_won."""
    await _create_won_deal(client, sales_headers, pricing_type="monthly", recurring_amount=200)

    stats = await _get_stats(client, sales_headers)
    assert stats["deals_mrr_won"] == 200.0
