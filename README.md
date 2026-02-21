# 🚀 FGA CRM — Fast Growth Advisor CRM

> CRM léger, moderne et modulable pour les équipes commerciales B2B.
> Conçu par **Fast Growth Advisors** — Stack alignée sur Startup Radar & Nomoia.

![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat&logo=docker&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=flat&logo=tailwind-css&logoColor=white)

---

## 📋 Présentation

FGA CRM est un CRM B2B léger qui ne cherche pas à remplacer Salesforce ou Zoho. L'objectif : **efficacité, modernité, modularité**. Chaque fonctionnalité fait gagner du temps, pas en perdre.

### Principes

- **Efficacité > Exhaustivité** — Pas d'usine à gaz
- **Modulable** — Modules activables/désactivables
- **IA-first** — Claude + ChatGPT intégrés nativement
- **Self-hosted** — Docker Compose, même infra que Startup Radar
- **Sécurisé** — Auth WebAuthn/JWT, RBAC, chiffrement

---

## 🏗️ Stack technique

| Couche | Technologie |
|--------|------------|
| **Backend** | FastAPI (Python 3.12+), SQLAlchemy 2.x async, Alembic |
| **Frontend** | React 18 + TypeScript, Vite, TanStack Query |
| **UI** | Tailwind CSS, Lucide Icons, Recharts |
| **Database** | PostgreSQL 16, Redis 7 |
| **Task Queue** | Celery + Redis |
| **Auth** | JWT + WebAuthn (Passkeys/Touch ID) |
| **IA** | Claude (Anthropic) + ChatGPT (OpenAI) |
| **Email** | OVH SMTP/IMAP |
| **Fichiers** | MinIO (S3-compatible) |
| **Container** | Docker Compose |

---

## 🧩 Modules

| Module | Description |
|--------|------------|
| 📊 **Dashboard** | KPIs, pipeline funnel, activités récentes, tâches du jour |
| 👥 **Contacts & Companies** | Gestion complète avec filtres, tags, champs custom, déduplication |
| 🎯 **Pipeline (Kanban)** | Pipeline visuel drag & drop, stages configurables, forecasting |
| 📝 **Activités & Tâches** | Tracking complet (emails, appels, meetings, notes, LinkedIn) |
| ✉️ **Email (OVH)** | Envoi/réception, templates, variables, tracking |
| 🔗 **LinkedIn** | Extension Chrome, imports Evaboot, enrichissement profils |
| 🤖 **IA** | Enrichissement, scoring, génération email, résumé de compte |
| 📧 **Marketing Automation** | Séquences email, conditions, throttling, analytics |
| 📅 **Calendrier** | Google Calendar + CalDAV OVH, booking links |
| 📁 **Fichiers** | Upload, preview, versionning, MinIO storage |
| 🔄 **Startup Radar** | Import leads, sync contacts CxO, enrichissement croisé |

---

## 🐳 Quick Start

```bash
# Cloner le repo
git clone git@github.com:hervefr78/fga-crm.git
cd fga-crm

# Copier la config
cp .env.example .env
# Éditer .env avec vos clés API

# Lancer en développement
make dev

# Ou directement avec Docker Compose
docker compose up -d
```

### Ports (sans conflit avec les autres apps)

| Service | Port |
|---------|------|
| Frontend | `3200` |
| Backend API | `8200` |
| PostgreSQL | `5436` |
| Redis | `6382` |

---

## 📁 Structure du projet

```
fga-crm/
├── docker-compose.yml          # Dev config
├── docker-compose.prod.yml     # Production config
├── .env.example                # Variables d'environnement
├── Makefile                    # Commandes utiles
├── nginx/                      # Reverse proxy config
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── app/
│       ├── main.py             # FastAPI entry point
│       ├── config.py           # Settings (pydantic-settings)
│       ├── core/               # Security, permissions, utils
│       ├── models/             # SQLAlchemy models
│       ├── schemas/            # Pydantic schemas
│       ├── api/v1/             # Route handlers
│       ├── services/           # Business logic
│       ├── integrations/       # LinkedIn, OVH, AI, Calendar
│       ├── automation/         # Marketing automation engine
│       ├── tasks/              # Celery async tasks
│       └── db/                 # Session, migrations
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── components/         # UI components
│       ├── pages/              # Route pages
│       ├── hooks/              # Custom hooks
│       ├── api/                # API clients
│       ├── contexts/           # Auth, Theme
│       └── types/              # TypeScript interfaces
├── scripts/                    # Init, backup, seed
└── docs/                       # Specs & documentation
```

---

## 🔐 Sécurité

- **Auth** : JWT (access + refresh tokens) + WebAuthn (Passkeys/Touch ID)
- **RBAC** : Admin, Manager, Sales, Viewer
- **Chiffrement** : AES-256 (Fernet) pour les données sensibles, HTTPS (Let's Encrypt)
- **RGPD** : Droit à l'oubli, export des données, consentement tracking
- **Audit** : Logs de toutes les actions CRUD sensibles

---

## 🔗 Intégrations

- **Startup Radar** — Import leads, sync bidirectionnelle, enrichissement croisé (réseau Docker partagé)
- **LinkedIn** — Extension Chrome + imports CSV (Evaboot/PhantomBuster)
- **OVH Email** — SMTP (envoi) + IMAP (réception)
- **Claude & ChatGPT** — Enrichissement, scoring, génération, analyse de sentiment
- **Google Calendar** — Sync bidirectionnelle, booking links
- **OVH Calendar** — CalDAV fallback

---

## 📄 Documentation

Le document de spécifications complet est disponible dans `docs/fga-crm-specs.docx`.

---

*Fast Growth Advisors — 2026*
