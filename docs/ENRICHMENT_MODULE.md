# Module d'enrichissement d'emails B2B (Compass)

> **Objet** — Ce document décrit **toutes** les fonctionnalités du module d'enrichissement de FGA-CRM, les **flux de données** possibles (on-demand, batch/ICP, contacts existants), et les **interactions entre applications** (CRM ↔ API gouv ↔ Icypeas ↔ Startup Radar).
>
> Dernière mise à jour : 2026-07-03. Correspond au code de `backend/app/services/enrichment/` déployé en prod.

---

## 1. Vue d'ensemble

Le module transforme un **point de départ** (un SIREN, une liste de SIREN, un filtre ICP, ou une sélection de contacts existants) en **contacts CRM prêts pour l'outreach**, avec un email pro **trouvé + vérifié**, dans le respect du RGPD (emails pro nominatifs uniquement).

Il est bâti en **architecture hexagonale** (ports/adapters) : le pipeline métier ne connaît que des interfaces abstraites (`CompanySource`, `PeopleSource`, `EmailFinder`, `EmailVerifier`) ; les implémentations réelles (Icypeas, API gouv) ou mock sont injectées par une **factory** selon la configuration. Cela permet de tourner tout le pipeline **sans aucune clé** (mode mock, dév/tests) et de basculer sur les fournisseurs réels en production via des variables d'environnement.

### Les 4 modes de lancement

| Mode | Point de départ | Résultat | Chemin d'exécution |
|------|-----------------|----------|--------------------|
| `company` | 1 SIREN | crée des contacts (décideurs) | inline (polling) |
| `batch` | liste de SIREN | crée des contacts | bulk async (webhook) si Icypeas+URL, sinon inline |
| `icp` | filtre NAF/région/effectif | crée des contacts | bulk async (webhook) si Icypeas+URL, sinon inline |
| `contacts` | contacts existants (ids ou « sans email ») | **met à jour** les contacts | bulk async (webhook) si Icypeas+URL, sinon inline |

Les modes `company/batch/icp` **créent** de nouveaux contacts à partir de sociétés (Feature A). Le mode `contacts` **enrichit des contacts déjà en base** (Feature B — après un import LinkedIn/CSV), avec option de **re-vérification** des emails existants.

---

## 2. Cartographie des applications

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FGA-CRM (ce projet)                          │
│                                                                           │
│  Frontend React            Backend FastAPI              Celery worker     │
│  ┌──────────────┐   HTTP   ┌─────────────────┐  enqueue ┌──────────────┐  │
│  │ Enrichment   │─────────▶│ POST /jobs      │─────────▶│ run_enrichment│ │
│  │ Contacts     │          │ (RBAC + quota)  │  (Redis) │ _job (orch.)  │  │
│  └──────────────┘          └─────────────────┘          └──────┬───────┘  │
│         ▲                          ▲                           │          │
│         │ poll /jobs               │ callback                  │          │
│         │                   ┌──────┴────────┐                  ▼          │
│         └───────────────────│ POST /webhook │◀────┐    PostgreSQL 16      │
│                             │ (HMAC public) │     │    (companies,        │
│                             └───────────────┘     │     contacts, jobs,   │
│                                                    │     bulks, ...)       │
└────────────────────────────────────────────────────┼──────────────────────┘
                                                      │
                    ┌─────────────────┐               │  callback bulkDone
   siren → société  │  API gouv       │               │
   ◀────────────────│ recherche-      │      ┌─────────┴──────────┐
                    │ entreprises     │      │      Icypeas       │
                    │ (gratuit)       │      │  email-search      │
                    └─────────────────┘      │  email-verification│
   contacts SR      ┌─────────────────┐      │  find-people       │
   ◀────────────────│  Startup Radar  │      │  (payant, async)   │
   (sync one-way)   │  (repo séparé)  │      └────────────────────┘
                    └─────────────────┘
```

### 2.1 Rôle de chaque application

| Application | Rôle | Couplage |
|-------------|------|----------|
| **FGA-CRM backend** | Orchestre le pipeline, stocke les données (source de vérité), expose l'API + le webhook | — |
| **API gouv** `recherche-entreprises.api.gouv.fr` | `siren → raison sociale, NAF, effectif, état` (PAS de site web). **Gratuit, sans clé.** | Appel HTTP sortant direct (aucun couplage) |
| **Icypeas** | `email-search` (trouve email), `email-verification` (vérifie), `find-people` (sourcing décideurs). **Payant, asynchrone** (submit → poll OU webhook). | Clé API + secret HMAC. Callback entrant signé |
| **Startup Radar** (repo séparé) | Pousse des startups/contacts vers le CRM via un sync **one-way**. Fournit `enrichment_source` (provenance de SON propre enrichissement). | Sync existant `startup_radar_sync.py` — indépendant du module d'enrichissement |
| **Frontend** | Déclenche les jobs (page Enrichissement + multi-select page Contacts), affiche l'état (polling) et la fiabilité des emails (`EmailIndicator`) | HTTP interne |

> **Note d'isolation** : le module d'enrichissement et la sync Startup Radar sont **deux flux distincts**. SR n'appelle pas Icypeas ; le module d'enrichissement n'appelle pas SR. Ils se rejoignent uniquement dans la table `contacts` (colonne `enrichment_source`).

---

## 3. Le pipeline métier (7 étapes)

Implémenté dans `orchestrator.py`. Selon le mode, certaines étapes sont sautées.

```
1. Résolution des sociétés     (CompanySource : get_by_siren / get_companies)
2. Résolution du domaine       (resolve_domain, heuristique — OPTIONNEL)
3. Sourcing des personnes      (PeopleSource : find-people, cascade coût-croissant)
4. Recherche d'email           (EmailFinder : domainOrCompany = domaine OU nom société)
5. Filtres RGPD                (classify_email = pro nominatif ? + suppression opt-out)
6. Vérification                (EmailVerifier : deliverabilité)
7. Persistance CRM             (crm_writer : upsert_contact / update_contact_email + provenance)
```

### Garde-fous transverses
- **Budget par run** (`CreditLedger`, `enrichment_max_credits_per_run=5000`) : `can_spend()` avant chaque dépense ; en mode sourcing, débité **par résultat** (un provider peut renvoyer N leads).
- **Quota journalier par organisation** (`reserve_daily_credits`, Redis, `enrichment_daily_quota=5000`) : réservation **atomique** (script Lua) AVANT l'enqueue Celery ; fail-**closed** en prod si Redis KO.
- **Fraîcheur** (`freshness`, Redis, TTL `enrichment_refresh_days=60j`) : une personne enrichie récemment n'est pas re-soumise/re-facturée. Clé partagée `person:{org}:{siren}:{prénom}.{nom}` entre tous les chemins (inline et bulk).
- **Suppression RGPD** (`is_suppressed`, table `enrichment_suppressions`) : opt-out / bounce, scopé par organisation.
- **Cascade waterfall** (`waterfall.py`) : providers du moins cher au plus cher, stop au 1er succès (utilisé pour le sourcing des personnes).

---

## 4. Flux de données détaillés

### 4.1 Mode `company` (on-demand, 1 SIREN)

Le plus simple — synchrone, polling Icypeas. Déclenché depuis la fiche société ou la page Enrichissement.

```
Frontend ──POST /jobs {mode:"company", siren}──▶ Backend
   Backend: RBAC (admin|manager) + reserve_daily_credits (quota org) + crée EnrichmentJob(status=queued)
   Backend ──.delay(job_id)──▶ Celery (Redis)
   Celery: run_enrichment_job
      1. GouvCompanySource.get_by_siren(siren) ──HTTP──▶ API gouv → Company(name, naf, domain=None)
      2. resolve_domain (heuristique nom→domaine, best-effort ~40%) [OPTIONNEL]
      3. IcypeasPeopleSource.find_people ──HTTP (poll)──▶ Icypeas → décideurs (CTO/CPO/CMO/FOUNDER)
      4. Pour chaque personne: IcypeasEmailFinder.find(person, domainOrCompany) ──HTTP (poll)──▶ Icypeas
      5. classify_email (pro nominatif ?) + is_suppressed
      6. IcypeasEmailVerifier.verify(email) ──HTTP (poll)──▶ Icypeas
      7. upsert_contact(...) + EnrichmentEmailVerification + record_provenance
      job.status = done  (commit par société = checkpoint résilient)
Frontend: poll GET /jobs → voit done + stats
```

**Interaction clé** : `domainOrCompany` — Icypeas accepte un **domaine OU un nom de société**. Si `resolve_domain` échoue (cas fréquent, ~60%), on passe `company.name` → la personne reste enrichissable. La résolution de domaine n'est donc **jamais bloquante**.

### 4.2 Modes `batch` / `icp` (bulk asynchrone via webhook)

Pour un volume, le polling par personne serait trop lent. Bascule sur le mode **bulk + webhook** dès que `icypeas_api_key` ET `icypeas_webhook_url` sont configurés.

```
Frontend ──POST /jobs {mode:"batch", sirens[]}──▶ Backend ──.delay──▶ Celery
   Celery: run_enrichment_job → _should_use_bulk(target)=true
      1. Résout les sociétés (batch: get_by_siren concurrent, sémaphore 5 ; icp: get_companies paginé)
      2-3. Source les personnes (inline, cascade)
      4'. NE cherche PAS l'email en direct. Construit UN bulk email-search:
            rows = [[prénom, nom, domainOrCompany], ...]
            contexts = [{company, person}, ...]  ← stocké pour reconstruire au callback
      ──POST /bulk-search (webhookUrlBulkDone, includeResultsInWebhook)──▶ Icypeas
      Persiste EnrichmentBulk(file=<id Icypeas>) + EnrichmentBulkItem[] (status=pending)
      job.status = awaiting_results   ← le job N'EST PAS terminé ici
   ... (minutes/heures plus tard) ...
   Icypeas ──POST /api/v1/integrations/icypeas/webhook {signature, timestamp, data}──▶ Backend
      Webhook: borne taille (2 Mo) + fenêtre anti-rejeu (±300s) + HMAC-SHA1
      process_bulk_callback: verrou ligne bulk (with_for_update, idempotent)
         Pour chaque résultat: RGPD + upsert_contact + verif + provenance + touch(fresh)
         Marque item found/not_found/error (savepoint par item)
      Quand tous les items du bulk sont résolus: bulk.done, et si TOUS les bulks du job
         sont done (verrou ligne job) → job.status = done
Frontend: poll GET /jobs → awaiting_results (badge ambre) → done
```

**Filet de sécurité** : `enrichment_reconcile_bulks_task` (Celery **beat, horaire** — `enrichment-reconcile-bulks-hourly` dans `celery_app.py`) marque `error`/`failed` les bulks sans callback au-delà de `enrichment_bulk_timeout_hours=24`.

### 4.3 Mode `contacts` (Feature B — enrichir l'existant)

Prend des contacts **déjà en base** (importés LinkedIn/CSV) et **met à jour** leur email — ne crée rien.

```
Déclencheurs UI:
  (a) Page Contacts: multi-select + bouton "Enrichir (N)" → {mode:"contacts", contact_ids:[...]}
  (b) Page Enrichissement: mode "Contacts existants" → {mode:"contacts", all_missing_email:true, reverify?}

_resolve_contacts (org-scopé, borné 1000):
   - contact_ids fournis        → ces contacts
   - all_missing_email + !reverify → contacts sans email (à trouver)
   - all_missing_email + reverify  → TOUS les contacts (manquants→find, remplis→reverify)

Bulk (_submit_bulk_contacts) — jusqu'à DEUX bulks sous un même job:
   - Contacts SANS email → bulk email-search  (rows=[prénom, nom, domainOrCompany])
   - Contacts AVEC email (si reverify) → bulk email-verification (rows=[[email]])
   Chaque item porte context.contact_id  ← marque le mode UPDATE côté callback

Webhook (_resolve_item):
   - context.contact_id présent → update_contact_email (MET À JOUR le contact existant)
        + backfill du domaine société depuis l'email Icypeas (si absent, anti-collision)
        + flag email_verified_by_icypeas = true
   - email injoignable en reverify (NOT_FOUND) → contact marqué email_status = "invalid"
   - suppression RGPD TOUJOURS vérifiée (même en reverify)
   Job done quand TOUS ses bulks (search + verify) sont done.
```

**Distinction inline/bulk** : si Icypeas n'est pas configuré (ou pas d'URL webhook), le mode `contacts` s'exécute **inline** (`_run_contacts_inline` → `_process_contact`, polling par contact). Le reverify est supporté dans les deux chemins.

---

## 5. Modèle de données

| Table | Rôle | Colonnes clés |
|-------|------|---------------|
| `companies` | sociétés CRM (source de vérité) | `siren`, `domain`, `domain_verified_by_icypeas`, unique **composite** `(organization_id, domain)` |
| `contacts` | contacts CRM | `email`, `email_status`, `email_verified_by_icypeas`, `enrichment_source`, `email_pattern_used`, `company_id` |
| `enrichment_jobs` | un job d'enrichissement | `mode`, `status` (queued/running/awaiting_results/done/failed), `target_json`, `stats_json` |
| `enrichment_bulks` | un bulk Icypeas rattaché à un job | `file` (id Icypeas), `task` (email-search/email-verification), `status`, `total/done/found` |
| `enrichment_bulk_items` | une ligne d'un bulk | `external_id`, `context_json` (company+person+contact_id), `status`, `contact_id` |
| `enrichment_email_verifications` | historique des vérifications | `email`, `status`, `confidence`, `deliverable`, `source` |
| `enrichment_provenance` | traçabilité (qui a fourni quoi) | `entity_type` (person/email), `field`, `source` |
| `enrichment_suppressions` | opt-out / bounces (RGPD) | `email`, `domain`, `linkedin_url`, `reason` |

**Isolation multi-tenant** : toutes ces tables portent `organization_id`. Tout read/write filtre par org. Les contraintes d'unicité sont **composites** `(organization_id, X)` — jamais globales (sinon collision cross-org).

---

## 6. Contrats externes

### 6.1 API gouv (`recherche-entreprises.api.gouv.fr`)
- `GET /search?q=<siren>&per_page=1` → identité (`nom_raison_sociale`, `activite_principale`, `etat_administratif`, `tranche_effectif_salarie`, `finances.<année>.ca`, `siege.*`). **Pas de site web.**
- `GET /search?activite_principale=<NAF>&etat_administratif=A&departement=<dept>&page=N` → recherche ICP (total capé à 10000).
- Gratuit, sans clé. Retry/backoff sur 429/5xx, throttle ~7 req/s.

### 6.2 Icypeas (payant, asynchrone)
- `POST /api/email-search` `{firstname, lastname, domainOrCompany}` → submit, puis poll `bulk-single-searchs/read`.
- `POST /api/email-verification` `{email}` → submit + poll.
- `POST /api/bulk-search` `{task, data[], custom:{externalIds, webhookUrlBulkDone, includeResultsInWebhook}}` → `{file}`.
- **Callback bulkDone** : `{signature, timestamp, data:{file, results[]}}` où `results[].results.emails[0].{email, certainty}` + `results[].userData.externalId`.
- **Certitudes** → statut : `ultra_sure`/`very_sure`/`probable` → `valid` ; `undeliverable`/`not_found` → `invalid` ; défaut → `risky`.
- **Sécurité du callback** : signature HMAC-SHA1 sur `lowercase(path+timestamp)` + fenêtre anti-rejeu ±300s. La signature **ne couvre pas le corps** (limite du protocole Icypeas) → la fenêtre de fraîcheur borne le rejeu.

---

## 7. Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|----------|--------|------|
| `ICYPEAS_API_KEY` | — | Active les adapters Icypeas réels (sinon mock) |
| `ICYPEAS_API_SECRET` | — | Secret HMAC de vérification du webhook |
| `ICYPEAS_WEBHOOK_URL` | — | URL publique du callback (active le mode bulk) |
| `ICYPEAS_WEBHOOK_VERIFY` | `true` | Vérifier la signature (refus en prod si `false`) |
| `ENRICHMENT_COMPANY_SOURCE` | `mock` | `gouv` = API gouv réelle ; `mock` = dév/tests |
| `ENRICHMENT_DAILY_QUOTA` | `5000` | Crédits/jour par organisation |
| `ENRICHMENT_MAX_CREDITS_PER_RUN` | `5000` | Plafond par job |
| `ENRICHMENT_REFRESH_DAYS` | `60` | TTL fraîcheur personne |
| `ENRICHMENT_BULK_TIMEOUT_HOURS` | `24` | Bulk sans callback → réconcilié `failed` |
| `ENRICHMENT_CATCHALL_ACCEPT` | `0.90` | Seuil d'acceptation catch-all |

**Sélection des adapters** (`factory.py`) :
- `get_company_source()` → `GouvCompanySource` si `ENRICHMENT_COMPANY_SOURCE=gouv`, sinon `MockCompanySource`.
- `get_email_finders/verifiers/people_sources()` → adapters Icypeas si `ICYPEAS_API_KEY`, sinon mocks.
- `get_bulk_client()` → client Icypeas si clé, sinon `None` (force le repli inline).

---

## 8. Affichage de la fiabilité (frontend)

`EmailIndicator` affiche un badge selon `email_status` + `enrichment_source` + `email_pattern_used` :
- `valid` → **Vérifié** (vert).
- `unknown` → **Candidat** (ambre) ; + **Pas vérifié** (rouge) si l'email a été **deviné** (source heuristique connue OU présence d'un `email_pattern_used`). Fallback générique `source « X »` pour toute source inconnue.
- `risky`/`invalid` → **Risqué** (rouge).

Le statut job `awaiting_results` (bulk en attente du webhook) est affiché en badge ambre et **maintient le polling** de la page Enrichissement.

---

## 9. Endpoints

| Méthode | Chemin | Auth | Rôle |
|---------|--------|------|------|
| POST | `/api/v1/enrichment/jobs` | admin/manager | Créer un job (tous modes) |
| GET | `/api/v1/enrichment/jobs` | admin/manager | Lister les jobs (org-scopé) |
| GET | `/api/v1/enrichment/jobs/{id}` | admin/manager | Détail d'un job |
| POST | `/api/v1/enrichment/companies/{siren}/enrich` | admin/manager | Raccourci mode company |
| POST | `/api/v1/integrations/icypeas/webhook` | **public (HMAC)** | Callback bulkDone Icypeas |

---

## 10. États d'un job

```
queued ──▶ running ──┬──▶ done            (inline, ou bulk sans lignes à enrichir)
                     └──▶ awaiting_results ──▶ done      (bulk : callback reçu, tous bulks résolus)
                                            └──▶ failed   (reconcile : timeout callback)
running ──▶ failed   (erreur globale, bornée DC2)
```

Résilience : commit **par société** (modes création) ou **par contact** (mode contacts inline) = checkpoint ; savepoint **par item** au callback (une collision n'annule pas tout le bulk).

---

## 11. Limitations connues / points de vigilance

- **Résolution de domaine ~40%** (heuristique nom→domaine). Le reste passe par le nom société via `domainOrCompany` — non bloquant.
- **Recherche ICP capée à 10000** (limite dure de l'API gouv).
- **Rétention RGPD** (`enrichment_retention_days=1095`) : **configurée mais pas encore appliquée** — aucune tâche de purge n'est implémentée. À câbler avant une mise en conformité stricte.
- **Réconciliation des bulks** : `enrichment_reconcile_bulks_task` tourne **automatiquement** (Celery beat horaire). Elle marque `error`/`failed` mais **ne re-poll pas** les résultats — le webhook `includeResults` reste le chemin nominal (un endpoint de lecture bulk Icypeas n'a pas été capté).
- **Signature webhook** : ne couvre pas le corps (protocole Icypeas) ; atténuée par la fenêtre anti-rejeu.
- **Startup Radar** peut envoyer des `enrichment_source` inconnus du CRM ; `EmailIndicator` les gère génériquement depuis 2026-07-03.

---

## 12. Fichiers de référence

```
backend/app/services/enrichment/
├── orchestrator.py      Pipeline 7 étapes + modes company/batch/icp/contacts
├── bulk_callback.py     Traitement du webhook bulkDone + reconcile
├── crm_writer.py        upsert_contact (create) / update_contact_email (Feature B)
├── factory.py           Sélection des adapters (réel vs mock)
├── ports.py             Interfaces + dataclasses (Company, PersonCandidate, TargetSpec...)
├── credit_ledger.py     Budget par run + quota journalier org (Redis, Lua)
├── freshness.py         TTL de fraîcheur (Redis) + client partagé
├── rgpd.py              classify_email (pro/perso/générique)
├── suppression.py       is_suppressed (opt-out/bounce, org-scopé)
├── roles.py             normalize_title (CTO/CPO/CMO/FOUNDER/OTHER)
├── provenance.py        record_provenance (traçabilité)
├── waterfall.py         Cascade coût-croissant générique
└── adapters/
    ├── gouv.py          GouvCompanySource (API gouv, Feature A)
    ├── icypeas.py       Client + EmailFinder/Verifier/PeopleSource + webhook HMAC
    └── mock.py          Adapters déterministes (dév/tests, sans clé)

backend/app/api/v1/enrichment.py          Endpoints jobs
backend/app/api/v1/enrichment_webhook.py  Endpoint webhook public
backend/app/models/enrichment.py          Modèles ORM (jobs, bulks, items, ...)
frontend/src/pages/Enrichment.tsx         UI de lancement (4 modes)
frontend/src/components/contacts/EmailIndicator.tsx  Affichage fiabilité email
```
