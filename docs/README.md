# 📋 Documentation FGA CRM

## Documents disponibles

| Document | Description |
|----------|------------|
| `fga-crm-specs.docx` | Spécifications complètes (architecture, data model, API, UI, sécurité, roadmap) |
| `PORTS.md` | Cartographie des ports Docker de tout l'écosystème Coptos |

## Résumé des specs

**FGA CRM** — Fast Growth Advisors CRM Light

- **Stack** : FastAPI + React/TypeScript + PostgreSQL + Redis + Docker (alignée Startup Radar)
- **Ports** : Frontend 3300 / API 8300 / PostgreSQL 5437 / Redis 6383 / MinIO 9004-9005
- **12 modules** : Dashboard, Contacts, Companies, Pipeline Kanban, Activités, Tâches, Email OVH, LinkedIn (API dev + Chrome ext), IA (Claude+GPT), Marketing Automation, Calendar, File Manager
- **Intégrations** : Startup Radar (réseau Docker), LinkedIn (compte développeur), OVH (email+calendar), Google Calendar, Claude + ChatGPT
- **UI** : Thème clair par défaut (plus lumineux que Startup Radar), dark mode disponible, icônes SVG (Lucide)
- **Sécurité** : JWT + WebAuthn, RBAC (Admin/Manager/Sales/Viewer), chiffrement AES-256, RGPD
