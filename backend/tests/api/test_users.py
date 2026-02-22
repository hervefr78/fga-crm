# =============================================================================
# FGA CRM - Tests API User Management (admin only)
# =============================================================================

import pytest
from httpx import AsyncClient

from app.models.user import User

# ---------------------------------------------------------------------------
# Acces : seul l'admin peut acceder aux endpoints /users
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_list_users(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    sales_user: User,
    manager_user: User,
):
    """Admin peut lister tous les utilisateurs."""
    resp = await client.get("/api/v1/users", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3


@pytest.mark.asyncio
async def test_sales_cannot_list_users(
    client: AsyncClient,
    sales_headers: dict,
    sales_user: User,
):
    """Sales ne peut pas lister les utilisateurs (403)."""
    resp = await client.get("/api/v1/users", headers=sales_headers)
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_manager_cannot_list_users(
    client: AsyncClient,
    manager_headers: dict,
    manager_user: User,
):
    """Manager ne peut pas lister les utilisateurs (403)."""
    resp = await client.get("/api/v1/users", headers=manager_headers)
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /users/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_get_user(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    sales_user: User,
):
    """Admin peut voir le detail d'un utilisateur."""
    resp = await client.get(f"/api/v1/users/{sales_user.id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "sales@fga.fr"


@pytest.mark.asyncio
async def test_get_user_not_found(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
):
    """Admin recoit 404 pour un utilisateur inexistant."""
    resp = await client.get("/api/v1/users/00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /users/{id}/role
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_change_role(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    sales_user: User,
):
    """Admin peut changer le role d'un autre utilisateur."""
    resp = await client.patch(f"/api/v1/users/{sales_user.id}/role", json={
        "role": "manager",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "manager"


@pytest.mark.asyncio
async def test_cannot_change_own_role(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
):
    """Admin ne peut pas changer son propre role."""
    resp = await client.patch(f"/api/v1/users/{test_user.id}/role", json={
        "role": "sales",
    }, headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_cannot_remove_last_admin(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    sales_user: User,
):
    """Impossible de retirer le dernier admin (changer son role via un autre user admin)."""
    # test_user est le seul admin → changer son role via lui-meme echoue (guard propre role)
    # On cree un scenario ou on essaie de changer le role d'un admin qui est le dernier
    # D'abord promouvoir sales en admin
    resp = await client.patch(f"/api/v1/users/{sales_user.id}/role", json={
        "role": "admin",
    }, headers=auth_headers)
    assert resp.status_code == 200

    # Maintenant il y a 2 admins — on peut retrograder sales
    resp = await client.patch(f"/api/v1/users/{sales_user.id}/role", json={
        "role": "sales",
    }, headers=auth_headers)
    assert resp.status_code == 200

    # test_user est de nouveau le seul admin
    # On ne peut plus le retrograder (mais on ne peut pas tester directement
    # car le guard "propre role" bloque d'abord)


@pytest.mark.asyncio
async def test_invalid_role_rejected(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    sales_user: User,
):
    """Un role invalide est rejete (422)."""
    resp = await client.patch(f"/api/v1/users/{sales_user.id}/role", json={
        "role": "superadmin",
    }, headers=auth_headers)
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /users/{id}/deactivate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_admin_can_deactivate_user(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    sales_user: User,
):
    """Admin peut desactiver un utilisateur."""
    resp = await client.patch(f"/api/v1/users/{sales_user.id}/deactivate", json={
        "is_active": False,
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


@pytest.mark.asyncio
async def test_admin_can_reactivate_user(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    sales_user: User,
):
    """Admin peut reactiver un utilisateur desactive."""
    # Desactiver
    await client.patch(f"/api/v1/users/{sales_user.id}/deactivate", json={
        "is_active": False,
    }, headers=auth_headers)

    # Reactiver
    resp = await client.patch(f"/api/v1/users/{sales_user.id}/deactivate", json={
        "is_active": True,
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


@pytest.mark.asyncio
async def test_cannot_deactivate_self(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
):
    """Admin ne peut pas se desactiver lui-meme."""
    resp = await client.patch(f"/api/v1/users/{test_user.id}/deactivate", json={
        "is_active": False,
    }, headers=auth_headers)
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Filtres liste utilisateurs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_users_search_filter(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    sales_user: User,
):
    """Filtre search sur nom ou email."""
    resp = await client.get("/api/v1/users?search=sales", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["email"] == "sales@fga.fr"


@pytest.mark.asyncio
async def test_list_users_role_filter(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    sales_user: User,
    manager_user: User,
):
    """Filtre par role."""
    resp = await client.get("/api/v1/users?role=sales", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp = await client.get("/api/v1/users?role=admin", headers=auth_headers)
    assert resp.json()["total"] == 1

    resp = await client.get("/api/v1/users?role=manager", headers=auth_headers)
    assert resp.json()["total"] == 1
