# =============================================================================
# FGA CRM - Alembic environment
# =============================================================================
# Convertit l'URL async (postgresql+asyncpg) en URL sync (postgresql+psycopg2)
# car Alembic execute les migrations en mode synchrone.
# =============================================================================

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Charger la config applicative et les models pour autogenerate
from app.config import settings
from app.models import Base  # noqa: F401 — importe tous les models

# this is the Alembic Config object
config = context.config

# URL : convertir asyncpg → psycopg2 pour Alembic (sync)
sync_url = settings.database_url.replace(
    "postgresql+asyncpg://", "postgresql+psycopg2://"
)
config.set_main_option("sqlalchemy.url", sync_url)

# Configurer le logging Python depuis alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Cible des metadata pour `--autogenerate`
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Mode offline : generer du SQL sans connexion."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Mode online : appliquer les migrations sur la DB."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
