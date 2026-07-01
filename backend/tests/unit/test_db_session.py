"""Garde-fou : l'engine des tasks Celery doit utiliser NullPool.

Regression : un pool persistant partage entre plusieurs asyncio.run() (une boucle
par task Celery) provoque asyncpg "another operation is in progress" / cross-loop.
NullPool ouvre une connexion fraiche a chaque checkout -> pas de fuite entre boucles.
"""

from __future__ import annotations

from sqlalchemy.pool import NullPool

from app.db.session import task_engine


def test_task_engine_uses_nullpool():
    assert isinstance(task_engine.pool, NullPool)
