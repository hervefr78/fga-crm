# =============================================================================
# FGA CRM - Tests Import CSV (Contacts + Companies)
# =============================================================================

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_import_contacts_valid(client: AsyncClient, auth_headers: dict):
    """Import de contacts valides."""
    response = await client.post("/api/v1/contacts/import", json={
        "rows": [
            {"first_name": "Alice", "last_name": "Import1"},
            {"first_name": "Bob", "last_name": "Import2", "email": "bob@test.com"},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert len(data["errors"]) == 0


@pytest.mark.asyncio
async def test_import_contacts_mixed(client: AsyncClient, auth_headers: dict):
    """Import mix valide/invalide : les valides passent, erreurs collectees."""
    response = await client.post("/api/v1/contacts/import", json={
        "rows": [
            {"first_name": "Valid", "last_name": "Contact"},
            {"first_name": "", "last_name": "Invalid"},  # first_name vide
            {"first_name": "Also", "last_name": "Valid"},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert len(data["errors"]) >= 1
    assert data["errors"][0]["row"] == 2


@pytest.mark.asyncio
async def test_import_contacts_all_invalid(client: AsyncClient, auth_headers: dict):
    """Import ou toutes les lignes sont invalides."""
    response = await client.post("/api/v1/contacts/import", json={
        "rows": [
            {"last_name": "Missing First"},  # first_name manquant
            {"first_name": "A", "last_name": "B", "status": "invalid_status"},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert len(data["errors"]) >= 2


@pytest.mark.asyncio
async def test_import_contacts_empty(client: AsyncClient, auth_headers: dict):
    """Import avec une liste vide."""
    response = await client.post("/api/v1/contacts/import", json={
        "rows": [],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert len(data["errors"]) == 0


@pytest.mark.asyncio
async def test_import_contacts_unauthenticated(client: AsyncClient):
    """Import sans token = 403."""
    response = await client.post("/api/v1/contacts/import", json={"rows": []})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_import_companies_valid(client: AsyncClient, auth_headers: dict):
    """Import d'entreprises valides."""
    response = await client.post("/api/v1/companies/import", json={
        "rows": [
            {"name": "ImportCo1"},
            {"name": "ImportCo2", "country": "France", "size_range": "11-50"},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert len(data["errors"]) == 0


@pytest.mark.asyncio
async def test_import_companies_invalid_size_range(client: AsyncClient, auth_headers: dict):
    """Import avec size_range invalide."""
    response = await client.post("/api/v1/companies/import", json={
        "rows": [
            {"name": "BadCo", "size_range": "not-a-range"},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert len(data["errors"]) >= 1
    assert data["errors"][0]["field"] == "size_range"


@pytest.mark.asyncio
async def test_import_companies_missing_name(client: AsyncClient, auth_headers: dict):
    """Import sans nom d'entreprise."""
    response = await client.post("/api/v1/companies/import", json={
        "rows": [
            {"country": "France"},  # name manquant
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert len(data["errors"]) >= 1
