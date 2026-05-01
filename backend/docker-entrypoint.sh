#!/bin/sh
# =============================================================================
# FGA CRM - Backend entrypoint
# =============================================================================
# Applique les migrations Alembic AVANT de demarrer l'app.
# Si argument fourni, l'execute (utilise pour Celery worker via override).
# Sinon, lance uvicorn par defaut.
# =============================================================================

set -e

# RUN_MIGRATIONS=1 par defaut. A passer a 0 pour les conteneurs satellites
# (worker Celery) afin d'eviter la race condition au boot (Postgres advisory
# lock evite la corruption mais on prefere un seul migrateur).
RUN_MIGRATIONS="${RUN_MIGRATIONS:-1}"

if [ "$RUN_MIGRATIONS" = "1" ]; then
    echo "[entrypoint] Applying Alembic migrations..."
    alembic upgrade head
else
    echo "[entrypoint] RUN_MIGRATIONS=0, skipping alembic upgrade"
fi

if [ "$#" -gt 0 ]; then
    echo "[entrypoint] Exec custom command: $*"
    exec "$@"
else
    echo "[entrypoint] Starting uvicorn..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
