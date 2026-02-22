# =============================================================================
# FGA CRM - Tests API Activities CRUD
# =============================================================================

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_activity(client: AsyncClient, auth_headers: dict):
    """Creer une activite avec les champs minimum."""
    response = await client.post("/api/v1/activities/", json={
        "type": "call",
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "call"
    assert data["user_id"] is not None


@pytest.mark.asyncio
async def test_create_activity_full(client: AsyncClient, auth_headers: dict):
    """Creer une activite avec tous les champs."""
    response = await client.post("/api/v1/activities/", json={
        "type": "email",
        "subject": "Relance Q1",
        "content": "Bonjour, suite a notre echange...",
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["type"] == "email"
    assert data["subject"] == "Relance Q1"


@pytest.mark.asyncio
async def test_create_activity_invalid_type(client: AsyncClient, auth_headers: dict):
    """Type invalide doit retourner 422."""
    response = await client.post("/api/v1/activities/", json={
        "type": "sms",
    }, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_activities(client: AsyncClient, auth_headers: dict):
    """Lister les activites (paginee)."""
    await client.post("/api/v1/activities/", json={"type": "call"}, headers=auth_headers)
    await client.post("/api/v1/activities/", json={"type": "note", "subject": "RDV"}, headers=auth_headers)

    response = await client.get("/api/v1/activities/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_get_activity(client: AsyncClient, auth_headers: dict):
    """Recuperer une activite par ID."""
    create_resp = await client.post("/api/v1/activities/", json={
        "type": "meeting",
        "subject": "Demo",
    }, headers=auth_headers)
    activity_id = create_resp.json()["id"]

    response = await client.get(f"/api/v1/activities/{activity_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["subject"] == "Demo"


@pytest.mark.asyncio
async def test_update_activity(client: AsyncClient, auth_headers: dict):
    """Mise a jour d'une activite."""
    create_resp = await client.post("/api/v1/activities/", json={
        "type": "note",
        "subject": "Avant",
    }, headers=auth_headers)
    activity_id = create_resp.json()["id"]

    response = await client.put(f"/api/v1/activities/{activity_id}", json={
        "subject": "Apres",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["subject"] == "Apres"


@pytest.mark.asyncio
async def test_delete_activity(client: AsyncClient, auth_headers: dict):
    """Supprimer une activite."""
    create_resp = await client.post("/api/v1/activities/", json={
        "type": "linkedin",
    }, headers=auth_headers)
    activity_id = create_resp.json()["id"]

    response = await client.delete(f"/api/v1/activities/{activity_id}", headers=auth_headers)
    assert response.status_code == 204

    response = await client.get(f"/api/v1/activities/{activity_id}", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_activity_user_id_auto_set(client: AsyncClient, auth_headers: dict):
    """Le user_id est automatiquement set depuis le token."""
    response = await client.post("/api/v1/activities/", json={
        "type": "task",
    }, headers=auth_headers)
    data = response.json()
    assert data["user_id"] is not None
    assert len(data["user_id"]) == 36  # UUID format


@pytest.mark.asyncio
async def test_activities_unauthenticated(client: AsyncClient):
    """Acces sans token = 403."""
    response = await client.get("/api/v1/activities/")
    assert response.status_code == 403
