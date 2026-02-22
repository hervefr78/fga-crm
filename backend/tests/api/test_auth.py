# =============================================================================
# FGA CRM - Tests API Auth (register, login, me)
# =============================================================================

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    """Enregistrer un nouvel utilisateur."""
    response = await client.post("/api/v1/auth/register", json={
        "email": "new@fga.fr",
        "password": "Secure1234!",
        "full_name": "New User",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new@fga.fr"
    assert data["full_name"] == "New User"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Interdire l'enregistrement d'un email deja pris."""
    payload = {"email": "dup@fga.fr", "password": "Pass1234!", "full_name": "Dup"}
    await client.post("/api/v1/auth/register", json=payload)
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """Login avec les bons identifiants."""
    # D'abord enregistrer
    await client.post("/api/v1/auth/register", json={
        "email": "login@fga.fr",
        "password": "Pass1234!",
        "full_name": "Login User",
    })
    # Puis login via form-encoded (OAuth2PasswordRequestForm)
    response = await client.post("/api/v1/auth/login", data={
        "username": "login@fga.fr",
        "password": "Pass1234!",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Login echoue avec un mauvais mot de passe."""
    await client.post("/api/v1/auth/register", json={
        "email": "wrong@fga.fr",
        "password": "CorrectPass1!",
        "full_name": "Wrong",
    })
    response = await client.post("/api/v1/auth/login", data={
        "username": "wrong@fga.fr",
        "password": "WrongPass1!",
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient):
    """GET /auth/me retourne l'utilisateur connecte."""
    # Enregistrer + login
    await client.post("/api/v1/auth/register", json={
        "email": "me@fga.fr",
        "password": "Pass1234!",
        "full_name": "Me User",
    })
    login_resp = await client.post("/api/v1/auth/login", data={
        "username": "me@fga.fr",
        "password": "Pass1234!",
    })
    token = login_resp.json()["access_token"]
    # Appeler /me
    response = await client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {token}",
    })
    assert response.status_code == 200
    assert response.json()["email"] == "me@fga.fr"


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    """GET /auth/me sans token = 403."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403
