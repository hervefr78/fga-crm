# Déploiement 2026-05-11 — Funding Sync Multi-source

**Feature** : Intégration funding multi-source Startup Radar → FGA CRM
**Branche** : `feature/funding-sync-multi-source`
**Phase** : B + C (côté CRM)
**Dépendance amont** : Phase A SR (en cours côté `startup-radar` repo)

---

## 1. Résumé

Étend le sync Startup Radar pour absorber le nouveau pipeline funding multi-source (LesPepitesTech, Maddyness, Eldorado, L'Usine Digitale, BODACC) avec enrichissement Pappers (SIREN, fondateurs, emails heuristiques).

**Côté CRM, aucun scraping** — on consomme uniquement l'API SR via le sync existant qu'on étend.

Ce que ça ajoute concrètement :
- 5 nouveaux champs `Company` (siren, funding_date, funding_amount, funding_series, funding_sources)
- 3 nouveaux champs `Contact` (enrichment_source, email_pattern_used, linkedin_url_status)
- 1 nouveau champ `Task` (company_id — permet d'attacher une task à une company sans contact)
- Auto-création d'`Activity` "Levée détectée" + `Task` "Qualifier la levée" pour chaque nouvelle levée
- Cron quotidien 09:00 (Europe/Paris) : sync incrémentale via `/startups?since=`
- UI : bloc Funding sur fiche company, badges Email/LinkedIn sur fiche contact, KPI Dashboard "Levées 7j", 3 nouveaux filtres sur la liste companies

---

## 2. Schéma DB

### Migration Alembic : `a3f8c1d92e4b_funding_sync`

```bash
# En prod, lancée automatiquement au boot du backend (docker-entrypoint.sh)
alembic upgrade head
```

**Changements** :

| Table | Colonne | Type | Index | Nullable |
|---|---|---|---|---|
| `companies` | `siren` | VARCHAR(9) | oui | oui |
| `companies` | `funding_date` | DATE | oui | oui |
| `companies` | `funding_amount` | BIGINT | oui | oui |
| `companies` | `funding_series` | VARCHAR(50) | non | oui |
| `companies` | `funding_sources` | JSONB | non | oui |
| `contacts` | `enrichment_source` | VARCHAR(50) | non | oui |
| `contacts` | `email_pattern_used` | VARCHAR(50) | non | oui |
| `contacts` | `linkedin_url_status` | VARCHAR(20) | non | oui |
| `tasks` | `company_id` | UUID FK | oui | oui (ON DELETE SET NULL) |

**Rollback** : `alembic downgrade daa19e2fefdb` (drop des 9 colonnes + index + FK).

---

## 3. Endpoints API

### Nouveaux

| Méthode | URL | Description |
|---|---|---|
| `POST` | `/api/v1/integrations/startup-radar/sync-recent-funding?days_back=N` | Sync incrémentale. `days_back` borné 1-90, défaut 7. |

### Étendus (rétrocompatibles, champs additionnels)

- `GET /api/v1/companies` : ajout des query params `funding_series`, `funding_amount_min` (€), `funding_date_after` (ISO YYYY-MM-DD).
- `GET /api/v1/companies/{id}` et `GET /api/v1/companies` : `CompanyResponse` expose `siren`, `funding_date`, `funding_amount`, `funding_series`, `funding_sources`.
- `GET /api/v1/contacts/{id}` et `GET /api/v1/contacts` : `ContactResponse` expose `enrichment_source`, `email_pattern_used`, `linkedin_url_status`.
- `GET /api/v1/tasks` : query param `company_id` accepté, `TaskResponse` expose `company_id`.
- `GET /api/v1/dashboard/stats` : `DashboardStats` expose `recent_funding_count` (7 derniers jours) et `recent_funding_amount`.
- `POST /api/v1/integrations/startup-radar/sync` (full sync existant) : `SyncResultResponse` expose `funding_activities_created` et `qualification_tasks_created`.

---

## 4. Stack Celery beat (nouvelle)

**Nouveau container** : `fga-crm-beat` (Celery beat scheduler, distinct du worker existant).

**Task périodique** :

| Task | Cron | Action |
|---|---|---|
| `app.tasks.funding_sync.sync_recent_funding_task` | **09:00 quotidien** (Europe/Paris) | Pull startups SR modifiées les 7 derniers jours, crée Activity "Levée détectée" + Task "Qualification" |

C'est **le seul cron actif** côté CRM (avant cette feature, aucun cron n'existait).

**Déploiement** :
```bash
cd /home/ubuntu/fga-crm
docker compose -f docker-compose.vps.yml build backend beat
docker compose -f docker-compose.vps.yml up -d backend beat worker frontend
```

Le worker existant **doit aussi être recréé** (nouvelle task `funding_sync` à enregistrer).

---

## 5. Variables d'environnement

**Aucune nouvelle variable requise.** Le sync réutilise :
- `STARTUP_RADAR_EMAIL`, `STARTUP_RADAR_PASSWORD` (déjà configurés)
- `REDIS_URL`, `DATABASE_URL` (déjà configurés)

Le `beat` container hérite des mêmes `.env.production` que le worker.

---

## 6. Idempotence

| Entité | Clé d'idempotence | Comportement |
|---|---|---|
| `Activity` (funding_detected) | `(company_id, type, subject incluant montant+série)` | Un round = un Activity. Round suivant = nouveau subject = nouveau Activity. |
| `Task` (qualification) | `(company_id, type='qualification', is_completed=False)` | Une seule task ouverte à la fois. Si complétée, une nouvelle peut être créée plus tard (nouveau round). |
| `Company.funding_*` | Update additif | Garde le montant le plus élevé, merge les `funding_sources` (set union), préserve les autres champs sur première valeur. |
| `Contact.email_pattern_used` | Préservé sur update | Première valeur conservée (heuristique stable). |
| `Contact.linkedin_url_status` | Écrasable | Permet la transition `candidate → verified` côté SR. |

---

## 7. Plan de déploiement (VPS)

```bash
# 1. Pull la branche sur le VPS
cd /home/ubuntu/fga-crm
git fetch origin
git checkout feature/funding-sync-multi-source
# (Ou rsync local → VPS après merge sur main)

# 2. Rebuild les images (backend + beat partagent le même Dockerfile)
docker compose -f docker-compose.vps.yml build backend beat frontend

# 3. Up — recrée les containers (beat est nouveau)
docker compose -f docker-compose.vps.yml up -d

# 4. Vérifier que la migration s'est appliquée
docker exec fga-crm-backend alembic current
# → doit afficher : a3f8c1d92e4b (head)

# 5. Vérifier que le beat est up et a chargé le schedule
docker logs fga-crm-beat --tail 20
# → doit montrer "beat: Starting..." sans erreur

# 6. Vérifier que le worker reconnaît la task funding_sync
docker exec fga-crm-worker celery -A app.tasks.celery_app inspect registered 2>&1 | grep funding
# → doit lister "app.tasks.funding_sync.sync_recent_funding_task"

# 7. Smoke test : déclencher manuellement (pas obligatoire si Phase A SR pas finie)
docker exec fga-crm-worker celery -A app.tasks.celery_app call \
  app.tasks.funding_sync.sync_recent_funding_task --args='[1]'
# Attendre 5s puis check les logs
docker logs fga-crm-worker --tail 30 | grep "FundingSync cron"
```

---

## 8. Rollback

### Code
```bash
git checkout main
docker compose -f docker-compose.vps.yml build backend beat
docker compose -f docker-compose.vps.yml up -d
```

### Base de données
```bash
docker exec fga-crm-backend alembic downgrade daa19e2fefdb
# Drop des 9 colonnes — les données funding seront perdues
```

⚠️ **Attention** : si des Activity `funding_detected` et Task `qualification` ont été créées, elles **survivent au rollback DB** (table activities et tasks intactes). Pour les nettoyer manuellement :
```sql
DELETE FROM activities WHERE type = 'funding_detected';
DELETE FROM tasks WHERE type = 'qualification';
```

### Cron
```bash
docker stop fga-crm-beat && docker rm fga-crm-beat
# Et retirer le service `beat:` de docker-compose.vps.yml
```

---

## 9. Tests

| Suite | Avant | Après | Δ |
|---|---|---|---|
| pytest (backend) | 230 pass | 248 pass | +18 (test_funding_sync.py) |
| vitest (frontend) | 15 pass | 34 pass | +19 (EmailIndicator, LinkedinIndicator, formatAmountMillions) |
| Régressions | 0 | 0 | — |

Les 30 fails RBAC pré-existants restent inchangés (assert 500 == 403, non liés à cette feature).

---

## 10. Dépendances amont (Phase A SR)

Pour que le sync fonctionne **end-to-end**, le côté SR doit exposer :
- Champs additionnels dans `GET /api/v1/startups` : `siren`, `funding_date`, `amount`, `series`, `source_names`, `investors`, `funding_date`
- Champs additionnels dans `GET /api/v1/contacts` : `enrichment_source`, `email_pattern_used`, `linkedin_url_status`
- Nouveau query param `?since=<ISO datetime>` sur `GET /api/v1/startups` (filtre `WHERE scraped_at >= since`)

Tant que Phase A n'est pas mergée côté SR :
- Le sync continue de fonctionner (mappe les champs nouveaux quand présents, sinon laisse à `null`)
- L'endpoint `sync-recent-funding` retournera un partial avec une erreur "endpoint not supporting since" — pas bloquant pour la full sync existante

---

## 11. Hors scope

Reporté à un déploiement ultérieur (cf. décisions Hervé 2026-05-11) :
- Notification email récap quotidien
- Filtrage par seuil de qualification (géré côté SR, pas CRM)
- Frontend dédié à la stat "Levées 7j" au-delà du KPI Dashboard
