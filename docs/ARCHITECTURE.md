# Architecture FGA CRM — Technique & Fonctionnelle

> Date : 2026-07-03 · Version vivante (à mettre à jour à chaque évolution structurelle)
> Public : développeurs rejoignant le projet, revue d'architecture, onboarding IA.
> Source de vérité : le code (`backend/app/`, `frontend/src/`). Ce document en est le reflet vérifié.

---

## 1. Mission & vision

**FGA CRM** est le CRM interne de Fast Growth Advisor. Au-delà d'un CRM classique (contacts / sociétés / deals / tâches / activités), il agrège des **modules de croissance** propriétaires :

- **GEO** — mesure de visibilité de marque dans les moteurs génératifs (ChatGPT, etc.).
- **Trends** — détection de tendances marché (Google Trends via providers).
- **Enrichment** — enrichissement d'emails B2B RGPD-compliant (module *Compass*).
- **Startup Radar sync** — ingestion one-way d'un radar de startups externe.
- **Intégrations entrantes** — Nomo-IA et Plein Phare Digital poussent des événements business dans le CRM.

> Vision produit : FGA CRM est la **fondation du futur produit Compass** (CRM + Startup Radar + Plein Phare + NOMO-IA), destiné aux PME/ETI en mode SaaS multi-tenant.

---

## 2. Stack technique

| Couche | Technologie |
|--------|-------------|
| **Backend** | FastAPI · Python 3.12 · SQLAlchemy async · asyncpg |
| **DB** | PostgreSQL 16 (JSONB) |
| **Cache / broker** | Redis 7 |
| **Background** | Celery + Celery Beat |
| **Storage** | MinIO (S3-compatible) — *provisionné, pas encore actif dans le code* |
| **Auth** | JWT (python-jose) access+refresh · WebAuthn/passkeys (modèle présent, pas d'UI) |
| **Frontend** | React 18 · TypeScript · Vite · Tailwind CSS 3.4 · Lucide |
| **State** | React Context (auth) + TanStack Query v5 (data) |
| **HTTP client** | Axios (`api/client.ts`) |
| **Migrations** | Alembic (prod) · `create_all` (dev/test) |
| **Tests** | pytest + pytest-asyncio (SQLite in-memory) · Vitest + RTL |
| **Package mgmt** | Poetry (backend) · npm (frontend) |
| **Orchestration** | Docker Compose |

---

## 3. Topologie & déploiement

### 3.1 — Services (dev, `docker-compose.yml`)

| Service | Port | Rôle |
|---------|------|------|
| frontend | 3300 | Vite dev server |
| backend | 8300 | API FastAPI (uvicorn) |
| db | 5437 | PostgreSQL 16 |
| redis | 6383 | broker Celery + cache |
| worker | — | Celery worker (`RUN_MIGRATIONS=0`) |
| beat | — | Celery Beat (scheduler) |
| minio | — | stockage S3-compatible |

### 3.2 — Production (VPS `crm.fast-growth.fr`)

- Compose dédié **`docker-compose.vps.yml`** (réseaux `internal` + `caddy-net` external), reverse-proxy **Caddy** (TLS auto).
- Variables via **`.env.production`** (présent uniquement sur le VPS, jamais synchronisé).
- **Migrations** : `docker-entrypoint.sh` du backend lance `alembic upgrade head` au boot ; le worker passe `RUN_MIGRATIONS=0` pour éviter la race condition (seul le backend migre).
- **Déploiement** : rsync du repo → build → `docker compose up -d` (jamais scp/reset direct sur le VPS).

---

## 4. Architecture backend (couches)

```
backend/app/
├── main.py            # bootstrap FastAPI, CORS, include api_router (/api/v1)
├── config.py          # Settings pydantic-settings (BaseSettings)
├── api/v1/            # routes (21 fichiers, ~108 endpoints) → §7
│   └── router.py      # agrégation des sous-routers
├── models/            # 30 tables SQLAlchemy → §5
├── schemas/           # Pydantic (requêtes/réponses, séparés des routes)
├── services/          # logique métier (enrichment, geo, trends, startup_radar, email…)
├── tasks/             # tâches Celery (enrichment, geo, trends, funding, SR full sync)
├── core/              # deps (get_current_user), security (JWT), rbac (tenant + ownership)
├── db/                # session async, init_db
└── alembic/           # migrations (versions/)
```

**Flux d'une requête** : `route` (validation Pydantic + auth `Depends`) → `service` (métier) → `model` (SQLAlchemy async) → réponse `_entity_to_response()`.

### Patterns backend (conventions projet)

- Schémas Pydantic dans `schemas/` (jamais dans les routes) — bornage DC1 (`max_length`, caps de liste).
- Helper `_entity_to_response()` + `_parse_uuid()` **locaux à chaque fichier route** (DC8).
- **Dates** : Pydantic stocke en `str`, conversion `date.fromisoformat()` dans la route AVANT SQLAlchemy (ADR-001 — source de bugs récurrents).
- PATCH via `model_dump(exclude_unset=True)`.
- Pagination `page` + `size` (max 100) → `{items, total, page, size, pages}`.
- `get_current_user` vit dans `app.core.deps` (**pas** dans `security`).

---

## 5. Modèle de données (30 tables)

Groupées par domaine fonctionnel. Toutes les tables métier portent `organization_id` (isolation multi-tenant, §6.3).

### CRM core
| Table | Rôle | Ownership |
|-------|------|-----------|
| `organizations` | tenant racine | — |
| `users` | membres (rôle admin/manager/sales) | — |
| `contacts` | personnes | `owner_id` |
| `companies` | sociétés | `owner_id` |
| `deals` | opportunités (pipeline) | `owner_id` |
| `tasks` | tâches/relances | `assigned_to` |
| `activities` | journal (email/call/meeting/note/linkedin/task/audit) | `user_id` |
| `tags` / `tag_assignments` | étiquetage transverse | — |
| `email_templates` | modèles email (`{{variables}}`) | — |

### Auth
| Table | Rôle |
|-------|------|
| `api_keys` | clés API (MCP / intégrations, `crm_xxx`) |
| `webauthn_credentials` | passkeys (modèle présent, pas d'UI) |

### GEO (Generative Engine Optimization)
| Table | Rôle |
|-------|------|
| `geo_brands` | marques suivies |
| `geo_prompts` | prompts testés contre les moteurs |
| `geo_runs` | exécutions (1 prompt × N runs) |
| `geo_metrics_daily` | métriques agrégées / jour |
| `geo_audit_jobs` | jobs d'audit de visibilité (déclenchés via SR) |

### Trends
| Table | Rôle |
|-------|------|
| `trend_categories` / `trend_category_seeds` | taxonomie + termes-graines |
| `trend_jobs` | jobs de génération de rapport |
| `trend_reports` | rapports (signaux normalisés + summary) |
| `trend_keywords` / `trend_snapshots` | séries temporelles |

### Enrichment (Compass)
| Table | Rôle |
|-------|------|
| `enrichment_jobs` | jobs (modes company/batch/icp/contacts) |
| `enrichment_bulks` / `enrichment_bulk_items` | recherches par lot Icypeas |
| `enrichment_email_verifications` | résultats de vérif email |
| `enrichment_provenance` | traçabilité source d'un email |
| `enrichment_suppression` | liste de suppression (opt-out RGPD) |

### Observabilité
| Table | Rôle |
|-------|------|
| `mcp_tool_usage` | log d'usage des outils MCP (comptage tokens/coûts) |

---

## 6. Sécurité : auth, RBAC, multi-tenant

### 6.1 — Authentification
- **JWT** access + refresh (`/auth/login`, `/auth/refresh`). Endpoints : register, login, refresh, me, change-password.
- Premier user inscrit = **admin** ; les suivants = **sales**.
- **`AUTH_BYPASS=true`** en dev (auto-login premier admin).
- Clés API `crm_xxx` (table `api_keys`) pour MCP + intégrations entrantes (Bearer).

### 6.2 — RBAC (3 rôles, centralisé `core/rbac.py` — ADR-003)
| Rôle | Portée |
|------|--------|
| **admin** | tout + gestion users |
| **manager** | tout (lecture/écriture) |
| **sales** | uniquement ses entités (ownership) |

Helpers : `apply_ownership_filter()` + `check_entity_access()`.
Ownership : contacts/companies/deals → `owner_id` · tasks → `assigned_to` · activities → `user_id`.

### 6.3 — Isolation multi-tenant (branche `feat/multi-tenant-isolation`)
- `OrgScopedMixin` : `organization_id NOT NULL` sur toutes les tables métier.
- Contraintes UNIQUE composites `(org_id, X)`.
- Helpers `apply_tenant_filter()` / `check_tenant_access()` dans `core/rbac.py` (renvoie 404 cross-org).
- L'org vient **toujours du serveur** (token → user.organization_id), jamais du client (DC18).

---

## 7. Inventaire des endpoints (~108, préfixe `/api/v1`)

| Router | Préfixe | Nb | Domaine |
|--------|---------|---:|---------|
| auth | `/auth` | 6 | register, login, refresh, me, change-password |
| companies | `/companies` | 6 | CRUD sociétés |
| contacts | `/contacts` | 6 | CRUD contacts |
| deals | `/deals` | 7 | CRUD deals + pricing + stages |
| tasks | `/tasks` | 6 | CRUD tâches |
| activities | `/activities` | 5 | journal d'activités |
| search | `/search` | 1 | recherche transverse |
| users | `/users` | 6 | gestion membres (admin) + `/lookup` |
| organizations | `/organizations` | 2 | org courante |
| emails | `/emails` | 2 | envoi email (SMTP OVH) |
| email-templates | `/email-templates` | 5 | CRUD modèles |
| integrations | `/integrations` | 9 | SR sync + Nomo-IA + Plein Phare |
| dashboard | `/dashboard` | 2 | KPIs agrégés |
| drafts-review | `/drafts-review` | 4 | revue de brouillons |
| admin/api-keys | `/admin/api-keys` | 4 | clés API (admin) |
| geo | `/geo` | 18 | brands, prompts, runs, metrics |
| geo_audit | `/geo` | 2 | POST/GET `/audit-visibility` |
| trends | `/trends` | 6 | catégories, jobs, rapports, health |
| enrichment | `/enrichment` | 4 | jobs + `/companies/{siren}/enrich` |
| enrichment_webhook | `/integrations/icypeas` | 1 | `/webhook` (callback lot) |
| mcp-usage | `/mcp-usage` | 3 | agrégations usage MCP |
| ai | *(racine)* | 3 | `/{company\|contact\|deal}/…/next-action` |

---

## 8. Modules fonctionnels

### 8.1 — CRM core & pipeline commercial
Contacts, sociétés, deals, tâches, activités. Le **pipeline** est piloté par `DEAL_STAGES` :
`new → contacted → meeting → proposal → negotiation → won | lost`.
Pages front : Pipeline (kanban), Signed (won), Lost, DealDetail. Tâches typées (`todo/call/email/meeting`) avec priorités (`low/medium/high/urgent`).

### 8.2 — AI Next-Action (`ai.py`)
Pour une société / un contact / un deal, suggère la **prochaine action commerciale** via OpenAI (gpt-4o-mini). Agrège le contexte (dernière activité, audit GEO éventuel) et renvoie une recommandation. 3 endpoints `…/next-action`.

### 8.3 — GEO (Generative Engine Optimization)
Mesure la visibilité d'une **marque** dans les réponses de moteurs génératifs.
Flux : `brand` → `prompts` (questions cibles) → `runs` (N exécutions/prompt, `GEO_RUNS_PER_PROMPT`) → **extraction** (toujours gpt-4o-mini, structured output *strict*, T=0) des mentions/rang/sentiment → **scoring** → `geo_metrics_daily`.
`geo_audit` : audit de visibilité déclenchable (POST `/audit-visibility`), quota journalier (`GEO_AUDIT_DAILY_QUOTA`), dédup, scope `geo:audit`. Beat : `geo_compute_metrics_task` chaque jour à 07:00.

### 8.4 — Trends
Génère un **rapport de tendances** pour une catégorie/pays/langue/fenêtre temporelle.
**Factory de provider** (`services/trends/provider.py`) : DataForSEO si `dataforseo_login`+`password` configurés, sinon **MockProvider** (déployable sans clé, données déterministes). SerpApi/SearchApi disponibles en adapters. Résultat normalisé : `market_pulse`, `timeseries`, `rising/top_queries`, `related_topics`, `regions` + `summary_md` + `opportunity_score`. Cache Redis (TTL quick vs trending). Modes `quick` / `deep`.

### 8.5 — Enrichment (module Compass)
Enrichissement d'emails B2B **RGPD-first**. Architecture **hexagonale** (ports/adapters, `factory.py` swap selon config). 4 modes via `POST /enrichment/jobs` :

| Mode | Cible | Traitement |
|------|-------|-----------|
| `company` | 1 SIREN | inline, synchrone |
| `batch` | liste de SIREN | recherche par lot Icypeas + webhook |
| `icp` | filtre ICP (NAF, CA, actif…) | résolution → lot Icypeas + webhook |
| `contacts` (Feature B) | contacts CRM existants | enrichit/`reverify` les emails manquants ou existants |

Pipeline transverse : **waterfall** (cascade de sources) → **RGPD** (`classify_email` : personal/generic/pro — seuls les pro nominatifs passent) → **suppression** (opt-out) → **provenance** (traçabilité) → **credit_ledger** (quota `ENRICHMENT_DAILY_QUOTA`, `MAX_CREDITS_PER_RUN`) → **crm_writer** (upsert contact, flags « validé Icypeas »).
Source société configurable (`ENRICHMENT_COMPANY_SOURCE`). Callback lot : `POST /integrations/icypeas/webhook`. Réconciliation des lots orphelins : beat `enrichment_reconcile_bulks_task` (minute 15). Doc détaillée : [`ENRICHMENT_MODULE.md`](ENRICHMENT_MODULE.md).

### 8.6 — Startup Radar sync (ADR-004)
Sync **one-way** SR → CRM. Dédup via `startup_radar_id`. Service `startup_radar_sync.py` (fetch + mapping + upsert). Full sync : task Celery `startup_radar_full_sync.full_sync_task`. Sync incrémental via l'API `integrations`.

### 8.7 — Email, templates, drafts
Envoi SMTP async (OVH, aiosmtplib). Templates avec variables `{{first_name}}`, `{{company_name}}`… stockés et tracés en `Activity(type="email")`. « Drafts review » : file de brouillons à valider avant envoi.

### 8.8 — Intégrations entrantes (`integrations.py`)
Webhooks business poussés dans le CRM, authentifiés par Bearer `crm_xxx` :
- **Nomo-IA** : nouvel abonnement → crée contact/société/deal. *(fallback header `X-Nomo-API-Key` déprécié, à retirer — cf. code-health §D.)*
- **Plein Phare Digital** : nouvelle commande + remboursement → synchronise l'état commercial.

### 8.9 — MCP usage
Log et agrégation de l'usage des outils MCP (tokens, coûts) — table `mcp_tool_usage`, page front McpTokens (admin).

---

## 9. Frontend (React 18 + TS)

### 9.1 — Routes (`App.tsx`)
`/` Dashboard · `/contacts` + `/contacts/:id` · `/companies` + `/:id` · `/pipeline` + `/:id` · `/signed` · `/lost` · `/tasks` · `/activities` · `/drafts` · `/geo` · `/trends` · `/enrichment` · `/email` · `/settings`.
Protégées : `/integrations` (**ManagerRoute**) · `/admin/users`, `/mcp-tokens` (**AdminRoute**).

### 9.2 — Organisation
- Pages dans `pages/`, composants de domaine dans `components/<feature>/` (pattern d'extraction établi : `<Feature>Atoms.tsx`, `<feature>Utils.ts`, `<Feature>ReportView.tsx`, `<Feature>Modal.tsx`).
- Primitives UI dans `components/ui/` (barrel `index.ts`).
- Clients API : `api/client.ts` (axios central) + modules `drafts.ts`, `enrichment.ts`, `geo.ts`, `trends.ts`, `http.ts`.
- Data : TanStack Query v5 (`useQuery`/`useMutation` + `invalidateQueries`). Auth : React Context.
- **Charte visuelle** : [`UI_GUIDELINES.md`](../UI_GUIDELINES.md) — patterns DetailHeader, KpiStrip, AiCard, ActivityTimeline, SideCard, SplitView. Anti-patterns : pas de `font-bold`, pas de `shadow-md+`, pas de gradient/emoji, pas de stat inventée (`—` si absente).

---

## 10. Intégrations & providers externes

| Intégration | Variable(s) config | Usage | État |
|-------------|--------------------|----|------|
| OpenAI | `OPENAI_API_KEY`, `OPENAI_MODEL` | AI next-action + extraction GEO (gpt-4o-mini) | actif |
| Icypeas | `ICYPEAS_API_KEY/SECRET`, `ICYPEAS_WEBHOOK_URL` | enrichment (recherche + vérif + lot) | actif |
| DataForSEO | `DATAFORSEO_LOGIN/PASSWORD` | Trends (provider primaire) | actif si configuré, sinon mock |
| SerpApi / SearchApi | `SERPAPI_KEY` / `SEARCHAPI_KEY` | Trends (adapters alternatifs) | disponible |
| Gemini | `GEMINI_API_KEY` | GEO (reporté — quota free tier = 0) | inactif |
| OVH SMTP | `OVH_SMTP_HOST/PORT` | envoi email | actif |
| Nomo-IA | `NOMO_API_KEY` | webhook entrant abonnements | actif |
| Plein Phare | `PLEIN_PHARE_API_KEY` | webhook entrant commandes/remboursements | actif |
| LinkedIn | `LINKEDIN_CLIENT_SECRET` | (OAuth prévu) | partiel |
| MinIO | `MINIO_*` | stockage S3 | **provisionné, pas encore utilisé dans le code** |

> ⚠️ Piège documenté (mémoire projet) : **SerpApi ≠ SearchApi** (deux services distincts, deux clés).

---

## 11. Background jobs (Celery + Beat)

**Tasks** (`app/tasks/`) :
- `enrichment.*` : run des jobs d'enrichissement + `enrichment_reconcile_bulks_task`.
- `geo.*` : run audit, `geo_compute_metrics_task`, pipeline GEO.
- `trends.*` : génération de rapports.
- `startup_radar_full_sync.full_sync_task` : sync complet SR.
- `funding_sync.sync_recent_funding_task` : sync levées (beat commentable côté CRM).

**Beat schedule** (`app/tasks/celery_app.py`) :
| Task | Cadence |
|------|---------|
| `geo_compute_metrics_task` | quotidien 07:00 |
| `enrichment_reconcile_bulks_task` | chaque heure (minute 15) |

---

## 12. Tests, CI, migrations

### Tests
- Backend : pytest + pytest-asyncio, **SQLite in-memory** (mapping JSONB→JSON, ADR-002), `asyncio_mode=auto`, `follow_redirects=True`. **625 tests**.
- Frontend : Vitest + RTL. **65 tests** (11 fichiers).

### CI (`.github/workflows/ci.yml`)
- **Backend** : Poetry → ruff 0.15.0 → pytest (SQLite).
- **Frontend** : `npm ci` → `tsc --noEmit` → eslint → vitest. *(`npm ci` exige lockfile synchronisé avec package.json.)*

### Migrations (Alembic)
- **Prod** : `alembic upgrade head` au boot du backend (`docker-entrypoint.sh`). Worker : `RUN_MIGRATIONS=0`.
- **Dev/test** : `init_db()` fait `create_all` (pas d'ALTER). Voir CLAUDE.md → « Premiere migration vers Alembic en prod existante » pour le stamp baseline.

### Scores de référence (ne pas dégrader)
Ruff 0 · tsc 0 · ESLint 0 · Pytest 625 · Vitest 65.

---

## 13. Décisions d'architecture (ADR)

Tracées dans [`docs/adr/`](adr/) :
- **ADR-001** — dates en `str` Pydantic, conversion dans les routes.
- **ADR-002** — SQLite in-memory pour les tests (JSONB→JSON).
- **ADR-003** — RBAC centralisé dans `core/rbac.py`.
- **ADR-004** — sync one-way Startup Radar → CRM.
- **ADR-005** — Docker Compose dev (ports dédiés, réseaux).

---

## 14. Documents liés

- [`CODE_HEALTH_REPORT.md`](CODE_HEALTH_REPORT.md) — code mort + drift de taille + plan de refacto.
- [`ENRICHMENT_MODULE.md`](ENRICHMENT_MODULE.md) — flux de données détaillés du module d'enrichissement.
- [`../UI_GUIDELINES.md`](../UI_GUIDELINES.md) — charte visuelle & patterns front.
- [`../CLAUDE.md`](../CLAUDE.md) — conventions, protocole d'orchestration, règles DC.
