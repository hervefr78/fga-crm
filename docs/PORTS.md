# 🐳 Cartographie des ports Docker — Écosystème Coptos

> Dernière mise à jour : 22 février 2026

## Ports par application

| Application | Frontend | Backend | PostgreSQL | Redis | Autres |
|------------|----------|---------|------------|-------|--------|
| **Marketer** | 3000 | 8000 | 5433 | 6379 | 8001 (ChromaDB) |
| **Startup Radar** | 3100 | 8100 | 5434 | 6380 | — |
| **DevHub** | 3200 | 8200 | 5436 | 6382 | — |
| **QRCode BTP** | — | — | 5435 | 6381 | 9002/9003 (MinIO) |
| **Repro Estimator** | — | 6060 | 6262 | 7575 | — |
| **FGA CRM** | **3300** | **8300** | **5437** | **6383** | **9004/9005** (MinIO) |

## Plages réservées pour le futur

| Plage | Disponible pour |
|-------|----------------|
| 3400-3499 | Prochain frontend |
| 8400-8499 | Prochain backend |
| 5438-5439 | Prochaine DB PostgreSQL |
| 6384-6389 | Prochain Redis |
| 9006-9009 | Prochain MinIO |

## Réseau Docker partagé

```yaml
# Créer le réseau (une seule fois)
docker network create coptos-network

# Utilisé par : startup-radar, fga-crm (communication backend-to-backend)
```
