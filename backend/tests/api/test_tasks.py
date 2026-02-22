# =============================================================================
# FGA CRM - Tests API Tasks CRUD
# =============================================================================

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_task(client: AsyncClient, auth_headers: dict):
    """Creer une tache avec les champs minimum."""
    response = await client.post("/api/v1/tasks/", json={
        "title": "Appeler le prospect",
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Appeler le prospect"
    assert data["type"] == "todo"
    assert data["priority"] == "medium"
    assert data["is_completed"] is False


@pytest.mark.asyncio
async def test_create_task_full(client: AsyncClient, auth_headers: dict):
    """Creer une tache avec tous les champs."""
    response = await client.post("/api/v1/tasks/", json={
        "title": "Demo produit",
        "description": "Preparer slides + demo live",
        "type": "meeting",
        "priority": "high",
        "due_date": "2026-03-15T14:00:00",
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "meeting"
    assert data["priority"] == "high"
    assert data["due_date"] is not None


@pytest.mark.asyncio
async def test_create_task_invalid_type(client: AsyncClient, auth_headers: dict):
    """Type invalide doit retourner 422."""
    response = await client.post("/api/v1/tasks/", json={
        "title": "Test",
        "type": "invalid",
    }, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_tasks(client: AsyncClient, auth_headers: dict):
    """Lister les taches (paginee)."""
    # Creer 2 taches
    await client.post("/api/v1/tasks/", json={"title": "Tache 1"}, headers=auth_headers)
    await client.post("/api/v1/tasks/", json={"title": "Tache 2"}, headers=auth_headers)

    response = await client.get("/api/v1/tasks/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


@pytest.mark.asyncio
async def test_get_task(client: AsyncClient, auth_headers: dict):
    """Recuperer une tache par ID."""
    create_resp = await client.post("/api/v1/tasks/", json={
        "title": "Detail test",
    }, headers=auth_headers)
    task_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Detail test"


@pytest.mark.asyncio
async def test_update_task(client: AsyncClient, auth_headers: dict):
    """Mise a jour partielle d'une tache."""
    create_resp = await client.post("/api/v1/tasks/", json={
        "title": "Avant update",
    }, headers=auth_headers)
    task_id = create_resp.json()["id"]

    response = await client.put(f"/api/v1/tasks/{task_id}", json={
        "title": "Apres update",
        "priority": "urgent",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Apres update"
    assert response.json()["priority"] == "urgent"


@pytest.mark.asyncio
async def test_toggle_completion(client: AsyncClient, auth_headers: dict):
    """Toggle completion d'une tache."""
    create_resp = await client.post("/api/v1/tasks/", json={
        "title": "A completer",
    }, headers=auth_headers)
    task_id = create_resp.json()["id"]
    assert create_resp.json()["is_completed"] is False

    # Completer
    response = await client.patch(f"/api/v1/tasks/{task_id}/complete", json={
        "is_completed": True,
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["is_completed"] is True
    assert response.json()["completed_at"] is not None

    # De-completer
    response = await client.patch(f"/api/v1/tasks/{task_id}/complete", json={
        "is_completed": False,
    }, headers=auth_headers)
    assert response.json()["is_completed"] is False
    assert response.json()["completed_at"] is None


@pytest.mark.asyncio
async def test_delete_task(client: AsyncClient, auth_headers: dict):
    """Supprimer une tache."""
    create_resp = await client.post("/api/v1/tasks/", json={
        "title": "A supprimer",
    }, headers=auth_headers)
    task_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert response.status_code == 204

    # Verifier qu'elle n'existe plus
    response = await client.get(f"/api/v1/tasks/{task_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_task_not_found(client: AsyncClient, auth_headers: dict):
    """Tache inexistante retourne 404."""
    response = await client.get(
        "/api/v1/tasks/00000000-0000-0000-0000-000000000000",
        headers=auth_headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_tasks_unauthenticated(client: AsyncClient):
    """Acces sans token = 403."""
    response = await client.get("/api/v1/tasks/")
    assert response.status_code == 403
