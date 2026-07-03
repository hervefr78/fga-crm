# CLAUDE.md — FGA CRM

## Projet

CRM interne Fast Growth Advisor. Full-stack : FastAPI async (Python 3.12) + React 18/TypeScript + PostgreSQL 16.
Docker Compose pour le dev. Ports : 3300 (front), 8300 (API), 5437 (DB), 6383 (Redis).

---

## Protocole d'orchestration obligatoire

### Principe

Pour tout changement non-trivial (> 5 lignes), Claude doit produire un **plan d'execution** AVANT de coder.
Ce plan est visible par l'utilisateur qui valide ou corrige avant execution.

### Sequence obligatoire

```
Intent → Plan → Execution → Validation → [Reparation] → Rapport
```

### Template de plan (a produire avant d'executer)

```markdown
## Plan : [titre court]

### Intention
[Ce qui doit etre fait et pourquoi]

### Classification
- [ ] Fix trivial (< 5 lignes) → pas de plan, executer directement
- [ ] Modification moyenne → ce plan suffit
- [ ] Changement structurel → design complet requis (voir workflow global CLAUDE.md)

### Agents a invoquer
| Ordre | Agent | Action |
|-------|-------|--------|
| 1 | repo-mapper | (si premiere session ou structure inconnue) |
| 2 | backend-architect | [ce qu'il doit faire] |
| 3 | frontend-integrator | [ce qu'il doit faire] |
| 4 | schema-guard | [verification contrats] |
| 5 | test-builder | [tests a creer] |
| 6 | quality-enforcer | validation globale |
| 7 | repair-agent | (si echec validation) |

(supprimer les lignes non pertinentes)

### Fichiers impactes
- [fichier] : [create / modify / delete]

### Risques
- [ce qui pourrait casser]

### Validations
- [ ] ruff check backend/app/
- [ ] tsc --noEmit (frontend)
- [ ] pytest tests/ -v
- [ ] vitest run
```

### Rapport de fin (a produire apres execution)

```markdown
## Rapport : [titre]

### Fichiers modifies
- [fichier] : [resume du changement]

### Validations
| Check | Statut |
|-------|--------|
| Ruff | pass/fail |
| tsc | pass/fail |
| Pytest | N/N pass |
| Vitest | N/N pass |

### Corrections appliquees
- [si repair-agent a ete invoque]

### Points a verifier manuellement
- [si applicable]
```

### Regles d'orchestration

1. **Ne jamais coder sans plan** pour les changements > 5 lignes
2. **Ne jamais livrer sans validation** — lancer les checks AVANT de dire "c'est bon"
3. **Separation stricte** — backend-architect ne touche pas le frontend, frontend-integrator ne touche pas le backend
4. **Max 3 boucles de reparation** — au-dela, escalade humaine
5. **Rapport obligatoire** — chaque tache se termine par un rapport structure

### Checklist de fin de tache (OBLIGATOIRE avant de rendre la main)

Avant de dire "c'est termine" ou "c'est bon" a l'utilisateur, verifier CHAQUE point :

- [ ] **Plan produit ?** — si changement > 5 lignes et pas de plan → le produire maintenant
- [ ] **Validation lancee ?** — si du code a ete modifie et pas de quality-enforcer → le lancer maintenant
- [ ] **Schema-guard lance ?** — si des modeles/schemas/types ont change → le lancer maintenant
- [ ] **Tests crees/mis a jour ?** — si feature ajoutee ou bug fixe sans test → signaler le manque
- [ ] **Rapport produit ?** — si pas de rapport structure → le produire maintenant
- [ ] **Fragilites adjacentes signalees ?** — si du code adjacent problematique a ete vu → le mentionner (DC17)

Si une etape manque, la faire AVANT de repondre. Ne JAMAIS dire "c'est termine" avec des etapes manquantes.

---

## Stack et architecture

### Backend (`/backend/app/`)
- **Framework** : FastAPI + SQLAlchemy async + asyncpg
- **Auth** : JWT (python-jose) + WebAuthn (passkeys, pas encore dans l'UI)
- **RBAC** : 3 roles (admin/manager/sales), centralise dans `core/rbac.py`
- **Email** : OVH SMTP async (aiosmtplib), templates avec variables `{{var}}`
- **Background** : Celery + Redis
- **Storage** : MinIO (S3-compatible)
- **Tests** : pytest + pytest-asyncio, SQLite in-memory (JSONB → JSON mapping)

### Frontend (`/frontend/src/`)
- **Framework** : React 18 + TypeScript + Vite
- **State** : React Context (auth) + TanStack Query v5 (data)
- **Style** : Tailwind CSS 3.4 + Lucide icons
- **HTTP** : Axios (`api/client.ts`)
- **Tests** : Vitest + React Testing Library

### Patterns du projet

#### Backend
- Schemas Pydantic dans `schemas/` (separes des routes), validation DC1
- Helper `_entity_to_response()` dans chaque fichier route (DC8)
- `_parse_uuid()` helper local dans chaque route
- `model_dump(exclude_unset=True)` pour les PATCH
- Dates : Pydantic stocke en `str`, conversion `date.fromisoformat()` dans la route AVANT passage a SQLAlchemy
- Pagination : `page` + `size` (max 100), reponse `{items, total, page, size}`
- RBAC : `apply_ownership_filter()` + `check_entity_access()` dans `core/rbac.py`
- `get_current_user` est dans `app.core.deps` (PAS dans `app.core.security`)

#### Frontend
- Composants UI dans `components/ui/` avec barrel export `index.ts`
- Modal + Form pattern : form recoit `entity?` (edit si present, create sinon)
- `useMutation` + `invalidateQueries` pour le CRUD
- Badge maps (TYPE_COLORS, etc.) au top du fichier page
- FilterBar.onChange signature : `(key, value)` pas `(values)`

#### UI Guidelines (OBLIGATOIRE pour tout travail frontend)
**Reference unique** : [`UI_GUIDELINES.md`](UI_GUIDELINES.md) a la racine du repo.
- TOUJOURS lire ce document avant de creer ou refactorer une page
- Charte visuelle, patterns recurrents (DetailHeader, KpiStrip, AiCard, ActivityTimeline, SideCard, SplitView), regles d'interaction, anti-patterns
- Checklist PR obligatoire en section 12 du document
- Toute deviation du guide doit etre justifiee dans la PR ET ajoutee au document si elle devient un nouveau pattern
- Stack : React 18 + TS + Tailwind 3.4 + Lucide + TanStack Query v5
- Anti-patterns critiques : pas de `font-bold` (700+), pas de `shadow-md+`, pas de gradient, pas d'emoji, pas de stat inventee (afficher `—` si absente)

#### Architecture modulaire (OBLIGATOIRE — voir DC21 global)
**Tout fichier applicatif reste sous ~400 lignes.** 500 = refacto obligatoire. Ne jamais laisser naître un fichier > 400 lignes.
- **Frontend** : extraire vers `components/<feature>/` → `<feature>Utils.ts`, `<Feature>Atoms.tsx`, `<Feature>XxxPanel.tsx`, `<Feature>Modal.tsx`. La page = hooks + layout + assemblage.
- **Backend** : routes → 1 router/sous-ressource agrégés dans `__init__.py` ; services → couches (client/mapper/orchestrator) ou handlers par mode dans `modes/`.
- Iso-comportement strict, 1 refacto = 1 PR (≤ 5 fichiers, DC15). Plan de refacto en cours : [`docs/CODE_HEALTH_REPORT.md`](docs/CODE_HEALTH_REPORT.md) (C1→C5). Pattern validé : Trends.tsx 547→209, GEO.tsx 1031→633.

---

## Regles specifiques a ce projet

### Dates (CRITIQUE — source de bugs recurrents)
- Les schemas Pydantic definissent les dates comme `str`
- Les models SQLAlchemy attendent `date` ou `datetime` natifs
- TOUJOURS convertir avec `date.fromisoformat()` / `datetime.fromisoformat()` dans la route
- Verifier TOUS les champs date d'un schema lors d'une modification

### Docker
- Apres ajout d'une dep dans `package.json` : `docker exec <container> npm install <pkg>` ou rebuild
- `docker compose restart` ne relit PAS le `.env` → utiliser `docker compose up -d <service>`
- En dev/test, `init_db()` fait `create_all` (pas d'ALTER sur tables existantes — voir section "Migrations Alembic")
- En production (`APP_ENV=production`), `init_db()` est no-op : les migrations sont gerees par Alembic (lance par `docker-entrypoint.sh`)
- Reseau `fga-network` (external) doit etre cree avant `docker compose up`

### Tests
- `follow_redirects=True` obligatoire dans httpx AsyncClient (conftest)
- JSONB → JSON mapping dans conftest pour SQLite
- `asyncio_mode = "auto"` dans pytest config
- `AUTH_BYPASS=true` dans `.env` pour dev (premier admin auto-login)

### Composants UI
- TOUJOURS lire le composant avant de l'utiliser (verifier props exactes)
- Utiliser `<select>` natif au lieu du composant `Select` pour children/options dynamiques
- `react-doctor --yes` pour skip les prompts interactifs

---

## Migrations Alembic

Alembic gere le schema en production. En dev/test, `init_db()` continue de faire `create_all` (plus rapide, evite de runner alembic a chaque test).

### Workflow

```bash
# Creer une migration apres modification d'un model
docker exec -it fga-crm-backend alembic revision --autogenerate -m "ajout_champ_xyz"

# Appliquer les migrations (lance automatiquement au boot du backend)
docker exec -it fga-crm-backend alembic upgrade head

# Verifier l'etat courant
docker exec -it fga-crm-backend alembic current

# Rollback de la derniere migration
docker exec -it fga-crm-backend alembic downgrade -1

# Historique
docker exec -it fga-crm-backend alembic history
```

### Notes

- Les migrations sont stockees dans `backend/alembic/versions/`
- En prod, `alembic upgrade head` est lance automatiquement au boot du backend via `backend/docker-entrypoint.sh`
- Le worker Celery passe `RUN_MIGRATIONS=0` pour eviter la race condition au boot — seul le backend applique les migrations
- En dev local, `init_db()` (au boot de FastAPI) fait toujours `create_all` (compat retro, schemas sont alignes)
- TOUJOURS relire la migration generee par `--autogenerate` avant de l'appliquer (DC10 : verifier les noms de champs)
- Le script SQL `backend/scripts/migrations/2026-04-30_deal_pricing.sql` reste comme bridge pour les envs prod existants qui n'avaient pas encore Alembic — voir "Premiere migration vers Alembic en prod existante"

### Premiere migration vers Alembic en prod existante

Pour une DB de prod existante (deja en place avant Alembic, sans la table `alembic_version`) :

```bash
# 1. Appliquer manuellement le SQL pricing (si pas encore applique)
docker exec -i fga-crm-db psql -U fga_crm -d fga_crm < backend/scripts/migrations/2026-04-30_deal_pricing.sql

# 2. Verifier qu'aucune table n'est manquante par rapport au baseline
#    (le schema doit matcher app/models/*.py exactement)

# 3. Marquer le schema comme aligne sur la migration baseline
#    (CREE la table alembic_version et la marque a la revision baseline)
docker exec -it fga-crm-backend alembic stamp head

# 4. A partir de la, toutes les futures migrations sont gerees normalement
docker exec -it fga-crm-backend alembic current  # doit afficher la revision baseline
```

Pour une DB neuve (deploiement from scratch), aucune action speciale : le `docker-entrypoint.sh` applique baseline + futures migrations automatiquement au premier boot.

---

## Validation obligatoire (ordre d'execution)

### Phase 1 — Apres chaque changement
```bash
# Backend
cd backend && ruff check app/

# Frontend
cd frontend && npx tsc --noEmit
cd frontend && npx eslint src/ --ext ts,tsx
```

### Phase 2 — Avant commit
```bash
# Tests
cd backend && python -m pytest tests/ -v
cd frontend && npx vitest run

# React quality
cd frontend && npx -y react-doctor@latest . --verbose --yes
```

### Scores de reference (ne pas degrader)
- Ruff : 0 errors
- tsc : 0 errors
- ESLint : 0 errors
- Pytest : 155/155
- Vitest : 15/15
- react-doctor : 99/100

---

## Domain

- **DEAL_STAGES** : new, contacted, meeting, proposal, negotiation, won, lost
- **TASK_TYPES** : todo, call, email, meeting
- **TASK_PRIORITIES** : low, medium, high, urgent
- **ACTIVITY_TYPES** : email, call, meeting, note, linkedin, task, audit
- **RBAC** : admin voit tout + manage users, manager voit tout, sales voit ses entites
- **Ownership** : contacts/companies/deals → `owner_id`, tasks → `assigned_to`, activities → `user_id`
- **Registration** : premier user = admin, suivants = sales
- **Startup Radar** : sync one-way SR → CRM via `startup_radar_id` (dedup)
- **Email templates** : variables `{{first_name}}`, `{{company_name}}`, etc. Stockees Activity(type="email")

---

---

## ADR (Architecture Decision Records)

Les decisions d'architecture sont tracees dans `docs/adr/`. Avant de modifier un pattern existant, verifier s'il y a un ADR qui explique pourquoi ce choix a ete fait.

- [ADR-001](docs/adr/001-dates-string-pydantic.md) — Dates en string dans Pydantic, conversion dans les routes
- [ADR-002](docs/adr/002-sqlite-tests.md) — SQLite in-memory pour les tests (mapping JSONB → JSON)
- [ADR-003](docs/adr/003-rbac-centralized.md) — RBAC centralise dans core/rbac.py
- [ADR-004](docs/adr/004-startup-radar-sync.md) — Sync one-way Startup Radar → CRM
- [ADR-005](docs/adr/005-docker-compose-dev.md) — Docker Compose pour le dev local (ports dedies, reseaux)

Template pour nouveaux ADR : `docs/adr/000-template.md`

---

## Hooks automatiques

Configures dans `.claude/settings.local.json` :
- **Edit/Write sur `.py`** → `ruff check` automatique sur le fichier
- **Edit/Write sur `.ts/.tsx`** → `tsc --noEmit` automatique

Ces hooks se declenchent sans intervention. Si une erreur est detectee, la corriger avant de continuer.

---

## Commentaires en francais pour ce projet.
