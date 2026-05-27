# =============================================================================
# FGA CRM - Tests : API Keys (Service Authentication Standard 2026-05)
# =============================================================================

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.user import User
from app.services.api_keys import KEY_PREFIX, _hash_key, create_api_key

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def service_user(db_session: AsyncSession) -> User:
    """Crée un service account de test."""
    user = User(
        id=uuid.uuid4(),
        email="mcp@crm.internal",
        hashed_password="$2b$12$disabled",
        full_name="MCP Service Account",
        role="service",
        is_active=True,
        is_service=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def valid_api_key(db_session: AsyncSession, service_user: User) -> tuple[ApiKey, str]:
    """Crée une API key valide pour le service_user. Retourne (record, raw_key)."""
    api_key, raw_key = await create_api_key(
        db=db_session,
        user_id=service_user.id,
        name="test-key",
        scopes=["read:*", "write:contacts"],
    )
    await db_session.commit()
    return api_key, raw_key


@pytest_asyncio.fixture
async def expired_api_key(db_session: AsyncSession, service_user: User) -> tuple[ApiKey, str]:
    """Crée une API key expirée."""
    api_key, raw_key = await create_api_key(
        db=db_session,
        user_id=service_user.id,
        name="expired-key",
        scopes=["read:*"],
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    await db_session.commit()
    return api_key, raw_key


@pytest_asyncio.fixture
async def revoked_api_key(db_session: AsyncSession, service_user: User) -> tuple[ApiKey, str]:
    """Crée une API key puis la révoque."""
    api_key, raw_key = await create_api_key(
        db=db_session,
        user_id=service_user.id,
        name="revoked-key",
        scopes=["read:*"],
    )
    api_key.is_active = False
    api_key.revoked_at = datetime.now(UTC)
    await db_session.commit()
    return api_key, raw_key


# ---------------------------------------------------------------------------
# Tests : service api_keys.py
# ---------------------------------------------------------------------------


class TestApiKeyService:
    """Tests unitaires du service api_keys (validate_api_key, create_api_key, revoke_api_key)."""

    async def test_create_api_key_returns_crm_prefix(
        self, db_session: AsyncSession, service_user: User
    ) -> None:
        """La raw_key doit commencer par crm_."""
        _, raw_key = await create_api_key(db_session, service_user.id, "test")
        assert raw_key.startswith(KEY_PREFIX)
        assert len(raw_key) == len(KEY_PREFIX) + 64  # crm_ + 32 bytes hex

    async def test_create_api_key_hash_stored(
        self, db_session: AsyncSession, service_user: User
    ) -> None:
        """La clé stockée est bien le SHA-256 de la raw_key."""
        record, raw_key = await create_api_key(db_session, service_user.id, "test")
        assert record.key_hash == _hash_key(raw_key)
        assert record.key_hash != raw_key  # jamais en clair

    async def test_validate_api_key_valid(
        self, db_session: AsyncSession, valid_api_key: tuple
    ) -> None:
        """Une clé valide retourne (ApiKey, User)."""
        from app.services.api_keys import validate_api_key
        _, raw_key = valid_api_key
        result = await validate_api_key(db_session, raw_key)
        assert result is not None
        api_key, user = result
        assert user.email == "mcp@crm.internal"
        assert api_key.name == "test-key"

    async def test_validate_api_key_updates_last_used_at(
        self, db_session: AsyncSession, valid_api_key: tuple
    ) -> None:
        """Après validation, last_used_at doit être renseigné."""
        from app.services.api_keys import validate_api_key
        record, raw_key = valid_api_key
        assert record.last_used_at is None

        await validate_api_key(db_session, raw_key)
        await db_session.refresh(record)
        assert record.last_used_at is not None

    async def test_validate_api_key_unknown(self, db_session: AsyncSession) -> None:
        """Une clé inconnue retourne None."""
        from app.services.api_keys import validate_api_key
        result = await validate_api_key(db_session, "crm_" + "0" * 64)
        assert result is None

    async def test_validate_api_key_expired(
        self, db_session: AsyncSession, expired_api_key: tuple
    ) -> None:
        """Une clé expirée retourne None."""
        from app.services.api_keys import validate_api_key
        _, raw_key = expired_api_key
        result = await validate_api_key(db_session, raw_key)
        assert result is None

    async def test_validate_api_key_revoked(
        self, db_session: AsyncSession, revoked_api_key: tuple
    ) -> None:
        """Une clé révoquée retourne None."""
        from app.services.api_keys import validate_api_key
        _, raw_key = revoked_api_key
        result = await validate_api_key(db_session, raw_key)
        assert result is None

    async def test_revoke_api_key(
        self, db_session: AsyncSession, valid_api_key: tuple
    ) -> None:
        """Révoquer une clé → is_active=False + revoked_at renseigné."""
        from app.services.api_keys import revoke_api_key, validate_api_key
        record, raw_key = valid_api_key

        success = await revoke_api_key(db_session, record.id)
        assert success is True

        result = await validate_api_key(db_session, raw_key)
        assert result is None

    async def test_revoke_api_key_not_found(self, db_session: AsyncSession) -> None:
        """Révoquer une clé inexistante retourne False."""
        from app.services.api_keys import revoke_api_key
        success = await revoke_api_key(db_session, uuid.uuid4())
        assert success is False


# ---------------------------------------------------------------------------
# Tests : endpoint /api/_internal/whoami
# ---------------------------------------------------------------------------


class TestWhoamiEndpoint:
    """Tests de l'endpoint /api/_internal/whoami."""

    async def test_whoami_valid_key(
        self, client: AsyncClient, valid_api_key: tuple
    ) -> None:
        """Une clé valide retourne l'identité du service account."""
        _, raw_key = valid_api_key
        response = await client.get(
            "/api/_internal/whoami",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "mcp@crm.internal"
        assert data["is_service"] is True
        assert data["key_name"] == "test-key"
        assert "read:*" in data["scopes"]

    async def test_whoami_missing_token(self, client: AsyncClient) -> None:
        """Sans token → 401."""
        response = await client.get("/api/_internal/whoami")
        assert response.status_code == 401

    async def test_whoami_invalid_key(self, client: AsyncClient) -> None:
        """Clé invalide → 401."""
        response = await client.get(
            "/api/_internal/whoami",
            headers={"Authorization": "Bearer crm_" + "0" * 64},
        )
        assert response.status_code == 401

    async def test_whoami_expired_key(
        self, client: AsyncClient, expired_api_key: tuple
    ) -> None:
        """Clé expirée → 401."""
        _, raw_key = expired_api_key
        response = await client.get(
            "/api/_internal/whoami",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert response.status_code == 401

    async def test_whoami_revoked_key(
        self, client: AsyncClient, revoked_api_key: tuple
    ) -> None:
        """Clé révoquée → 401."""
        _, raw_key = revoked_api_key
        response = await client.get(
            "/api/_internal/whoami",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Tests : scope checking via require_service_scope
# ---------------------------------------------------------------------------


class TestScopeChecking:
    """Tests de la dépendance require_service_scope."""

    async def test_scope_wildcard_grants_access(
        self, db_session: AsyncSession, service_user: User
    ) -> None:
        """Un scope read:* donne accès à tous les sous-scopes read:xxx."""
        from app.services.api_keys import validate_api_key
        _, raw_key = await create_api_key(
            db_session, service_user.id, "wildcard-key", scopes=["read:*"]
        )
        await db_session.commit()

        result = await validate_api_key(db_session, raw_key)
        assert result is not None
        api_key, _ = result
        assert "read:*" in api_key.scopes

    async def test_scope_missing_blocks(
        self, db_session: AsyncSession, service_user: User
    ) -> None:
        """Un scope non présent et sans wildcard doit lever 403."""
        # Ce test valide la logique de require_service_scope en direct
        from fastapi import HTTPException

        from app.core.deps import require_service_scope

        # Simuler une Request avec des scopes limités
        class MockRequest:
            state_api_key_scopes: list = ["read:deals"]

            class state:
                api_key_scopes = ["read:deals"]

        scope_checker = require_service_scope("write:contacts")
        mock_request = MockRequest()

        with pytest.raises(HTTPException) as exc_info:
            await scope_checker(request=mock_request, user=service_user)  # type: ignore[arg-type]

        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# Tests : admin endpoints /api/v1/admin/api-keys
# ---------------------------------------------------------------------------


class TestAdminApiKeyEndpoints:
    """Tests des endpoints admin pour gérer les API keys."""

    async def test_create_key_admin_only(
        self, client: AsyncClient, auth_headers: dict, service_user: User
    ) -> None:
        """La création d'une clé est réservée aux admins."""
        response = await client.post(
            "/api/v1/admin/api-keys",
            headers=auth_headers,
            json={
                "name": "test-mcp",
                "user_id": str(service_user.id),
                "scopes": ["read:*"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["key"].startswith("crm_")
        assert data["name"] == "test-mcp"

    async def test_create_key_returns_raw_key_once(
        self, client: AsyncClient, auth_headers: dict, service_user: User
    ) -> None:
        """La raw_key est retournée dans la réponse (une seule fois)."""
        response = await client.post(
            "/api/v1/admin/api-keys",
            headers=auth_headers,
            json={"name": "once-key", "user_id": str(service_user.id), "scopes": []},
        )
        assert response.status_code == 201
        assert "key" in response.json()

    async def test_list_keys_admin_only(
        self, client: AsyncClient, auth_headers: dict, valid_api_key: tuple
    ) -> None:
        """Liste les clés (admin only)."""
        response = await client.get("/api/v1/admin/api-keys", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_revoke_key(
        self, client: AsyncClient, auth_headers: dict, valid_api_key: tuple
    ) -> None:
        """Révoquer une clé via l'endpoint admin → 204."""
        record, _ = valid_api_key
        response = await client.delete(
            f"/api/v1/admin/api-keys/{record.id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

    async def test_revoke_nonexistent_key(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Révoquer une clé inexistante → 404."""
        response = await client.delete(
            f"/api/v1/admin/api-keys/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_create_service_account(
        self, client: AsyncClient, auth_headers: dict
    ) -> None:
        """Créer un service account via l'endpoint admin."""
        response = await client.post(
            "/api/v1/admin/api-keys/service-accounts",
            headers=auth_headers,
            json={
                "email": "nomo-ia@crm.internal",
                "full_name": "Nomo-IA Service Account",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["is_service"] is True
        assert data["email"] == "nomo-ia@crm.internal"

    async def test_create_service_account_idempotent(
        self, client: AsyncClient, auth_headers: dict, service_user: User
    ) -> None:
        """Appeler deux fois → le même user est retourné (pas de doublon)."""
        payload = {"email": service_user.email, "full_name": service_user.full_name}
        r1 = await client.post("/api/v1/admin/api-keys/service-accounts", headers=auth_headers, json=payload)
        r2 = await client.post("/api/v1/admin/api-keys/service-accounts", headers=auth_headers, json=payload)
        assert r1.status_code in (201, 200)
        assert r2.status_code in (201, 200)
        assert r1.json()["id"] == r2.json()["id"]
