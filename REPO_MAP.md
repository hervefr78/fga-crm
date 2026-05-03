# REPO_MAP.md — FGA CRM

> Derniere mise a jour : 2026-04-01
> Generee par : project-bootstrap agent

---

## Stack detecte

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Backend | Python 3.12, FastAPI, SQLAlchemy async, asyncpg | FastAPI ^0.109, SQLAlchemy ^2.0.25 |
| Frontend | React 18, TypeScript, Vite | React ^18.3.1, Vite ^7.3.1 |
| Base de donnees | PostgreSQL 16 (Alpine) | pg16 |
| Cache / Broker | Redis 7 (Alpine) | redis:7-alpine |
| Storage | MinIO (S3-compatible) | latest |
| Background tasks | Celery + Redis | Celery ^5.3.6 |
| Tests backend | pytest + pytest-asyncio (SQLite in-memory) | pytest ^7.4.4 |
| Tests frontend | Vitest + React Testing Library | Vitest ^4.0.18 |
| Lint backend | Ruff | ^0.15.0 |
| Lint frontend | ESLint + TypeScript | ESLint ^8.57 |
| Style | Tailwind CSS 3.4 + Lucide icons | |
| State management | React Context (auth) + TanStack Query v5 (data) | |
| HTTP client | Axios (frontend), httpx (backend services) | |
| Auth | JWT (python-jose) + WebAuthn (backend only) | |
| AI | Anthropic Claude + OpenAI (optionnel) | |
| Email | OVH SMTP async (aiosmtplib) | |
| Containerisation | Docker Compose | |

---

## Arborescence cle

```
fga-crm/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Routes FastAPI (12 modules)
│   │   ├── core/            # Auth deps, security, RBAC
│   │   ├── db/              # Session async SQLAlchemy
│   │   ├── models/          # 9 models SQLAlchemy
│   │   ├── schemas/         # Pydantic schemas (11 modules)
│   │   ├── services/        # Email, Startup Radar client + sync
│   │   ├── integrations/    # (vide, package init)
│   │   ├── automation/      # (vide, package init)
│   │   ├── tasks/           # Celery app + workers
│   │   ├── config.py        # pydantic-settings (env vars)
│   │   └── main.py          # FastAPI app factory + lifespan
│   ├── tests/
│   │   ├── api/             # 12 fichiers tests API
│   │   ├── unit/            # 3 fichiers tests unitaires
│   │   └── conftest.py      # Fixtures DB (SQLite), JSONB mapping
│   ├── pyproject.toml       # Poetry deps + ruff + pytest config
│   ├── Dockerfile
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── api/             # client.ts (fonctions API), http.ts (Axios)
│   │   ├── components/
│   │   │   ├── ui/          # 14 composants generiques
│   │   │   ├── activities/  # ActivityForm
│   │   │   ├── audit/       # AuditResultPanel
│   │   │   ├── companies/   # CompanyForm
│   │   │   ├── contacts/    # ContactForm
│   │   │   ├── dashboard/   # KpiCard, PipelineChart, ActivityChart, TaskProgress
│   │   │   ├── email/       # ComposeModal, TemplateForm
│   │   │   ├── import/      # CsvImportModal
│   │   │   ├── layout/      # Layout, GlobalSearch
│   │   │   ├── pipeline/    # DealForm, KanbanBoard, KanbanCard
│   │   │   └── tasks/       # TaskForm
│   │   ├── contexts/        # AuthContext
│   │   ├── hooks/           # useDebounce
│   │   ├── pages/           # 13 pages
│   │   ├── types/           # index.ts (interfaces + constantes)
│   │   ├── utils/           # csv.ts (export CSV)
│   │   └── test/            # setup.ts (vitest)
│   ├── package.json
│   ├── vite.config.ts / vitest.config.ts / tsconfig.json
│   └── Dockerfile
├── docs/
│   ├── adr/                 # 4 ADR + template
│   ├── PORTS.md
│   └── README.md
├── docker-compose.yml       # Dev : db, redis, minio, backend, worker, frontend
├── docker-compose.sonar.yml # SonarQube
├── docker-compose.vps.yml   # Production VPS
├── Makefile                 # Commandes dev
├── CLAUDE.md
├── .claude/settings.local.json
└── .claude/napkin.md
```

---

## Carte backend

### Routes API (/api/v1/)

| Prefix | Module | Endpoints | Auth |
|--------|--------|-----------|------|
| /auth | auth.py | login, register, me, change-password | Public (login/register), JWT (reste) |
| /contacts | contacts.py | CRUD + import CSV + filtres | JWT + RBAC |
| /companies | companies.py | CRUD + import CSV + filtres + audit flags | JWT + RBAC |
| /deals | deals.py | CRUD + PATCH stage + filtres | JWT + RBAC |
| /tasks | tasks.py | CRUD + PATCH complete + filtres (overdue) | JWT + RBAC |
| /activities | activities.py | CRUD + filtres par contact/company/deal | JWT + RBAC |
| /search | search.py | Recherche globale (contacts, companies, deals) | JWT |
| /users | users.py | List users, PATCH role, PATCH deactivate | JWT + Admin only |
| /emails | emails.py | Send email, list sent | JWT |
| /email-templates | email_templates.py | CRUD templates | JWT + RBAC |
| /integrations | integrations.py | Sync SR, status, audit company | JWT |
| /dashboard | dashboard.py | Stats agregees (10+ queries) | JWT + RBAC |

### Models SQLAlchemy

| Model | Ownership field | Relations cle |
|-------|-----------------|---------------|
| User | — | owns contacts, companies, deals, tasks |
| Company | owner_id | has contacts, deals, activities |
| Contact | owner_id | belongs to company, has deals, tasks, activities |
| Deal | owner_id | belongs to company + contact |
| Task | assigned_to | belongs to contact, deal |
| Activity | user_id | belongs to contact, company, deal |
| EmailTemplate | owner_id | — |
| Tag | — | M2M via TagAssignment |
| WebAuthnCredential | user_id | belongs to User |

### Schemas Pydantic (11 modules)

common, company, contact, deal, task, activity, user, email, dashboard, integration, search, import_export

### Services

| Service | Fichier | Role |
|---------|---------|------|
| Email | services/email.py | Envoi SMTP async (OVH), template variable resolution |
| SR Client | services/startup_radar.py | Client HTTP vers API Startup Radar (JWT auth) |
| SR Sync | services/startup_radar_sync.py | Sync SR → CRM (dedup, mapping, savepoints) |

### Core

| Module | Role |
|--------|------|
| core/deps.py | get_current_user, get_current_admin (FastAPI Depends) |
| core/security.py | JWT encode/decode, password hashing |
| core/rbac.py | apply_ownership_filter(), check_entity_access() |
| config.py | pydantic-settings, toutes les env vars |
| db/session.py | AsyncSession factory, init_db (create_all), close_db |

---

## Carte frontend

### Pages (13)

| Route | Page | Fonctionnalites |
|-------|------|-----------------|
| / | Dashboard | KPI cards, pipeline chart, activity chart, task progress |
| /contacts | Contacts | Liste paginee, filtres, import/export CSV |
| /contacts/:id | ContactDetail | Fiche detail, activites, deals, tasks, compose email |
| /companies | Companies | Liste paginee, filtres, import CSV |
| /companies/:id | CompanyDetail | Fiche, contacts, deals, activites, onglet Audit SR |
| /pipeline | Pipeline | Kanban board (DnD), formulaire deal |
| /pipeline/:id | DealDetail | Fiche deal detail |
| /tasks | Tasks | Liste, filtres (type, priority, overdue), toggle complete |
| /activities | Activities | Liste paginee, filtres par type |
| /email | Email | Tabs envoyes/templates, compose modal, CRUD templates |
| /integrations | Integrations | Sync Startup Radar, stat cards |
| /settings | Settings | Profil, changement mot de passe |
| /admin/users | AdminUsers | Gestion users — admin only |
| /login | Login | Formulaire login/register |

### Composants UI generiques (14)

Badge, Button, ConfirmDialog, EmptyState, FilterBar, Input, LoadingSpinner, Modal, Pagination, SearchInput, Select, Tabs, Textarea + barrel export index.ts

### Pattern d'appel API

```
Page → api/client.ts → api/http.ts (Axios + JWT interceptor) → Backend /api/v1/*
```

### State management

- Auth : AuthContext (login, logout, user, isAuthenticated)
- Data : TanStack Query v5 (useQuery, useMutation, invalidateQueries)
- Pas de store global (Redux, Zustand)

---

## Carte tests

### Backend (155 declares, 153 passent — 2 echecs sur test_filters)

| Fichier | Couverture |
|---------|------------|
| test_health.py | Health endpoint |
| test_auth.py | Login, register, me, change-password |
| test_registration.py | Premier user admin, suivants sales |
| test_filters.py | Filtres contacts, companies, deals, tasks (2 FAIL) |
| test_import.py | Import CSV contacts, companies |
| test_rbac.py | RBAC 3 roles, ownership filtering |
| test_search.py | Recherche globale |
| test_tasks.py | CRUD tasks, toggle, overdue |
| test_users.py | Admin user management |
| test_email_templates.py | CRUD templates |
| test_emails.py | Send email, list sent |
| test_activities.py | CRUD activities |
| test_email_service.py | Service SMTP (unit, mock) |
| test_schemas.py | Validation Pydantic |
| test_security.py | JWT encode/decode |

### Frontend (15 tests — 2 fichiers seulement)

| Fichier | Couverture |
|---------|------------|
| Badge.test.tsx | Composant Badge (7 tests) |
| Button.test.tsx | Composant Button (8 tests) |

**Risque** : couverture frontend tres faible (2 composants UI, 0 pages, 0 integration API)

---

## Contrats partages (backend <-> frontend)

| Entite | Backend schema | Frontend type | Champs sensibles |
|--------|----------------|---------------|------------------|
| Contact | ContactResponse | Contact | email_status, lead_score, source, owner_name |
| Company | CompanyResponse | Company | startup_radar_id, has_audit_*, audit_score |
| Deal | DealResponse | Deal | stage, priority, expected_close_date |
| Task | TaskResponse | Task | type, priority, is_completed, due_date |
| Activity | ActivityResponse | Activity | type, metadata_ |
| User | UserResponse | User | role, is_active |
| EmailTemplate | EmailTemplateResponse | EmailTemplate | variables (string[]) |
| Dashboard | DashboardStats | DashboardStats | champs agreges |
| Pagination | {items, total, page, size} | PaginatedResponse<T> | pages (calcule frontend) |

---

## Flux transverses

### Flux CRUD standard (ex: Contact)
```
ContactsPage → getContacts(params) → GET /api/v1/contacts
  → contacts.py → apply_ownership_filter → SQLAlchemy → PostgreSQL
  → ContactListResponse {items, total, page, size}
```

### Flux Email
```
ComposeModal → sendEmail(data) → POST /api/v1/emails/send
  → emails.py → resolve template vars → email service (aiosmtplib → OVH)
  → Create Activity(type="email") + metadata_
```

### Flux Startup Radar Sync
```
IntegrationsPage → POST /integrations/startup-radar/sync
  → startup_radar_sync.py → SR client (login JWT, fetch data)
  → Mapping → Companies, Contacts, Activities (dedup startup_radar_id)
  → Savepoints (begin_nested) par iteration
```

---

## Notes pour les agents

### Pieges connus
1. **Dates** : Pydantic str → SQLAlchemy date — convertir avec fromisoformat() dans la route (ADR-001)
2. **JSONB SQLite** : mapper JSONB → JSON dans conftest (ADR-002)
3. **get_current_user** : dans app.core.deps, PAS app.core.security
4. **Docker node_modules** : volume anonyme — docker exec npm install apres ajout dep
5. **docker compose restart** ne relit pas le .env — utiliser docker compose up -d
6. **init_db create_all** : pas d'ALTER TABLE — colonnes manuellement ou Alembic
7. **Kanban size** : frontend size=200, backend cap 100
8. **FilterBar.onChange** : signature (key, value) pas (values)

### Conventions
- Commentaires en francais
- Schemas separes des routes (dans schemas/)
- Helper _entity_to_response() dans chaque fichier route
- Helper _parse_uuid() local dans chaque fichier route
- model_dump(exclude_unset=True) pour PATCH
- Badge maps au top des fichiers pages
- select natif pour dropdowns dynamiques (pas le composant Select)
