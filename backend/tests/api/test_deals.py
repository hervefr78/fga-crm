# =============================================================================
# FGA CRM - Tests API Deals CRUD + pricing recurrent
# =============================================================================

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_deal(client: AsyncClient, headers: dict, **kwargs) -> dict:
    """Creer un deal et retourner le JSON de reponse."""
    payload = {"title": "Deal Test", **kwargs}
    resp = await client.post("/api/v1/deals", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Creation — pricing one_shot (defaut)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_deal_one_shot(client: AsyncClient, auth_headers: dict):
    """POST sans pricing_type → pricing_type='one_shot', recurring_amount=null.

    Verifie aussi la presence des champs actual_close_date et position dans la
    reponse (exposition complete du modele — DC17).
    """
    data = await _create_deal(client, auth_headers, title="Deal one_shot")
    assert data["pricing_type"] == "one_shot"
    assert data["recurring_amount"] is None
    assert data["commitment_months"] is None
    # Champs additionnels exposes (defauts du modele)
    assert data["actual_close_date"] is None
    assert data["position"] == 0


@pytest.mark.asyncio
async def test_create_deal_one_shot_with_amount(client: AsyncClient, auth_headers: dict):
    """Deal one_shot avec amount classique → amount stocke, recurring_amount nul."""
    data = await _create_deal(
        client, auth_headers,
        title="Projet ponctuel",
        pricing_type="one_shot",
        amount=15000,
    )
    assert data["pricing_type"] == "one_shot"
    assert data["amount"] == 15000.0
    assert data["recurring_amount"] is None


# ---------------------------------------------------------------------------
# Creation — pricing recurrent (monthly)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_deal_monthly(client: AsyncClient, auth_headers: dict):
    """POST pricing_type=monthly, recurring_amount=500, commitment_months=12 → 201 avec tous les champs."""
    data = await _create_deal(
        client, auth_headers,
        title="Abonnement mensuel",
        pricing_type="monthly",
        recurring_amount=500,
        commitment_months=12,
    )
    assert data["pricing_type"] == "monthly"
    assert data["recurring_amount"] == 500.0
    assert data["commitment_months"] == 12


@pytest.mark.asyncio
async def test_create_deal_quarterly(client: AsyncClient, auth_headers: dict):
    """Deal trimestriel correctement persiste."""
    data = await _create_deal(
        client, auth_headers,
        pricing_type="quarterly",
        recurring_amount=1500,
        commitment_months=12,
    )
    assert data["pricing_type"] == "quarterly"
    assert data["recurring_amount"] == 1500.0


@pytest.mark.asyncio
async def test_create_deal_annual(client: AsyncClient, auth_headers: dict):
    """Deal annuel correctement persiste."""
    data = await _create_deal(
        client, auth_headers,
        pricing_type="annual",
        recurring_amount=12000,
        commitment_months=24,
    )
    assert data["pricing_type"] == "annual"
    assert data["recurring_amount"] == 12000.0
    assert data["commitment_months"] == 24


# ---------------------------------------------------------------------------
# Creation — validation pricing_type invalide
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_deal_invalid_pricing_type(client: AsyncClient, auth_headers: dict):
    """POST avec pricing_type='weekly' → 422 (non autorise)."""
    resp = await client.post("/api/v1/deals", json={
        "title": "Deal invalide",
        "pricing_type": "weekly",
    }, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_deal_recurring_amount_negative(client: AsyncClient, auth_headers: dict):
    """recurring_amount negatif → 422."""
    resp = await client.post("/api/v1/deals", json={
        "title": "Deal negatif",
        "pricing_type": "monthly",
        "recurring_amount": -100,
    }, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_deal_commitment_months_zero(client: AsyncClient, auth_headers: dict):
    """commitment_months=0 → 422 (ge=1)."""
    resp = await client.post("/api/v1/deals", json={
        "title": "Deal zero mois",
        "pricing_type": "monthly",
        "commitment_months": 0,
    }, headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_deal_commitment_months_too_high(client: AsyncClient, auth_headers: dict):
    """commitment_months=200 → 422 (le=120)."""
    resp = await client.post("/api/v1/deals", json={
        "title": "Deal trop long",
        "pricing_type": "monthly",
        "commitment_months": 200,
    }, headers=auth_headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Mise a jour — transitions pricing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_deal_pricing_to_recurring(client: AsyncClient, auth_headers: dict):
    """Creer one_shot puis PUT pricing_type=annual + recurring_amount=6000 → ok."""
    created = await _create_deal(
        client, auth_headers,
        title="One shot a migrer",
        pricing_type="one_shot",
        amount=6000,
    )
    deal_id = created["id"]

    resp = await client.put(f"/api/v1/deals/{deal_id}", json={
        "pricing_type": "annual",
        "recurring_amount": 6000,
        "commitment_months": 12,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pricing_type"] == "annual"
    assert data["recurring_amount"] == 6000.0
    assert data["commitment_months"] == 12


@pytest.mark.asyncio
async def test_update_deal_pricing_to_one_shot(client: AsyncClient, auth_headers: dict):
    """Creer monthly puis PUT pricing_type=one_shot + recurring_amount=null → null persiste."""
    created = await _create_deal(
        client, auth_headers,
        title="Abonnement converti",
        pricing_type="monthly",
        recurring_amount=500,
        commitment_months=12,
    )
    deal_id = created["id"]

    resp = await client.put(f"/api/v1/deals/{deal_id}", json={
        "pricing_type": "one_shot",
        "recurring_amount": None,
        "commitment_months": None,
        "amount": 5000,
    }, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["pricing_type"] == "one_shot"
    assert data["recurring_amount"] is None


@pytest.mark.asyncio
async def test_update_deal_invalid_pricing_type(client: AsyncClient, auth_headers: dict):
    """PUT avec pricing_type invalide → 422."""
    created = await _create_deal(client, auth_headers, title="Deal a invalider")
    deal_id = created["id"]

    resp = await client.put(f"/api/v1/deals/{deal_id}", json={
        "pricing_type": "weekly",
    }, headers=auth_headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Validation cross-field : recurring_amount obligatoire si pricing recurrent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_deal_recurrent_without_recurring_amount(
    client: AsyncClient, auth_headers: dict
):
    """POST pricing_type=monthly sans recurring_amount → 422 avec message clair.

    Sans cette validation, le deal serait silencieusement ignore au calcul MRR.
    """
    resp = await client.post("/api/v1/deals", json={
        "title": "Abonnement sans montant",
        "pricing_type": "monthly",
    }, headers=auth_headers)
    assert resp.status_code == 422
    body = resp.json()
    # Le message doit mentionner recurring_amount pour faciliter le debug cote client
    assert "recurring_amount" in str(body).lower()


@pytest.mark.asyncio
async def test_update_deal_to_recurrent_without_recurring_amount(
    client: AsyncClient, auth_headers: dict
):
    """Creer one_shot puis PUT pricing_type=monthly sans recurring_amount → 422."""
    created = await _create_deal(
        client, auth_headers,
        title="Deal a migrer",
        pricing_type="one_shot",
        amount=5000,
    )
    deal_id = created["id"]

    resp = await client.put(f"/api/v1/deals/{deal_id}", json={
        "pricing_type": "monthly",
    }, headers=auth_headers)
    assert resp.status_code == 422
    assert "recurring_amount" in str(resp.json()).lower()


@pytest.mark.asyncio
async def test_update_deal_set_recurring_to_null_on_recurrent(
    client: AsyncClient, auth_headers: dict
):
    """Creer monthly avec recurring_amount=500, PUT recurring_amount=null sans
    changer pricing_type → 422 (le deal resterait recurrent sans montant)."""
    created = await _create_deal(
        client, auth_headers,
        title="Abonnement existant",
        pricing_type="monthly",
        recurring_amount=500,
        commitment_months=12,
    )
    deal_id = created["id"]

    resp = await client.put(f"/api/v1/deals/{deal_id}", json={
        "recurring_amount": None,
    }, headers=auth_headers)
    assert resp.status_code == 422
    assert "recurring_amount" in str(resp.json()).lower()


# ---------------------------------------------------------------------------
# Unauthenticated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deals_unauthenticated(client: AsyncClient):
    """Acces sans token → 403."""
    resp = await client.get("/api/v1/deals")
    assert resp.status_code == 403
