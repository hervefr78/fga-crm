# =============================================================================
# FGA CRM - Tests API Contacts (champs derives, joined company_name)
# =============================================================================

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_contact_response_includes_company_name(
    client: AsyncClient, auth_headers: dict, db_session, test_org
):
    """list/get contact expose company_name si rattache a une Company (DC6 selectinload)."""
    from app.models.company import Company

    company = Company(id=uuid.uuid4(), name="Acme Corp", organization_id=test_org.id)
    db_session.add(company)
    await db_session.commit()

    # Creer le contact via API (test du chemin POST → company_name populé)
    resp = await client.post(
        "/api/v1/contacts",
        json={
            "first_name": "Jean",
            "last_name": "Dupont",
            "email": "jean@acme.fr",
            "company_id": str(company.id),
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["company_id"] == str(company.id)
    assert created["company_name"] == "Acme Corp"

    # GET detail
    resp = await client.get(f"/api/v1/contacts/{created['id']}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["company_name"] == "Acme Corp"

    # GET list
    resp = await client.get("/api/v1/contacts", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["company_name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_contact_without_company_returns_null_company_name(
    client: AsyncClient, auth_headers: dict
):
    """Un contact sans company_id => company_name = None (pas de KeyError, DC2)."""
    resp = await client.post(
        "/api/v1/contacts",
        json={"first_name": "Solo", "last_name": "User"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["company_id"] is None
    assert body["company_name"] is None


@pytest.mark.asyncio
async def test_update_contact_changes_company_name(
    client: AsyncClient, auth_headers: dict, db_session, test_org
):
    """PUT company_id => company_name reflete la nouvelle company (re-fetch DC6)."""
    from app.models.company import Company

    c1 = Company(id=uuid.uuid4(), name="Old Co", organization_id=test_org.id)
    c2 = Company(id=uuid.uuid4(), name="New Co", organization_id=test_org.id)
    db_session.add_all([c1, c2])
    await db_session.commit()

    create_resp = await client.post(
        "/api/v1/contacts",
        json={
            "first_name": "Switch",
            "last_name": "User",
            "company_id": str(c1.id),
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    contact_id = create_resp.json()["id"]
    assert create_resp.json()["company_name"] == "Old Co"

    # Changer la company
    upd_resp = await client.put(
        f"/api/v1/contacts/{contact_id}",
        json={"company_id": str(c2.id)},
        headers=auth_headers,
    )
    assert upd_resp.status_code == 200, upd_resp.text
    assert upd_resp.json()["company_name"] == "New Co"
