# =============================================================================
# FGA CRM - Tests Registration (role attribution automatique)
# =============================================================================

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_first_user_gets_admin_role(client: AsyncClient):
    """Le premier utilisateur inscrit recoit le role admin."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "first@fga.fr",
        "password": "Secure1234!",
        "full_name": "First User",
    })
    assert resp.status_code == 201
    assert resp.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_second_user_gets_sales_role(client: AsyncClient):
    """Le deuxieme utilisateur inscrit recoit le role sales."""
    # Premier utilisateur → admin
    await client.post("/api/v1/auth/register", json={
        "email": "admin@fga.fr",
        "password": "Secure1234!",
        "full_name": "Admin User",
    })

    # Deuxieme utilisateur → sales
    resp = await client.post("/api/v1/auth/register", json={
        "email": "sales@fga.fr",
        "password": "Secure1234!",
        "full_name": "Sales User",
    })
    assert resp.status_code == 201
    assert resp.json()["role"] == "sales"


@pytest.mark.asyncio
async def test_third_user_also_gets_sales_role(client: AsyncClient):
    """Le troisieme utilisateur recoit aussi le role sales."""
    await client.post("/api/v1/auth/register", json={
        "email": "admin@fga.fr", "password": "Secure1234!", "full_name": "Admin",
    })
    await client.post("/api/v1/auth/register", json={
        "email": "user2@fga.fr", "password": "Secure1234!", "full_name": "User 2",
    })
    resp = await client.post("/api/v1/auth/register", json={
        "email": "user3@fga.fr", "password": "Secure1234!", "full_name": "User 3",
    })
    assert resp.status_code == 201
    assert resp.json()["role"] == "sales"
