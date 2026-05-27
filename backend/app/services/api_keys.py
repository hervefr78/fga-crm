# =============================================================================
# FGA CRM - Service API Keys (async)
# =============================================================================
# Création, validation et révocation des clés API service-to-service.
# Standard : crm_<32_bytes_hex>, hash SHA-256, jamais la clé en clair en DB.
# Doc : ~/Documents/Claude/docs/SERVICE_AUTH_STANDARD.md

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey
from app.models.user import User

KEY_PREFIX = "crm_"
KEY_BYTES = 32  # 64 chars hex


def _hash_key(raw_key: str) -> str:
    """SHA-256 du raw_key → stocké en base."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def create_api_key(
    db: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    scopes: list[str] | None = None,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Crée une API key. Retourne (record, raw_key).

    Le raw_key n'est retourné qu'une seule fois — il n'est jamais stocké en clair.
    """
    raw_key = KEY_PREFIX + secrets.token_hex(KEY_BYTES)
    key_hash = _hash_key(raw_key)

    api_key = ApiKey(
        user_id=user_id,
        key_hash=key_hash,
        name=name,
        scopes=scopes or [],
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.flush()

    return api_key, raw_key


async def validate_api_key(
    db: AsyncSession,
    raw_key: str,
) -> tuple[ApiKey, User] | None:
    """Valide une API key et retourne (ApiKey, User) associé.

    Met à jour last_used_at atomiquement.
    Retourne None si invalide, révoquée ou expirée.
    """
    key_hash = _hash_key(raw_key)

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active.is_(True),
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        return None

    # Vérifier expiration (SQLite retourne naive, PostgreSQL retourne aware)
    if api_key.expires_at:
        expires_at = api_key.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            return None

    # Charger le user associé
    user_result = await db.execute(select(User).where(User.id == api_key.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        return None

    # MAJ last_used_at (fire-and-forget dans la même transaction)
    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key.id)
        .values(last_used_at=datetime.now(UTC))
    )

    return api_key, user


async def revoke_api_key(db: AsyncSession, key_id: uuid.UUID) -> bool:
    """Révoque une API key (soft-delete : is_active=False + revoked_at). Admin only."""
    result = await db.execute(
        update(ApiKey)
        .where(ApiKey.id == key_id, ApiKey.is_active.is_(True))
        .values(is_active=False, revoked_at=datetime.now(UTC))
    )
    return (result.rowcount or 0) > 0


async def list_api_keys(db: AsyncSession) -> list[ApiKey]:
    """Liste toutes les API keys (actives + révoquées) pour l'admin."""
    result = await db.execute(
        select(ApiKey).order_by(ApiKey.created_at.desc())
    )
    return list(result.scalars().all())


async def get_or_create_service_account(
    db: AsyncSession,
    email: str,
    full_name: str,
    hashed_password: str = "$2b$12$disabled",  # compte désactivé pour connexion UI  # noqa: S107
) -> User:
    """Retourne le service account existant ou le crée.

    Les service accounts ont is_service=True et ne peuvent pas se connecter via l'UI.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role="service",
            is_active=True,
            is_service=True,
        )
        db.add(user)
        await db.flush()
    return user
