# =============================================================================
# FGA CRM - Tests Recherche Globale
# =============================================================================

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_global_search_contacts(client: AsyncClient, auth_headers: dict):
    """La recherche globale trouve des contacts."""
    await client.post("/api/v1/contacts/", json={
        "first_name": "Searchable", "last_name": "Person", "email": "sp@test.com",
    }, headers=auth_headers)

    response = await client.get("/api/v1/search/", params={"q": "Searchable"}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["contacts"]) >= 1
    assert data["contacts"][0]["label"] == "Searchable Person"


@pytest.mark.asyncio
async def test_global_search_companies(client: AsyncClient, auth_headers: dict):
    """La recherche globale trouve des entreprises."""
    await client.post("/api/v1/companies/", json={
        "name": "UniqueCompanySearch",
    }, headers=auth_headers)

    response = await client.get("/api/v1/search/", params={"q": "UniqueCompany"}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["companies"]) >= 1


@pytest.mark.asyncio
async def test_global_search_deals(client: AsyncClient, auth_headers: dict):
    """La recherche globale trouve des deals."""
    await client.post("/api/v1/deals/", json={
        "title": "UniqueDealSearch",
    }, headers=auth_headers)

    response = await client.get("/api/v1/search/", params={"q": "UniqueDeal"}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["deals"]) >= 1


@pytest.mark.asyncio
async def test_global_search_cross_entities(client: AsyncClient, auth_headers: dict):
    """La recherche retourne des resultats de plusieurs entites."""
    # Creer des entites avec un terme commun
    await client.post("/api/v1/contacts/", json={
        "first_name": "CrossTest", "last_name": "Contact",
    }, headers=auth_headers)
    await client.post("/api/v1/companies/", json={
        "name": "CrossTest Corp",
    }, headers=auth_headers)

    response = await client.get("/api/v1/search/", params={"q": "CrossTest"}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["contacts"]) >= 1
    assert len(data["companies"]) >= 1


@pytest.mark.asyncio
async def test_global_search_max_results(client: AsyncClient, auth_headers: dict):
    """La recherche est limitee a 5 resultats par entite."""
    # Creer 7 contacts avec le meme prefixe
    for i in range(7):
        await client.post("/api/v1/contacts/", json={
            "first_name": "LimitTest", "last_name": f"Contact{i}",
        }, headers=auth_headers)

    response = await client.get("/api/v1/search/", params={"q": "LimitTest"}, headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["contacts"]) <= 5


@pytest.mark.asyncio
async def test_global_search_empty_results(client: AsyncClient, auth_headers: dict):
    """La recherche avec un terme inexistant retourne des listes vides."""
    response = await client.get("/api/v1/search/", params={"q": "zzzznonexistent"}, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["contacts"]) == 0
    assert len(data["companies"]) == 0
    assert len(data["deals"]) == 0


@pytest.mark.asyncio
async def test_global_search_unauthenticated(client: AsyncClient):
    """Recherche sans token = 403."""
    response = await client.get("/api/v1/search/", params={"q": "test"})
    assert response.status_code == 403
