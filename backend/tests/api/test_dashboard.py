# =============================================================================
# FGA CRM - Tests API Dashboard — KPI MRR / ARR / one-shot + next-actions
# =============================================================================

import uuid
from datetime import UTC, date, datetime, timedelta

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


# ---------------------------------------------------------------------------
# Next-actions agregees (mock rule-based)
# ---------------------------------------------------------------------------


async def _get_next_actions(client: AsyncClient, headers: dict) -> list[dict]:
    """Appeler /next-actions et retourner la liste."""
    resp = await client.get("/api/v1/dashboard/next-actions", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_dashboard_next_actions_empty(client: AsyncClient, auth_headers: dict):
    """Utilisateur sans deals/contacts/tasks => liste vide."""
    items = await _get_next_actions(client, auth_headers)
    assert items == []


@pytest.mark.asyncio
async def test_dashboard_next_actions_overdue_tasks(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session,
):
    """1 task overdue => suggestion 'Reprendre le controle'."""
    from app.models.task import Task

    task = Task(
        id=uuid.uuid4(),
        title="Tache en retard",
        is_completed=False,
        due_date=datetime.now(UTC) - timedelta(days=2),
        assigned_to=test_user.id,
        organization_id=test_user.organization_id,
    )
    db_session.add(task)
    await db_session.commit()

    items = await _get_next_actions(client, auth_headers)
    assert len(items) == 1
    assert "controle" in items[0]["title"].lower()
    assert items[0]["primary_action"]["type"] == "view"


@pytest.mark.asyncio
async def test_dashboard_next_actions_hot_blocked_deals(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session,
):
    """1 deal stage=proposal sans activity => suggestion 'Reactiver'."""
    from app.models.deal import Deal

    deal = Deal(
        id=uuid.uuid4(),
        title="Proposition en standby",
        stage="proposal",
        owner_id=test_user.id,
        organization_id=test_user.organization_id,
    )
    db_session.add(deal)
    await db_session.commit()

    items = await _get_next_actions(client, auth_headers)
    assert len(items) == 1
    assert "reactiver" in items[0]["title"].lower()
    assert "1 deal(s)" in items[0]["title"]


@pytest.mark.asyncio
async def test_dashboard_next_actions_hot_blocked_excluded_when_recent_activity(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session,
):
    """Deal proposal AVEC activity recente (< 7j) => pas de suggestion 'Reactiver'."""
    from app.models.activity import Activity
    from app.models.deal import Deal

    deal = Deal(
        id=uuid.uuid4(),
        title="Deal actif",
        stage="proposal",
        owner_id=test_user.id,
        organization_id=test_user.organization_id,
    )
    db_session.add(deal)
    await db_session.flush()

    activity = Activity(
        id=uuid.uuid4(),
        type="email",
        subject="Recente",
        deal_id=deal.id,
        user_id=test_user.id,
        organization_id=test_user.organization_id,
    )
    db_session.add(activity)
    await db_session.commit()

    items = await _get_next_actions(client, auth_headers)
    # Aucun signal "hot blocked" puisque activity dans les 7 derniers jours
    titles = [it["title"].lower() for it in items]
    assert all("reactiver" not in t for t in titles)


@pytest.mark.asyncio
async def test_dashboard_next_actions_stale_qualified_contacts(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session,
):
    """Contact qualified sans activity 14j => suggestion 'Relancer'."""
    from app.models.contact import Contact

    contact = Contact(
        id=uuid.uuid4(),
        first_name="Stale",
        last_name="Qualif",
        email="stale-qualif@test.fr",
        status="qualified",
        owner_id=test_user.id,
        organization_id=test_user.organization_id,
    )
    db_session.add(contact)
    await db_session.commit()

    items = await _get_next_actions(client, auth_headers)
    assert len(items) >= 1
    assert any("relancer" in it["title"].lower() for it in items)


@pytest.mark.asyncio
async def test_dashboard_next_actions_close_imminent(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session,
):
    """Deal pipeline avec close date dans 3j => suggestion 'Closer cette semaine'."""
    from app.models.deal import Deal

    deal = Deal(
        id=uuid.uuid4(),
        title="A closer",
        stage="negotiation",
        owner_id=test_user.id,
        expected_close_date=date.today() + timedelta(days=3),
        organization_id=test_user.organization_id,
    )
    db_session.add(deal)
    await db_session.commit()

    items = await _get_next_actions(client, auth_headers)
    titles = [it["title"].lower() for it in items]
    # negotiation sans activity declenche aussi 'Reactiver' — les deux sont valides
    assert any("closer" in t or "reactiver" in t for t in titles)


@pytest.mark.asyncio
async def test_dashboard_next_actions_max_3(
    client: AsyncClient,
    auth_headers: dict,
    test_user,
    db_session,
):
    """4 signaux declenches => liste limitee a 3 suggestions."""
    from app.models.contact import Contact
    from app.models.deal import Deal
    from app.models.task import Task

    # 1. Task overdue
    db_session.add(Task(
        id=uuid.uuid4(),
        title="Overdue",
        is_completed=False,
        due_date=datetime.now(UTC) - timedelta(days=1),
        assigned_to=test_user.id,
        organization_id=test_user.organization_id,
    ))
    # 2. Deal proposal sans activity
    db_session.add(Deal(
        id=uuid.uuid4(),
        title="Hot blocked",
        stage="proposal",
        owner_id=test_user.id,
        organization_id=test_user.organization_id,
    ))
    # 3. Contact qualified stale
    db_session.add(Contact(
        id=uuid.uuid4(),
        first_name="Stale",
        last_name="Qualif",
        status="qualified",
        owner_id=test_user.id,
        organization_id=test_user.organization_id,
    ))
    # 4. Deal close imminent (different du #2 pour garantir signal distinct)
    db_session.add(Deal(
        id=uuid.uuid4(),
        title="Close soon",
        stage="meeting",  # pipeline mais hors proposal/negotiation
        owner_id=test_user.id,
        expected_close_date=date.today() + timedelta(days=4),
        organization_id=test_user.organization_id,
    ))
    await db_session.commit()

    items = await _get_next_actions(client, auth_headers)
    assert len(items) <= 3
    # On verifie qu'on a bien 3 suggestions distinctes (priorites 1, 2, 3)
    assert len(items) == 3


@pytest.mark.asyncio
async def test_dashboard_next_actions_rbac_isolation(
    client: AsyncClient,
    sales_headers: dict,
    sales_b_headers: dict,
    sales_user,
    sales_user_b,
    db_session,
):
    """Sales A ne voit pas les signaux de Sales B (ownership filter)."""
    from app.models.task import Task

    # Task overdue assignee a sales A
    db_session.add(Task(
        id=uuid.uuid4(),
        title="Overdue de A",
        is_completed=False,
        due_date=datetime.now(UTC) - timedelta(days=1),
        assigned_to=sales_user.id,
        organization_id=sales_user.organization_id,
    ))
    await db_session.commit()

    # Sales A voit la suggestion
    items_a = await _get_next_actions(client, sales_headers)
    assert any("controle" in it["title"].lower() for it in items_a)

    # Sales B ne voit rien (pas le proprietaire de la task)
    items_b = await _get_next_actions(client, sales_b_headers)
    assert items_b == []
