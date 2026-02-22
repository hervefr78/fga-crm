# =============================================================================
# FGA CRM - Tests API Email Templates (CRUD + RBAC)
# =============================================================================

import pytest
from httpx import AsyncClient

from app.models.user import User

TEMPLATES_URL = "/api/v1/email-templates"

VALID_TEMPLATE = {
    "name": "Introduction prospect",
    "subject": "Bonjour {{first_name}}",
    "body": "Bonjour {{first_name}} {{last_name}},\n\nJe suis {{sender_name}}.",
}


# ---------- Create ----------


@pytest.mark.asyncio
async def test_create_template(client: AsyncClient, auth_headers: dict):
    resp = await client.post(TEMPLATES_URL, json=VALID_TEMPLATE, headers=auth_headers)
    assert resp.status_code == 201

    data = resp.json()
    assert data["name"] == VALID_TEMPLATE["name"]
    assert data["subject"] == VALID_TEMPLATE["subject"]
    assert data["body"] == VALID_TEMPLATE["body"]
    assert data["id"]
    assert data["owner_id"]
    assert data["created_at"]


@pytest.mark.asyncio
async def test_create_template_extracts_variables(client: AsyncClient, auth_headers: dict):
    resp = await client.post(TEMPLATES_URL, json=VALID_TEMPLATE, headers=auth_headers)
    assert resp.status_code == 201

    variables = resp.json()["variables"]
    assert "first_name" in variables
    assert "last_name" in variables
    assert "sender_name" in variables


@pytest.mark.asyncio
async def test_create_template_no_auth(client: AsyncClient):
    resp = await client.post(TEMPLATES_URL, json=VALID_TEMPLATE)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_create_template_invalid(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        TEMPLATES_URL,
        json={"subject": "Objet", "body": "Corps"},  # name manquant
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ---------- List ----------


@pytest.mark.asyncio
async def test_list_templates(client: AsyncClient, auth_headers: dict):
    # Creer 2 templates
    await client.post(TEMPLATES_URL, json=VALID_TEMPLATE, headers=auth_headers)
    await client.post(
        TEMPLATES_URL,
        json={"name": "Relance", "subject": "Relance", "body": "Message de relance"},
        headers=auth_headers,
    )

    resp = await client.get(TEMPLATES_URL, headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert "page" in data
    assert "size" in data
    assert "pages" in data


@pytest.mark.asyncio
async def test_list_templates_search(client: AsyncClient, auth_headers: dict):
    await client.post(TEMPLATES_URL, json=VALID_TEMPLATE, headers=auth_headers)
    await client.post(
        TEMPLATES_URL,
        json={"name": "Relance client", "subject": "Relance", "body": "Texte"},
        headers=auth_headers,
    )

    resp = await client.get(TEMPLATES_URL, params={"search": "Relance"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "Relance client"


# ---------- Get ----------


@pytest.mark.asyncio
async def test_get_template(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(TEMPLATES_URL, json=VALID_TEMPLATE, headers=auth_headers)
    template_id = create_resp.json()["id"]

    resp = await client.get(f"{TEMPLATES_URL}/{template_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == template_id
    assert resp.json()["name"] == VALID_TEMPLATE["name"]


@pytest.mark.asyncio
async def test_get_template_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.get(
        f"{TEMPLATES_URL}/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ---------- Update ----------


@pytest.mark.asyncio
async def test_update_template(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(TEMPLATES_URL, json=VALID_TEMPLATE, headers=auth_headers)
    template_id = create_resp.json()["id"]

    resp = await client.put(
        f"{TEMPLATES_URL}/{template_id}",
        json={"name": "Template modifie"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Template modifie"


@pytest.mark.asyncio
async def test_update_template_reextracts_variables(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(TEMPLATES_URL, json=VALID_TEMPLATE, headers=auth_headers)
    template_id = create_resp.json()["id"]

    resp = await client.put(
        f"{TEMPLATES_URL}/{template_id}",
        json={"body": "Nouveau body avec {{company_name}}"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    variables = resp.json()["variables"]
    assert "company_name" in variables
    assert "first_name" in variables  # du subject inchange


# ---------- Delete ----------


@pytest.mark.asyncio
async def test_delete_template(client: AsyncClient, auth_headers: dict):
    create_resp = await client.post(TEMPLATES_URL, json=VALID_TEMPLATE, headers=auth_headers)
    template_id = create_resp.json()["id"]

    resp = await client.delete(f"{TEMPLATES_URL}/{template_id}", headers=auth_headers)
    assert resp.status_code == 204

    # Verifier suppression
    resp = await client.get(f"{TEMPLATES_URL}/{template_id}", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_template_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.delete(
        f"{TEMPLATES_URL}/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ---------- RBAC ----------


@pytest.mark.asyncio
async def test_template_rbac_isolation(
    client: AsyncClient,
    sales_user: User,
    sales_headers: dict,
    sales_user_b: User,
    sales_b_headers: dict,
):
    """Sales A cree un template, Sales B ne le voit pas."""
    # Sales A cree
    resp = await client.post(TEMPLATES_URL, json=VALID_TEMPLATE, headers=sales_headers)
    assert resp.status_code == 201
    template_id = resp.json()["id"]

    # Sales A le voit dans la liste
    resp = await client.get(TEMPLATES_URL, headers=sales_headers)
    assert resp.json()["total"] == 1

    # Sales B ne le voit pas
    resp = await client.get(TEMPLATES_URL, headers=sales_b_headers)
    assert resp.json()["total"] == 0

    # Sales B ne peut pas le GET
    resp = await client.get(f"{TEMPLATES_URL}/{template_id}", headers=sales_b_headers)
    assert resp.status_code == 403

    # Sales B ne peut pas le modifier
    resp = await client.put(
        f"{TEMPLATES_URL}/{template_id}",
        json={"name": "Hijack"},
        headers=sales_b_headers,
    )
    assert resp.status_code == 403

    # Sales B ne peut pas le supprimer
    resp = await client.delete(f"{TEMPLATES_URL}/{template_id}", headers=sales_b_headers)
    assert resp.status_code == 403
