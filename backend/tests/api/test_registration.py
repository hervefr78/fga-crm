# =============================================================================
# FGA CRM - Tests Registration (multi-tenant : 1 inscription = 1 org)
# =============================================================================

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_creates_org_and_admin(client: AsyncClient):
    """Toute inscription cree une organisation et le user en est l'admin."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "founder@fga.fr",
        "password": "Secure1234!",
        "full_name": "Founder User",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["role"] == "admin"
    assert body["organization_id"]  # une org a bien ete creee et rattachee
    assert body["is_superadmin"] is False  # un signup n'est jamais super-admin


@pytest.mark.asyncio
async def test_each_registration_gets_its_own_org(client: AsyncClient):
    """Deux inscriptions distinctes -> deux organisations distinctes (isolation)."""
    r1 = await client.post("/api/v1/auth/register", json={
        "email": "a@fga.fr", "password": "Secure1234!", "full_name": "User A",
    })
    r2 = await client.post("/api/v1/auth/register", json={
        "email": "b@fga.fr", "password": "Secure1234!", "full_name": "User B",
    })
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["organization_id"] != r2.json()["organization_id"]
    assert r1.json()["role"] == "admin"
    assert r2.json()["role"] == "admin"


@pytest.mark.asyncio
async def test_register_custom_org_name(client: AsyncClient):
    """Le nom d'organisation fourni est accepte."""
    resp = await client.post("/api/v1/auth/register", json={
        "email": "c@fga.fr", "password": "Secure1234!", "full_name": "User C",
        "organization_name": "Acme Corp",
    })
    assert resp.status_code == 201
    assert resp.json()["organization_id"]


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client: AsyncClient):
    """Un email deja enregistre est rejete (unicite globale)."""
    payload = {"email": "dup@fga.fr", "password": "Secure1234!", "full_name": "Dup"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 400
