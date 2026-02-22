# =============================================================================
# FGA CRM - Tests Filtres Avances (Contacts + Companies)
# =============================================================================

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_filter_contacts_by_source(client: AsyncClient, auth_headers: dict):
    """Filtrer les contacts par source."""
    await client.post("/api/v1/contacts/", json={
        "first_name": "Alice", "last_name": "Source", "source": "linkedin",
    }, headers=auth_headers)
    await client.post("/api/v1/contacts/", json={
        "first_name": "Bob", "last_name": "Other", "source": "website",
    }, headers=auth_headers)

    response = await client.get("/api/v1/contacts/", params={"source": "linkedin"}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["source"] == "linkedin"


@pytest.mark.asyncio
async def test_filter_contacts_by_decision_maker(client: AsyncClient, auth_headers: dict):
    """Filtrer les contacts par is_decision_maker."""
    await client.post("/api/v1/contacts/", json={
        "first_name": "DM", "last_name": "Yes", "is_decision_maker": True,
    }, headers=auth_headers)
    await client.post("/api/v1/contacts/", json={
        "first_name": "DM", "last_name": "No", "is_decision_maker": False,
    }, headers=auth_headers)

    response = await client.get("/api/v1/contacts/", params={"is_decision_maker": "true"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["is_decision_maker"] is True


@pytest.mark.asyncio
async def test_filter_contacts_by_created_after(client: AsyncClient, auth_headers: dict):
    """Filtrer les contacts par date de creation."""
    await client.post("/api/v1/contacts/", json={
        "first_name": "Recent", "last_name": "Contact",
    }, headers=auth_headers)

    # Tous les contacts creees maintenant devraient apparaitre apres 2020
    response = await client.get("/api/v1/contacts/", params={
        "created_after": "2020-01-01T00:00:00",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] >= 1


@pytest.mark.asyncio
async def test_filter_contacts_invalid_date(client: AsyncClient, auth_headers: dict):
    """Date invalide retourne 422."""
    response = await client.get("/api/v1/contacts/", params={
        "created_after": "not-a-date",
    }, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_filter_contacts_combined(client: AsyncClient, auth_headers: dict):
    """Combiner search + filtres."""
    await client.post("/api/v1/contacts/", json={
        "first_name": "Marie", "last_name": "Dupont", "source": "linkedin", "status": "qualified",
    }, headers=auth_headers)
    await client.post("/api/v1/contacts/", json={
        "first_name": "Marie", "last_name": "Martin", "source": "website", "status": "new",
    }, headers=auth_headers)

    response = await client.get("/api/v1/contacts/", params={
        "search": "Marie", "source": "linkedin",
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["last_name"] == "Dupont"


@pytest.mark.asyncio
async def test_filter_companies_by_size_range(client: AsyncClient, auth_headers: dict):
    """Filtrer les entreprises par taille."""
    await client.post("/api/v1/companies/", json={
        "name": "Startup", "size_range": "1-10",
    }, headers=auth_headers)
    await client.post("/api/v1/companies/", json={
        "name": "Corp", "size_range": "500+",
    }, headers=auth_headers)

    response = await client.get("/api/v1/companies/", params={"size_range": "1-10"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == "Startup"


@pytest.mark.asyncio
async def test_filter_companies_invalid_size_range(client: AsyncClient, auth_headers: dict):
    """Taille invalide retourne 422."""
    response = await client.get("/api/v1/companies/", params={"size_range": "invalid"}, headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_filter_companies_by_country(client: AsyncClient, auth_headers: dict):
    """Filtrer les entreprises par pays (ILIKE)."""
    await client.post("/api/v1/companies/", json={
        "name": "FrenchCo", "country": "France",
    }, headers=auth_headers)
    await client.post("/api/v1/companies/", json={
        "name": "GermanCo", "country": "Germany",
    }, headers=auth_headers)

    response = await client.get("/api/v1/companies/", params={"country": "france"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["name"] == "FrenchCo"
