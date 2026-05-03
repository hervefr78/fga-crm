# ADR-002 : SQLite in-memory pour les tests

## Date
2026-02-22

## Statut
accepted

## Contexte
Les tests API ont besoin d'une base de donnees. PostgreSQL est utilise en production, mais lancer un container PostgreSQL pour chaque run de tests ralentit le feedback loop.

## Decision
Utiliser SQLite in-memory pour les tests avec un mapping JSONB → JSON dans le conftest. Les tests utilisent `create_all()` pour creer les tables a chaque session.

## Alternatives envisagees
- PostgreSQL en container pour les tests — rejetee parce que trop lent pour le dev local, complexifie le CI
- PostgreSQL testcontainers — rejetee parce que dependance supplementaire, meme overhead

## Consequences
- Les colonnes JSONB doivent etre mappees vers JSON dans le conftest (`JSONB: JSON`)
- Certains comportements PostgreSQL specifiques (full-text search, array ops) ne sont pas testables
- `follow_redirects=True` necessaire dans httpx (SQLite + FastAPI trailing slash redirect)
- Suffisant pour 155+ tests API avec bonne couverture

## Fichiers impactes
- `backend/tests/conftest.py` — mapping JSONB, fixtures DB, client async
