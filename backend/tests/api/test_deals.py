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
# List — filtres category (pipeline / signed / lost)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_deals_category_pipeline(client: AsyncClient, auth_headers: dict):
    """category=pipeline → retourne uniquement les deals dans new/contacted/.../negotiation."""
    await _create_deal(client, auth_headers, title="Pipeline new", stage="new")
    await _create_deal(client, auth_headers, title="Won deal", stage="won")
    await _create_deal(client, auth_headers, title="Lost deal", stage="lost")

    resp = await client.get("/api/v1/deals?category=pipeline", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["stage"] == "new"


@pytest.mark.asyncio
async def test_list_deals_category_signed(client: AsyncClient, auth_headers: dict):
    """category=signed → retourne uniquement les deals stage=won."""
    await _create_deal(client, auth_headers, title="Pipeline", stage="new")
    await _create_deal(client, auth_headers, title="Won deal", stage="won")
    await _create_deal(client, auth_headers, title="Lost deal", stage="lost")

    resp = await client.get("/api/v1/deals?category=signed", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["stage"] == "won"


@pytest.mark.asyncio
async def test_list_deals_category_lost(client: AsyncClient, auth_headers: dict):
    """category=lost → retourne uniquement les deals stage=lost."""
    await _create_deal(client, auth_headers, title="Pipeline", stage="new")
    await _create_deal(client, auth_headers, title="Won deal", stage="won")
    await _create_deal(client, auth_headers, title="Lost deal", stage="lost")

    resp = await client.get("/api/v1/deals?category=lost", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["stage"] == "lost"


# ---------------------------------------------------------------------------
# List — filtres close_date / pricing_type / owner_id
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_deals_filter_close_date_range(client: AsyncClient, auth_headers: dict):
    """Filtrer les deals won par range de actual_close_date."""
    # Creer 2 deals won, override actual_close_date en BDD pour controler les dates
    from datetime import date as _date

    from sqlalchemy import select as _select

    from app.models.deal import Deal as _Deal
    from tests.conftest import test_session_maker

    d1 = await _create_deal(client, auth_headers, title="Won 2025-01", stage="won")
    d2 = await _create_deal(client, auth_headers, title="Won 2025-06", stage="won")

    async with test_session_maker() as session:
        result = await session.execute(_select(_Deal))
        for deal in result.scalars().all():
            if deal.title == "Won 2025-01":
                deal.actual_close_date = _date(2025, 1, 15)
            elif deal.title == "Won 2025-06":
                deal.actual_close_date = _date(2025, 6, 15)
        await session.commit()

    # Range qui inclut uniquement le 2025-06
    resp = await client.get(
        "/api/v1/deals?close_date_from=2025-05-01&close_date_to=2025-12-31",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == d2["id"]
    # On peut tester l'edge inferieur
    resp2 = await client.get(
        "/api/v1/deals?close_date_from=2025-01-01&close_date_to=2025-03-01",
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total"] == 1
    assert data2["items"][0]["id"] == d1["id"]


@pytest.mark.asyncio
async def test_list_deals_filter_pricing_type(client: AsyncClient, auth_headers: dict):
    """Filtrer par pricing_type=monthly retourne uniquement les deals mensuels."""
    await _create_deal(
        client, auth_headers,
        title="Monthly deal",
        pricing_type="monthly",
        recurring_amount=500,
    )
    await _create_deal(
        client, auth_headers,
        title="One shot deal",
        pricing_type="one_shot",
        amount=10000,
    )

    resp = await client.get("/api/v1/deals?pricing_type=monthly", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["pricing_type"] == "monthly"


@pytest.mark.asyncio
async def test_list_deals_filter_pricing_type_invalid(
    client: AsyncClient, auth_headers: dict
):
    """pricing_type inconnu → 422 (DC1 — pas de fallback silencieux)."""
    resp = await client.get("/api/v1/deals?pricing_type=weekly", headers=auth_headers)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_list_deals_filter_owner_id(
    client: AsyncClient,
    auth_headers: dict,
    sales_headers: dict,
    sales_user,
):
    """Admin filtre par owner_id (sales) → voit les deals owned par ce sales."""
    # Sales cree son propre deal
    await _create_deal(client, sales_headers, title="Sales deal")
    # Admin cree son propre deal
    await _create_deal(client, auth_headers, title="Admin deal")

    resp = await client.get(
        f"/api/v1/deals?owner_id={sales_user.id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Sales deal"


# ---------------------------------------------------------------------------
# Auto-set actual_close_date sur changements de stage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_stage_sets_actual_close_date(
    client: AsyncClient, auth_headers: dict
):
    """PATCH stage=won sur un deal pipeline → actual_close_date = today."""
    from datetime import date as _date

    created = await _create_deal(client, auth_headers, title="A signer", stage="proposal")
    deal_id = created["id"]
    assert created["actual_close_date"] is None

    resp = await client.patch(
        f"/api/v1/deals/{deal_id}/stage", json={"stage": "won"}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["stage"] == "won"
    assert data["actual_close_date"] == _date.today().isoformat()


@pytest.mark.asyncio
async def test_update_stage_lost_sets_actual_close_date(
    client: AsyncClient, auth_headers: dict
):
    """PATCH stage=lost → actual_close_date = today."""
    from datetime import date as _date

    created = await _create_deal(client, auth_headers, title="A perdre", stage="negotiation")
    deal_id = created["id"]

    resp = await client.patch(
        f"/api/v1/deals/{deal_id}/stage", json={"stage": "lost"}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["actual_close_date"] == _date.today().isoformat()


@pytest.mark.asyncio
async def test_update_stage_back_to_pipeline_resets_close_date(
    client: AsyncClient, auth_headers: dict
):
    """won → new : actual_close_date doit etre reset a None."""
    created = await _create_deal(client, auth_headers, title="A re-ouvrir", stage="proposal")
    deal_id = created["id"]

    # 1. won → close_date set
    resp = await client.patch(
        f"/api/v1/deals/{deal_id}/stage", json={"stage": "won"}, headers=auth_headers
    )
    assert resp.json()["actual_close_date"] is not None

    # 2. won → new : close_date reset
    resp = await client.patch(
        f"/api/v1/deals/{deal_id}/stage", json={"stage": "new"}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["actual_close_date"] is None


@pytest.mark.asyncio
async def test_update_stage_idempotent_close_date(
    client: AsyncClient, auth_headers: dict
):
    """won → won (re-soumission) : actual_close_date inchange (pas d'ecrasement)."""
    from datetime import date as _date

    from sqlalchemy import select as _select

    from app.models.deal import Deal as _Deal
    from tests.conftest import test_session_maker

    created = await _create_deal(client, auth_headers, title="Stable", stage="proposal")
    deal_id = created["id"]

    # 1. proposal → won
    resp = await client.patch(
        f"/api/v1/deals/{deal_id}/stage", json={"stage": "won"}, headers=auth_headers
    )
    initial_close = resp.json()["actual_close_date"]

    # 2. Forcer une date passee en BDD pour detecter une eventuelle re-ecriture
    fixed_date = _date(2024, 1, 1)
    async with test_session_maker() as session:
        result = await session.execute(_select(_Deal).where(_Deal.id == _parse_uuid_str(deal_id)))
        deal = result.scalar_one()
        deal.actual_close_date = fixed_date
        await session.commit()

    # 3. won → won (PATCH a la meme valeur) — la close_date doit rester inchangee
    resp = await client.patch(
        f"/api/v1/deals/{deal_id}/stage", json={"stage": "won"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["actual_close_date"] == fixed_date.isoformat()
    assert resp.json()["actual_close_date"] != initial_close


# Helper local pour le test ci-dessus (eviter d'importer le helper de la route)
def _parse_uuid_str(value: str):
    import uuid as _uuid
    return _uuid.UUID(value)


# ---------------------------------------------------------------------------
# Endpoint /stats
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deals_stats_signed_mrr(client: AsyncClient, auth_headers: dict):
    """1 deal won monthly recurring=1500 → mrr=1500, arr=18000, count=1, recurring_count=1."""
    await _create_deal(
        client, auth_headers,
        title="Won monthly",
        stage="won",
        pricing_type="monthly",
        recurring_amount=1500,
        commitment_months=12,
    )

    resp = await client.get("/api/v1/deals/stats?category=signed", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] == 1
    assert data["recurring_count"] == 1
    assert data["one_shot_amount"] == 0.0
    assert abs(data["mrr"] - 1500.0) < 0.01
    assert abs(data["arr"] - 18000.0) < 0.01


@pytest.mark.asyncio
async def test_deals_stats_signed_mixed(client: AsyncClient, auth_headers: dict):
    """1 won monthly(500) + 1 won annual(6000) + 1 won one_shot(10000)
    → mrr = 500 + 6000/12 = 1000, arr = 12000, one_shot_amount = 10000."""
    await _create_deal(
        client, auth_headers,
        title="Won monthly",
        stage="won",
        pricing_type="monthly",
        recurring_amount=500,
    )
    await _create_deal(
        client, auth_headers,
        title="Won annual",
        stage="won",
        pricing_type="annual",
        recurring_amount=6000,
    )
    await _create_deal(
        client, auth_headers,
        title="Won one shot",
        stage="won",
        pricing_type="one_shot",
        amount=10000,
    )

    resp = await client.get("/api/v1/deals/stats?category=signed", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] == 3
    assert data["recurring_count"] == 2
    assert abs(data["one_shot_amount"] - 10000.0) < 0.01
    # Total amount = somme des champs `amount` (recurrents ont amount=null → ignores via or 0)
    assert abs(data["total_amount"] - 10000.0) < 0.01
    assert abs(data["mrr"] - 1000.0) < 0.01
    assert abs(data["arr"] - 12000.0) < 0.01


@pytest.mark.asyncio
async def test_deals_stats_empty(client: AsyncClient, auth_headers: dict):
    """Sans deal → tous les KPI a 0 (DC10 — pas de division par zero)."""
    resp = await client.get("/api/v1/deals/stats", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] == 0
    assert data["recurring_count"] == 0
    assert data["mrr"] == 0.0
    assert data["arr"] == 0.0
    assert data["total_amount"] == 0.0
    assert data["one_shot_amount"] == 0.0


# ---------------------------------------------------------------------------
# Champs derives (owner_name, company_name, loss_reason)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_deals_includes_owner_name(
    client: AsyncClient, auth_headers: dict, test_user
):
    """list_deals expose owner_name (full_name du user proprietaire) — DC6 selectinload."""
    await _create_deal(client, auth_headers, title="Deal avec owner")

    resp = await client.get("/api/v1/deals", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert "owner_name" in item
    assert item["owner_name"] == test_user.full_name
    assert item["owner_id"] == str(test_user.id)


@pytest.mark.asyncio
async def test_list_deals_includes_company_name(
    client: AsyncClient, auth_headers: dict, db_session, test_org
):
    """list_deals expose company_name si le deal est rattache a une company."""
    import uuid as _uuid

    from app.models.company import Company as _Company

    company = _Company(id=_uuid.uuid4(), name="Acme Corp", organization_id=test_org.id)
    db_session.add(company)
    await db_session.commit()

    await _create_deal(
        client, auth_headers,
        title="Deal Acme",
        company_id=str(company.id),
    )

    resp = await client.get("/api/v1/deals", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["company_id"] == str(company.id)
    assert item["company_name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_create_deal_with_loss_reason(
    client: AsyncClient, auth_headers: dict
):
    """POST avec loss_reason → champ persiste et expose en GET."""
    created = await _create_deal(
        client, auth_headers,
        title="Deal perdu",
        stage="lost",
        loss_reason="Trop cher",
    )
    assert created["loss_reason"] == "Trop cher"

    # Verification via GET detail
    resp = await client.get(f"/api/v1/deals/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["loss_reason"] == "Trop cher"


@pytest.mark.asyncio
async def test_get_deal_without_company_returns_null_company_name(
    client: AsyncClient, auth_headers: dict
):
    """Un deal sans company_id → company_name = None (pas de KeyError, DC2)."""
    created = await _create_deal(client, auth_headers, title="Deal solo")
    resp = await client.get(f"/api/v1/deals/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["company_id"] is None
    assert body["company_name"] is None
    # contact_name est None aussi quand pas de contact_id
    assert body["contact_id"] is None
    assert body["contact_name"] is None


@pytest.mark.asyncio
async def test_list_deals_includes_contact_name(
    client: AsyncClient, auth_headers: dict, db_session, test_org
):
    """list_deals expose contact_name si le deal est rattache a un Contact (DC6 selectinload)."""
    import uuid as _uuid

    from app.models.contact import Contact as _Contact

    contact = _Contact(
        id=_uuid.uuid4(), first_name="Marie", last_name="Curie", email="m@curie.fr",
        organization_id=test_org.id,
    )
    db_session.add(contact)
    await db_session.commit()

    await _create_deal(
        client, auth_headers,
        title="Deal Curie",
        contact_id=str(contact.id),
    )

    # GET list
    resp = await client.get("/api/v1/deals", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["contact_id"] == str(contact.id)
    assert items[0]["contact_name"] == "Marie Curie"

    # GET detail
    resp = await client.get(f"/api/v1/deals/{items[0]['id']}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["contact_name"] == "Marie Curie"


# ---------------------------------------------------------------------------
# Unauthenticated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deals_unauthenticated(client: AsyncClient):
    """Acces sans token → 403."""
    resp = await client.get("/api/v1/deals")
    assert resp.status_code == 401
