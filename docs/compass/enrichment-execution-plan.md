# Plan d'exécution — Enrichissement d'emails B2B (feature FGA-CRM / Compass)

> Adapte `enrichment-module-spec.md` (racine) en **feature native FGA-CRM**, brique du
> produit **Compass** (CRM+SR+PPD+NOMO-IA pour PME/ETI). Multi-tenant dès le départ,
> 2 modes au choix (à la demande + batch/ICP), moteur Icypeas **mock-first** (buildable
> sans clé, comme le provider mock de Trends).
>
> Statut : plan validé, développement à suivre. Cf. mémoire `enrichment-feature-compass`.

---

## 1. Objectif & périmètre

Sourcer les décideurs fonctionnels (CTO/CPO/CMO) des éditeurs de logiciels FR, résoudre
+ vérifier leurs emails pro nominatifs (Icypeas), défendable RGPD, produire des
**contacts CRM natifs** prêts pour l'outreach (NOMO-IA en aval).

**2 modes (au choix de l'utilisateur, via `TargetSpec.kind`)** :
- **A — à la demande** : 1 société (depuis sa fiche) → « Enrichir les décideurs ».
- **B — batch/ICP** : filtre NAF éditeurs + limite → job async (budget, fraîcheur, reprise).

Hors périmètre : envoi/séquences (module outreach), génération de contenu (NOMO), scoring
final (`lead_score_multibrand`, invoqué en fin).

---

## 2. Intégration dans FGA-CRM (mapping spec → repo)

| Spec | FGA-CRM |
|---|---|
| Orchestrateur + ports/adapters | `backend/app/services/enrichment/` |
| Modèle de données | `backend/app/models/enrichment.py` + migration Alembic |
| API d'entrée | `backend/app/api/v1/enrichment.py` (RBAC manager+) |
| Jobs async (Icypeas async) | `backend/app/tasks/enrichment.py` (Celery, `task_session_maker` NullPool) |
| CreditLedger / FreshnessCache | services Redis (patterns quota geo-audit + dédup Trends) |
| UI + sidebar | `frontend/src/pages/Enrichment.tsx` + `components/enrichment/` + item sidebar |
| `crm_upsert_contact` | **écriture DB interne** (contacts CRM) — plus un appel MCP |

**Réutilisé tel quel** : auth/RBAC, service-keys, Celery+Redis, Postgres+Alembic, UI_GUIDELINES.
**Externe (API/MCP)** : Icypeas (nouveau), Plein Phare/frdata, Startup Radar.

---

## 3. Modèle de données (multi-tenant dès le départ)

**Principe** : ne PAS dupliquer `companies`/`contacts` (source de vérité CRM). La sortie du
pipeline crée/enrichit des **contacts**. On ajoute des tables dédiées à l'état d'enrichissement.
Toutes portent `organization_id` (nullable, indexé — convention GEO/Trends ; deviendra réel
avec le multi-tenant Compass).

- **`enrichment_jobs`** : id, organization_id, created_by (FK users SET NULL), mode
  (`company|batch|icp`), target_json (TargetSpec), status (`queued|running|done|failed`),
  stats_json (people_found, emails_found, credits_spent, valid_count…), error, created_at,
  finished_at, updated_at. Index (status, created_at).
- **`enrichment_provenance`** : id, organization_id, entity_type (`person|email`),
  contact_id (FK contacts SET NULL), field (`name|email|title|linkedin`), source (enum),
  source_detail, legal_basis (`legitimate_interest`), collected_at. → réponse CNIL « d'où vient
  ma donnée ». Immuable.
- **`enrichment_suppression`** : id, organization_id, email?, domain?, linkedin_url?, reason
  (`opt_out|bounce|manual|bloctel`), added_at. Index (email), (domain).
- **`enrichment_email_verifications`** : id, organization_id, contact_id (FK contacts),
  email, domain_type (`pro|personal|generic`), confidence, status
  (`valid|catch_all|risky|invalid`), deliverable (bool), source, verified_at.

> Les candidats non retenus (sans email valide) NE sont PAS persistés individuellement
> (comptés dans job.stats). Seuls les décideurs délivrables deviennent des `contacts`.
> Évite une table `Person` parallèle qui dupliquerait `contacts`.

Enums (source unique, `models/enrichment.py`) : Role, DomainType, VerificationStatus, Source,
SuppressionReason, EnrichmentMode, JobStatus.

---

## 4. Ports & adapters (hexagonal — comme les providers Trends)

**Ports** (`services/enrichment/ports.py`, ABC) : `CompanySource`, `PeopleSource`,
`EmailFinder`, `EmailVerifier`. Value objects : Company, PersonCandidate, EmailCandidate,
VerificationResult, TargetSpec, IcpFilter.

**Adapters** (`services/enrichment/adapters/`) :
- `crm_people.py` — CrmPeopleSource (interne, coût 0)
- `startup_radar.py` — StartupRadarPeopleSource (radar_get_decision_makers)
- `plein_phare.py` — PleinPhareCompanySource (frdata_*)
- `icypeas.py` — IcypeasClient (async) + FindPeople/EmailFinder/Verifier
- **`mock.py` — MockIcypeas* déterministe** (build-first, sans clé — cf. Trends mock)
- `millionverifier.py` (option, 2ᵉ passe)

**Factory** (`services/enrichment/factory.py`) : sélectionne Icypeas réel si clé configurée,
sinon mock. Ordre des sources piloté par config (§17 spec).

**Cascade `waterfall`** (`services/enrichment/waterfall.py`) : stop au 1er succès, ordre
coût-croissant, respecte le budget (CreditLedger). Réutilisée sourcing personnes ET fallback finders.

**Services transverses** (`services/enrichment/services/`) :
- `credit_ledger.py` — quota/budget **par organisation** (Redis, garde-fou canSpend). 
- `freshness.py` — TTL 60/90j (dédup, Redis/DB).
- `suppression.py` — opt-out/bounce (table).
- `provenance.py` — audit RGPD (table).

---

## 5. Orchestrateur & pipeline (7 étapes, spec §5)

`services/enrichment/orchestrator.py::run(db, job)` :
1. Résolution comptes (CompanySource + filtre ICP/NAF + résolution domaine).
2. Filtre suppression (écarter domaines opt-out).
3. Sourcing personnes (cascade CRM→Radar→Icypeas, stop-on-cover, normalizeTitle → rôle).
4. Résolution email (Icypeas Email Finder, réutilise email connu CRM/Radar sans re-facturer).
5. Vérification + **filtres RGPD bloquants** (rejet perso/générique, statut valid/catch_all/…).
6. Persistance : upsert contact interne + provenance + verification + TTL.
7. Scoring (`lead_score_multibrand`) + stats job.

Idempotent (garde d'état terminal), échec → `failed` borné (DC2/DC5). Mode A = 1 société,
Mode B = boucle sur le batch (async, reprise).

---

## 6. API (RBAC manager+, `api/v1/enrichment.py`)

- `POST /enrichment/jobs` — body `{ mode, target }` (company|batch|icp) → `{ job_id, status }`.
- `GET /enrichment/jobs/{id}` — statut + stats + résumé.
- `GET /enrichment/jobs` — liste paginée (par org).
- `POST /companies/{siren}/enrich` — raccourci Mode A (équivaut à POST jobs kind=company).
- `GET /enrichment/config` — rôles cibles, seuils (lecture).

Quota par org (CreditLedger) sur POST. Dédup fraîcheur avant dépense.

---

## 7. Frontend (`pages/Enrichment.tsx` + sidebar)

- **Sidebar** : entrée « Enrichissement » (RBAC manager+), icône Lucide.
- **Page** : 2 onglets/modes — « À la demande » (recherche société → enrichir) et
  « Batch/ICP » (filtre NAF + limite → lancer). Liste des jobs + polling statut + résultats
  (contacts trouvés, taux, coût, provenance). États idle/running/done/failed. Conforme UI_GUIDELINES.
- **Fiche société** : bouton « Enrichir les décideurs » (Mode A) → job + toast + refresh contacts.
- `types/enrichment.ts` + `api/enrichment.ts` (alignés DC10).

---

## 8. Phasage (commits entre chaque — DC15). Mock-first : buildable sans clé Icypeas.

| Phase | Contenu | Dépend d'Icypeas ? |
|---|---|---|
| **P1 — Socle** | models multi-tenant + migration + enums + `normalize_title()` + filtres RGPD (blocklist perso/génériques) + config + tests unit | non |
| **P2 — Ports + adapters mock** | ports (ABC) + value objects + MockIcypeas déterministe + services (Credit/Freshness/Suppression/Provenance) + waterfall + tests | non (mock) |
| **P3 — Orchestrateur** | pipeline 7 étapes + task Celery + tests (mock, déterministe) | non (mock) |
| **P4 — API** | endpoints 2 modes + RBAC + quota + dédup + tests | non |
| **P5 — UI** | page + sidebar + bouton fiche société + polling + tests | non |
| **P6 — Icypeas réel** | cartographie API live + adapters réels (Icypeas/frdata/Radar) + swap factory + validation live + test cadrage §20 | **OUI (clé requise)** |
| **P7 — Conformité & résilience** | purge 3 ans, opt-out bloquant E2E, retries/rate-limit, métriques par tenant, audit log | partiel |

**Livrable démontrable dès P5** : les 2 modes fonctionnent avec des données mock déterministes
(comme Trends l'a fait). P6 branche le vrai moteur quand la clé Icypeas est là.

---

## 9. Coût & RGPD (opérationnalisés, pas documentés)

- **Coût** : CreditLedger par org + ordre coût-croissant + facturation au succès (Email Finder 1cr
  seulement si trouvé). Plafonds `maxCreditsPerRun` / `globalCeiling` (config).
- **RGPD** (dans le pipeline) : base légale legitimate_interest sur chaque provenance ; emails pro
  nominatifs uniquement (rejet perso/générique bloquant) ; suppression consultée avant enrichissement
  ET avant safe_to_send ; rétention 3 ans (purge) ; mention art.14 rattachée (aval outreach).
- **Gate non-technique** : LIA + registre validés par DPO/juridique avant prod (§21.8 spec).

---

## 10. Points ouverts (non bloquants pour P1-P5)

1. **Nom sidebar** : « Enrichissement » par défaut (à confirmer).
2. **Clé Icypeas** : requise pour P6 (cartographie live + adapter réel). P1-P5 en mock.
3. **Accès frdata/Radar** : format exact `radar_get_decision_makers`, domaine stocké côté PPD ? (P6).
4. **ESP bounce feedback** (P7).
5. **Organization model** : `organization_id` posé dès maintenant (nullable) ; activation multi-tenant
   Compass = chantier transverse séparé.

---

## 11. Validation (chaque phase)
`ruff check app/` · `pytest tests/` · `tsc --noEmit` · `eslint` · `vitest` · migration relue (DC10).
Déploiement prod après P-validées (rsync + build + up, migration Alembic auto).
