# =============================================================================
# FGA CRM - Tests RBAC (isolation ownership entre roles)
# =============================================================================

import pytest
from httpx import AsyncClient

from app.models.user import User

# ---------------------------------------------------------------------------
# Contacts — isolation ownership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sales_sees_only_own_contacts(
    client: AsyncClient,
    sales_headers: dict,
    sales_b_headers: dict,
    sales_user: User,
    sales_user_b: User,
):
    """Sales A cree un contact → Sales B ne le voit pas dans la liste."""
    # Sales A cree un contact
    resp = await client.post("/api/v1/contacts", json={
        "first_name": "Alice", "last_name": "Dupont", "email": "alice@test.fr",
    }, headers=sales_headers)
    assert resp.status_code == 201
    contact_id = resp.json()["id"]

    # Sales A voit son contact
    resp = await client.get("/api/v1/contacts", headers=sales_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    # Sales B ne voit rien
    resp = await client.get("/api/v1/contacts", headers=sales_b_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0

    # Sales B ne peut pas GET le contact de A
    resp = await client.get(f"/api/v1/contacts/{contact_id}", headers=sales_b_headers)
    assert resp.status_code == 403

    # Sales B ne peut pas PUT le contact de A
    resp = await client.put(f"/api/v1/contacts/{contact_id}", json={
        "first_name": "Hack",
    }, headers=sales_b_headers)
    assert resp.status_code == 403

    # Sales B ne peut pas DELETE le contact de A
    resp = await client.delete(f"/api/v1/contacts/{contact_id}", headers=sales_b_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_sees_all_contacts(
    client: AsyncClient,
    auth_headers: dict,
    sales_headers: dict,
    test_user: User,
    sales_user: User,
):
    """Admin voit les contacts de tous les utilisateurs."""
    # Sales cree un contact
    resp = await client.post("/api/v1/contacts", json={
        "first_name": "Bob", "last_name": "Martin", "email": "bob@test.fr",
    }, headers=sales_headers)
    assert resp.status_code == 201

    # Admin voit le contact du sales
    resp = await client.get("/api/v1/contacts", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


@pytest.mark.asyncio
async def test_manager_sees_all_contacts(
    client: AsyncClient,
    manager_headers: dict,
    sales_headers: dict,
    manager_user: User,
    sales_user: User,
):
    """Manager voit les contacts de tous les utilisateurs."""
    # Sales cree un contact
    resp = await client.post("/api/v1/contacts", json={
        "first_name": "Claire", "last_name": "Leroy", "email": "claire@test.fr",
    }, headers=sales_headers)
    assert resp.status_code == 201

    # Manager voit le contact du sales
    resp = await client.get("/api/v1/contacts", headers=manager_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] >= 1


# ---------------------------------------------------------------------------
# Companies — isolation ownership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sales_sees_only_own_companies(
    client: AsyncClient,
    sales_headers: dict,
    sales_b_headers: dict,
    sales_user: User,
    sales_user_b: User,
):
    """Sales A cree une entreprise → Sales B ne la voit pas."""
    resp = await client.post("/api/v1/companies", json={
        "name": "Acme Corp",
    }, headers=sales_headers)
    assert resp.status_code == 201
    company_id = resp.json()["id"]

    # Sales B ne voit pas
    resp = await client.get("/api/v1/companies", headers=sales_b_headers)
    assert resp.json()["total"] == 0

    # Sales B ne peut pas GET
    resp = await client.get(f"/api/v1/companies/{company_id}", headers=sales_b_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Deals — isolation ownership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sales_sees_only_own_deals(
    client: AsyncClient,
    sales_headers: dict,
    sales_b_headers: dict,
    sales_user: User,
    sales_user_b: User,
):
    """Sales A cree un deal → Sales B ne le voit pas."""
    resp = await client.post("/api/v1/deals", json={
        "title": "Deal Secret", "amount": 10000,
    }, headers=sales_headers)
    assert resp.status_code == 201
    deal_id = resp.json()["id"]

    # Sales B ne voit pas
    resp = await client.get("/api/v1/deals", headers=sales_b_headers)
    assert resp.json()["total"] == 0

    # Sales B ne peut pas changer le stage
    resp = await client.patch(f"/api/v1/deals/{deal_id}/stage", json={
        "stage": "won",
    }, headers=sales_b_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Tasks — isolation ownership (assigned_to)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sales_sees_only_own_tasks(
    client: AsyncClient,
    sales_headers: dict,
    sales_b_headers: dict,
    sales_user: User,
    sales_user_b: User,
):
    """Sales A cree une tache → Sales B ne la voit pas."""
    resp = await client.post("/api/v1/tasks", json={
        "title": "Ma tache privee", "type": "todo", "priority": "high",
    }, headers=sales_headers)
    assert resp.status_code == 201
    task_id = resp.json()["id"]

    # La tache est assignee a Sales A par defaut
    assert resp.json()["assigned_to"] == str(sales_user.id)

    # Sales B ne voit pas
    resp = await client.get("/api/v1/tasks", headers=sales_b_headers)
    assert resp.json()["total"] == 0

    # Sales B ne peut pas completer la tache de A
    resp = await client.patch(f"/api/v1/tasks/{task_id}/complete", json={
        "is_completed": True,
    }, headers=sales_b_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Activities — isolation ownership (user_id)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sales_sees_only_own_activities(
    client: AsyncClient,
    sales_headers: dict,
    sales_b_headers: dict,
    sales_user: User,
    sales_user_b: User,
):
    """Sales A cree une activite → Sales B ne la voit pas."""
    resp = await client.post("/api/v1/activities", json={
        "type": "note", "subject": "Note privee",
    }, headers=sales_headers)
    assert resp.status_code == 201
    activity_id = resp.json()["id"]

    # Sales B ne voit pas
    resp = await client.get("/api/v1/activities", headers=sales_b_headers)
    assert resp.json()["total"] == 0

    # Sales B ne peut pas GET
    resp = await client.get(f"/api/v1/activities/{activity_id}", headers=sales_b_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Search — filtrage ownership pour sales
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_respects_ownership(
    client: AsyncClient,
    sales_headers: dict,
    sales_b_headers: dict,
    sales_user: User,
    sales_user_b: User,
):
    """La recherche globale ne retourne que les entites du sales."""
    # Sales A cree un contact
    await client.post("/api/v1/contacts", json={
        "first_name": "Unique", "last_name": "Searchable", "email": "unique@test.fr",
    }, headers=sales_headers)

    # Sales A trouve son contact
    resp = await client.get("/api/v1/search?q=Unique", headers=sales_headers)
    assert resp.status_code == 200
    data = resp.json()
    total_results = len(data.get("contacts", [])) + len(data.get("companies", [])) + len(data.get("deals", []))
    assert total_results >= 1

    # Sales B ne trouve rien
    resp = await client.get("/api/v1/search?q=Unique", headers=sales_b_headers)
    assert resp.status_code == 200
    data = resp.json()
    total_results = len(data.get("contacts", [])) + len(data.get("companies", [])) + len(data.get("deals", []))
    assert total_results == 0
