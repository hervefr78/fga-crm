# =============================================================================
# FGA CRM - Tests API AI Next-Action (mock simple, pas de LLM)
# =============================================================================

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_company(client: AsyncClient, headers: dict, **kwargs) -> dict:
    payload = {"name": "Acme Test", **kwargs}
    resp = await client.post("/api/v1/companies", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_contact(client: AsyncClient, headers: dict, **kwargs) -> dict:
    payload = {"first_name": "Jean", "last_name": "Test", **kwargs}
    resp = await client.post("/api/v1/contacts", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _create_deal(client: AsyncClient, headers: dict, **kwargs) -> dict:
    payload = {"title": "Deal Test", **kwargs}
    resp = await client.post("/api/v1/deals", json=payload, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Company next-action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_company_next_action_no_audit(
    client: AsyncClient, auth_headers: dict
):
    """Company sans aucune activite audit => suggestion 'Lancer un audit'."""
    company = await _create_company(client, auth_headers, name="No Audit Co")

    resp = await client.get(
        f"/api/v1/companies/{company['id']}/next-action", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "audit" in body["title"].lower()
    assert body["primary_action"]["type"] == "view"


@pytest.mark.asyncio
async def test_company_next_action_404(client: AsyncClient, auth_headers: dict):
    """Company inexistante => 404."""
    fake_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/companies/{fake_id}/next-action", headers=auth_headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Contact next-action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_contact_next_action_no_email(
    client: AsyncClient, auth_headers: dict
):
    """Contact sans email => suggestion 'Trouver email' (priorite absolue)."""
    contact = await _create_contact(client, auth_headers, first_name="No", last_name="Email")

    resp = await client.get(
        f"/api/v1/contacts/{contact['id']}/next-action", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "email" in body["title"].lower()


@pytest.mark.asyncio
async def test_contact_next_action_decision_maker_new(
    client: AsyncClient, auth_headers: dict
):
    """Decideur identifie + statut new + email => suggestion 'prospection ciblee'."""
    contact = await _create_contact(
        client,
        auth_headers,
        first_name="Marie",
        last_name="Boss",
        email="marie@test.fr",
        is_decision_maker=True,
        status="new",
    )

    resp = await client.get(
        f"/api/v1/contacts/{contact['id']}/next-action", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["primary_action"]["type"] == "compose_email"


@pytest.mark.asyncio
async def test_contact_next_action_default_followup(
    client: AsyncClient, auth_headers: dict
):
    """Contact avec email + statut != new + non decideur => suggestion 'planifier suivi'."""
    contact = await _create_contact(
        client,
        auth_headers,
        first_name="Standard",
        last_name="User",
        email="std@test.fr",
        status="contacted",
        is_decision_maker=False,
    )

    resp = await client.get(
        f"/api/v1/contacts/{contact['id']}/next-action", headers=auth_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "suivi" in body["title"].lower() or body["primary_action"]["type"] == "create_task"


@pytest.mark.asyncio
async def test_contact_next_action_stale(
    client: AsyncClient, auth_headers: dict, db_session
):
    """Contact avec last_contacted_at > 30 jours => suggestion 'relancer'."""
    from app.models.contact import Contact

    contact_obj = Contact(
        id=uuid.uuid4(),
        first_name="Stale",
        last_name="Lead",
        email="stale@test.fr",
        status="contacted",
        last_contacted_at=datetime.now(UTC) - timedelta(days=45),
    )
    db_session.add(contact_obj)
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/contacts/{contact_obj.id}/next-action", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "relancer" in body["title"].lower()
    assert body["primary_action"]["type"] == "compose_email"


# ---------------------------------------------------------------------------
# Deal next-action
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deal_next_action_lost(client: AsyncClient, auth_headers: dict):
    """stage='lost' => 204 No Content (frontend masque l'AI card)."""
    deal = await _create_deal(client, auth_headers, title="Lost", stage="lost")
    resp = await client.get(
        f"/api/v1/deals/{deal['id']}/next-action", headers=auth_headers
    )
    assert resp.status_code == 204
    assert resp.text == ""


@pytest.mark.asyncio
async def test_deal_next_action_won(client: AsyncClient, auth_headers: dict):
    """stage='won' => suggestion onboarding."""
    deal = await _create_deal(client, auth_headers, title="Won", stage="won")
    resp = await client.get(
        f"/api/v1/deals/{deal['id']}/next-action", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "onboarding" in body["title"].lower()
    assert body["primary_action"]["type"] == "create_task"


@pytest.mark.asyncio
async def test_deal_next_action_pipeline_meeting(
    client: AsyncClient, auth_headers: dict
):
    """stage='meeting' => suggestion 'envoyer la proposition'."""
    deal = await _create_deal(client, auth_headers, title="Meeting", stage="meeting")
    resp = await client.get(
        f"/api/v1/deals/{deal['id']}/next-action", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "proposition" in body["title"].lower()


@pytest.mark.asyncio
async def test_deal_next_action_close_urgency(
    client: AsyncClient, auth_headers: dict
):
    """stage=proposal + expected_close_date dans 3 jours => 'relance urgente'."""
    soon = (date.today() + timedelta(days=3)).isoformat()
    deal = await _create_deal(
        client,
        auth_headers,
        title="Urgent",
        stage="proposal",
        expected_close_date=soon,
    )
    resp = await client.get(
        f"/api/v1/deals/{deal['id']}/next-action", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "urgente" in body["title"].lower()


@pytest.mark.asyncio
async def test_deal_next_action_404(client: AsyncClient, auth_headers: dict):
    """Deal inexistant => 404."""
    fake_id = uuid.uuid4()
    resp = await client.get(
        f"/api/v1/deals/{fake_id}/next-action", headers=auth_headers
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# RBAC : un sales ne doit pas voir le next-action d'un deal d'un autre sales
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deal_next_action_rbac_forbidden(
    client: AsyncClient,
    sales_headers: dict,
    sales_b_headers: dict,
):
    """Sales A cree un deal => Sales B recoit 403 sur le next-action (cf check_entity_access)."""
    deal = await _create_deal(client, sales_headers, title="Private", stage="new")
    resp = await client.get(
        f"/api/v1/deals/{deal['id']}/next-action", headers=sales_b_headers
    )
    # Pattern projet : check_entity_access leve 403 (pas 404). On respecte le pattern.
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_company_next_action_rbac_forbidden(
    client: AsyncClient,
    sales_headers: dict,
    sales_b_headers: dict,
):
    """Sales A cree une company => Sales B recoit 403 sur le next-action."""
    company = await _create_company(client, sales_headers, name="Sales A Co")
    resp = await client.get(
        f"/api/v1/companies/{company['id']}/next-action", headers=sales_b_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_contact_next_action_rbac_forbidden(
    client: AsyncClient,
    sales_headers: dict,
    sales_b_headers: dict,
):
    """Sales A cree un contact => Sales B recoit 403 sur le next-action."""
    contact = await _create_contact(client, sales_headers, first_name="Priv", last_name="Ate")
    resp = await client.get(
        f"/api/v1/contacts/{contact['id']}/next-action", headers=sales_b_headers
    )
    assert resp.status_code == 403
