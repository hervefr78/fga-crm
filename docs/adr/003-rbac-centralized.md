# ADR-003 : RBAC centralise dans core/rbac.py

## Date
2026-02-22

## Statut
accepted

## Contexte
Le CRM a 3 roles (admin, manager, sales) avec des regles de visibilite differentes. Chaque entite a un champ d'ownership (`owner_id`, `assigned_to`, `user_id`). La logique de filtrage doit etre appliquee sur toutes les routes.

## Decision
Centraliser le RBAC dans `app/core/rbac.py` avec deux fonctions :
- `apply_ownership_filter(query, Model, user)` — filtre les queries selon le role
- `check_entity_access(entity, user)` — verifie l'acces a une entite specifique

Les roles sont derives de proprietes sur le model User :
- `user.is_admin` = role admin uniquement
- `user.is_manager` = admin OU manager (bypass RBAC)

## Alternatives envisagees
- Middleware FastAPI — rejetee parce que le filtrage depend du model ORM et de la query, pas accessible dans un middleware HTTP
- Decorateurs par route — rejetee parce que duplication, risque d'oubli sur une route
- Library externe (casbin) — rejetee parce que over-engineering pour 3 roles fixes

## Consequences
- Toute nouvelle route doit appeler `apply_ownership_filter` sur ses queries list
- Toute route detail/update/delete doit appeler `check_entity_access`
- Les ownership fields doivent etre documentes par entite (DC8)
- Un oubli = fuite de donnees entre users sales

## Fichiers impactes
- `backend/app/core/rbac.py` — logique centrale
- `backend/app/api/v1/*.py` — chaque route appelle les fonctions RBAC
- `backend/app/models/user.py` — proprietes `is_admin`, `is_manager`
