# =============================================================================
# FGA CRM - Conftest (fixtures partagees pour tous les tests)
# =============================================================================

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.types import JSON

from app.core.security import create_access_token, hash_password
from app.db.session import get_db
from app.main import app
from app.models import Base
from app.models.user import User

# ---------------------------------------------------------------------------
# BDD de test — SQLite async en memoire
# Mapper JSONB → JSON pour compatibilite SQLite
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_maker = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# Remplacer JSONB par JSON dans les colonnes pour SQLite
# (PostgreSQL JSONB n'existe pas en SQLite)
for table in Base.metadata.tables.values():
    for column in table.columns:
        if isinstance(column.type, JSONB):
            column.type = JSON()


# ---------------------------------------------------------------------------
# Event loop scope
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def event_loop():
    """Creer un event loop unique pour toute la session de test."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ---------------------------------------------------------------------------
# BDD — creer/detruire les tables autour de chaque test
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Creer les tables avant chaque test, les detruire apres."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ---------------------------------------------------------------------------
# Session DB pour les tests
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        yield session


# ---------------------------------------------------------------------------
# Override de la dependance get_db pour utiliser la BDD de test
# ---------------------------------------------------------------------------

async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with test_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Client HTTP async (httpx) branche sur l'app FastAPI
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as ac:
        yield ac
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Utilisateur de test + token JWT
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Creer un utilisateur de test en BDD."""
    user = User(
        id=uuid.uuid4(),
        email="test@fga.fr",
        hashed_password=hash_password("Test1234!"),
        full_name="Test User",
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    """Headers d'authentification avec un JWT valide (admin)."""
    token = create_access_token(data={"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Utilisateurs multi-roles pour tests RBAC
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def sales_user(db_session: AsyncSession) -> User:
    """Creer un utilisateur sales en BDD."""
    user = User(
        id=uuid.uuid4(),
        email="sales@fga.fr",
        hashed_password=hash_password("Sales1234!"),
        full_name="Sales User",
        role="sales",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def sales_headers(sales_user: User) -> dict[str, str]:
    """Headers d'authentification pour un sales."""
    token = create_access_token(data={"sub": str(sales_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def manager_user(db_session: AsyncSession) -> User:
    """Creer un utilisateur manager en BDD."""
    user = User(
        id=uuid.uuid4(),
        email="manager@fga.fr",
        hashed_password=hash_password("Manager1234!"),
        full_name="Manager User",
        role="manager",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def manager_headers(manager_user: User) -> dict[str, str]:
    """Headers d'authentification pour un manager."""
    token = create_access_token(data={"sub": str(manager_user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sales_user_b(db_session: AsyncSession) -> User:
    """Creer un deuxieme utilisateur sales (pour tests isolation)."""
    user = User(
        id=uuid.uuid4(),
        email="sales-b@fga.fr",
        hashed_password=hash_password("SalesB1234!"),
        full_name="Sales User B",
        role="sales",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def sales_b_headers(sales_user_b: User) -> dict[str, str]:
    """Headers d'authentification pour le deuxieme sales."""
    token = create_access_token(data={"sub": str(sales_user_b.id)})
    return {"Authorization": f"Bearer {token}"}
