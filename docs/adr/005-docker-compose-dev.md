# ADR-005 : Docker Compose pour le developpement local

## Date
2026-04-01

## Statut
accepted

## Contexte
Le projet necessite plusieurs services (PostgreSQL, Redis, MinIO, backend FastAPI, worker Celery, frontend React). Le dev local doit etre reproductible et isolé des autres projets (Startup Radar, DevHub, etc.).

## Decision
Utiliser Docker Compose avec des ports dedies pour eviter les conflits :
- Frontend : 3300
- Backend API : 8300
- PostgreSQL : 5437
- Redis : 6383
- MinIO : 9004 / 9005 (console)

Deux reseaux :
- `fga-crm-internal` (interne aux services)
- `fga-network` (externe, partage avec Startup Radar pour la sync)

Le frontend utilise un volume anonyme pour `node_modules` (pas synce avec l'hote).

## Alternatives envisagees
- Dev sans Docker (services locaux) — rejetee parce que non reproductible, conflits de ports
- Kubernetes local (minikube) — rejetee parce que trop lourd pour un projet solo

## Consequences
- Apres ajout d'une dep npm : `docker exec fga-crm-frontend npm install <pkg>` ou rebuild container
- `docker compose restart` ne relit pas le `.env` → utiliser `docker compose up -d`
- Le reseau `fga-network` doit etre cree avant `docker compose up` (`docker network create fga-network`)
- `init_db()` fait `create_all` (pas d'Alembic en dev), donc pas d'ALTER TABLE automatique

## Fichiers impactes
- `docker-compose.yml` — configuration dev
- `docker-compose.vps.yml` — configuration production
- `backend/Dockerfile`, `frontend/Dockerfile`
- `Makefile` — commandes dev
