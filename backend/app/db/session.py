# =============================================================================
# FGA CRM - Database Session
# =============================================================================

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings

# Engine principal (FastAPI) : pool persistant, une seule boucle asyncio (uvicorn).
engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_pool_max_overflow,
    echo=settings.app_debug,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Engine dedie aux tasks Celery : NullPool -> AUCUNE connexion reutilisee entre
# les boucles asyncio. Chaque task fait `asyncio.run(...)` = nouvelle boucle ; une
# connexion poolee creee dans une boucle precedente, reutilisee dans la suivante,
# provoque asyncpg "another operation is in progress" / cross-loop. NullPool ouvre
# et ferme une connexion fraiche a chaque checkout -> pas de fuite entre boucles.
task_engine = create_async_engine(
    settings.database_url,
    poolclass=NullPool,
    echo=settings.app_debug,
)

task_session_maker = async_sessionmaker(
    task_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Creer les tables manquantes en dev/test.

    En production, les migrations sont gerees par Alembic
    (`alembic upgrade head` execute par le Docker entrypoint).
    On skip ici pour eviter tout conflit entre create_all et alembic.
    """
    if settings.is_production:
        return

    from app.models import Base  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    await engine.dispose()


async def get_db() -> AsyncSession:
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
