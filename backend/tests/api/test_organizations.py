# =============================================================================
# FGA CRM - Tests gestion multi-tenant (creation de membre + organisation)
# =============================================================================

import pytest
from httpx import AsyncClient

_MEMBER = {"email": "member@fga.fr", "full_name": "New Member", "password": "Secret123!", "role": "sales"}


@pytest.mark.asyncio
async def test_admin_creates_member_in_own_org(
    client: AsyncClient, auth_headers: dict, test_org
):
    """Un admin cree un membre : rattache a SON org, visible dans sa liste."""
    r = await client.post("/api/v1/users", headers=auth_headers, json=_MEMBER)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["organization_id"] == str(test_org.id)
    assert body["role"] == "sales"

    r = await client.get("/api/v1/users", headers=auth_headers)
    assert "member@fga.fr" in [u["email"] for u in r.json()["items"]]


@pytest.mark.asyncio
async def test_create_member_duplicate_email_rejected(client: AsyncClient, auth_headers: dict):
    assert (await client.post("/api/v1/users", headers=auth_headers, json=_MEMBER)).status_code == 201
    r = await client.post("/api/v1/users", headers=auth_headers, json=_MEMBER)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_create_member_forbidden_for_sales(client: AsyncClient, sales_headers: dict):
    r = await client.post("/api/v1/users", headers=sales_headers, json=_MEMBER)
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_get_my_organization(client: AsyncClient, auth_headers: dict, test_org):
    r = await client.get("/api/v1/organizations/me", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(test_org.id)
    assert body["is_active"] is True


@pytest.mark.asyncio
async def test_admin_renames_organization(client: AsyncClient, auth_headers: dict):
    r = await client.patch(
        "/api/v1/organizations/me", headers=auth_headers, json={"name": "Nouveau Nom SA"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Nouveau Nom SA"


@pytest.mark.asyncio
async def test_rename_organization_forbidden_for_sales(client: AsyncClient, sales_headers: dict):
    r = await client.patch("/api/v1/organizations/me", headers=sales_headers, json={"name": "X"})
    assert r.status_code == 403
