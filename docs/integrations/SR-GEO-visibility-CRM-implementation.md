# Spec d'implémentation — FGA-CRM : endpoint de mesure de visibilité GEO pour SR

> **Interne FGA-CRM.** Décrit ce qu'il faut construire côté CRM pour exposer le
> contrat [`SR-GEO-visibility-API-contract.md`](SR-GEO-visibility-API-contract.md).
> Réutilise au maximum le pipeline GEO existant (collect → extract → match).
>
> Statut : proposition à valider avant code. Estimation : ~1,5–2,5 j.

---

## 1. Intention

Exposer 2 endpoints service-à-service (auth par clé `crm_`, scope `geo:audit`) qui,
à partir d'un `{company_name, domain, aliases, prompts[1..5]}`, lancent une mesure de
visibilité **Perplexity** asynchrone et renvoient un résultat agrégé
(`visible`, `visibility_rate`, `competitors_found`, `summary`).

**Contraintes** :
- Ne pas polluer le dashboard GEO de FGA (marques éphémères `is_owned=false`).
- Maîtriser le coût : dédup 30 j + quota/jour.
- Réutiliser `execute_geo_batch` / collector Perplexity / extractor existants.

---

## 2. Classification

**Changement structurel** (nouveau modèle + migration + endpoints + task Celery).
→ Design validé avant code, livraison en phases + tests (DC15).

---

## 3. Modèle de données

### Nouvelle table `geo_audit_jobs`

Tracking + dédup + résultat (le module GEO n'a pas de table de job ; on en ajoute une
dédiée, calquée sur le pattern `trend_jobs`).

| Colonne | Type | Notes |
|---|---|---|
| `id` | UUID PK | = `audit_id` renvoyé à SR |
| `organization_id` | UUID null | cohérence multi-tenant future |
| `domain` | Text, index | ex. `acme.com` |
| `company_name` | Text | |
| `request_hash` | Text, index | `sha256(domain + engine + prompts triés + country + language)` — dédup |
| `engine` | Text | `perplexity` (v1) |
| `status` | Text | `queued\|running\|completed\|failed` (DC5) |
| `brand_id` | UUID FK `geo_brands` SET NULL | marque éphémère créée |
| `result_json` | JSONB | résultat agrégé (cf. contrat §4), `{}` tant que non terminé |
| `error` | Text null | borné 2000 (DC1) |
| `created_at` / `finished_at` | timestamptz | |

Index : `ix_geo_audit_jobs_hash_status (request_hash, status)`, `ix_geo_audit_jobs_domain`.

> **Marque éphémère** : réutilise `GeoBrand` avec `is_owned=false`. Le dashboard GEO
> filtre déjà `is_owned=true` → invisible pour FGA. `slug = "audit-" + slug(domain) + "-" + short_hash`.
> Prompts créés sur cette marque (réutilisés au run).

Migration Alembic dédiée (`geo_audit_jobs`), `down_revision` = tête courante.

---

## 4. Auth & scope

- Nouveau scope : **`geo:audit`**.
- Endpoints protégés par `Depends(require_service_scope("geo:audit"))` (mécanisme
  existant, cf. `mcp_usage.py`).
- La clé se crée via `/admin/api-keys` (admin) avec ce scope. Documenter la valeur du
  quota dans la description de la clé.

---

## 5. Endpoints (`app/api/v1/geo_audit.py`)

### `POST /geo/audit-visibility`
1. Valider le body (schéma Pydantic borné, DC1) : `prompts` 1–5 × ≤1000, `aliases` ≤10,
   `domain`/`company_name` ≤255, `country`/`language` ≤8.
2. `request_hash` = sha256(domain|engine|prompts triés|country|language).
3. **Quota** : compter les jobs créés par cette clé aujourd'hui (via `request.state.api_key_name`
   ou un compteur Redis `geo_audit:quota:{key}:{yyyymmdd}`). Si ≥ plafond → `429` + `Retry-After`.
4. **Dédup** (si `refresh=false`) : job `completed` avec ce `request_hash` et
   `finished_at ≥ now-30j` → renvoyer `{audit_id, status:"completed", cache_hit:true}`.
5. Sinon : créer `GeoAuditJob(status="queued", request_hash, domain, company_name, engine)`,
   commit, puis `enqueue geo_audit_visibility_task.delay(str(job.id))`.
6. Retour `{audit_id: job.id, status:"queued", cache_hit:false}`.

### `GET /geo/audit-visibility/{audit_id}`
- Charger le job (404 si absent). Retour `{audit_id, status, engine, company_name, domain,
  created_at, result: result_json or None}`.
- `result` exposé seulement si `status="completed"`.

Enregistrer le router : `api_router.include_router(geo_audit.router, prefix="/geo", tags=["GEO Audit"])`
**avant** un éventuel `/geo/{brand_id}` (ordre de match) — de toute façon les chemins
sont `/geo/audit-visibility[...]`, sans collision.

---

## 6. Task Celery (`app/tasks/geo.py` ou `geo_audit.py`)

`geo_audit_visibility_task(audit_job_id: str)` (via `task_session_maker`, NullPool — cf.
fix cross-loop déjà en place) :

1. Charger le job. Garde d'idempotence : si `status` terminal → return (retry Celery).
2. `status="running"`, commit.
3. Créer la **marque éphémère** (`is_owned=false`, aliases) + les **prompts** (depuis
   `params`/le job — stocker les prompts dans `result_json.request` ou une colonne
   `params_json` ; simplest : ajouter `params_json` au modèle pour porter prompts +
   aliases + country/language). Lier `job.brand_id`.
4. `execute_geo_batch(db, brand_id, engine="perplexity", prompt_ids, n_runs=1, country, language)`.
5. **Agréger** depuis les `GeoRun` du batch :
   - `mentions` = runs avec `brand_mentioned`, `runs_total` = total, `visibility_rate` = %.
   - `best_position` = min des `brand_position` non nuls.
   - `recommended` = any `brand_recommended`.
   - `sentiment` = sentiment de la meilleure mention (ou agrégat simple).
   - `competitors_found` = top marques de `brands_found` **hors** la marque auditée,
     comptées (réutiliser la logique du scorer / une agrégation locale).
   - `per_prompt` = pour chaque prompt : mentioned + position.
   - `summary` = phrase FR générée par template (pas de LLM nécessaire) :
     `"{mentions}/{total} — {company} {n'apparaît nulle part | citée…} ; acteurs cités : …"`.
6. `result_json` = payload contrat §4, `status="completed"`, `finished_at`, commit.
7. Sur exception : rollback, re-fetch job, `status="failed"`, `error` borné.

> Réutilise 100 % du pipeline existant (collector Perplexity, extractor OpenAI corrigé,
> `_match_brand`). Le seul code neuf : la création marque/prompts éphémères + l'agrégation
> résultat + le job tracking.

---

## 7. Schemas Pydantic (`app/schemas/geo_audit.py`)

- `AuditVisibilityRequest` (bornes DC1) · `AuditVisibilityCreateResponse`
  (`audit_id`, `status`, `cache_hit`) · `AuditVisibilityResult` (contrat §4) ·
  `AuditVisibilityStatusResponse`.

---

## 8. Nettoyage (cron optionnel)

Task beat quotidienne : purge des `geo_audit_jobs` + marques éphémères (`is_owned=false`
créées par l'audit) `finished_at < now-90j`. Évite l'accumulation. Non bloquant pour la v1.

---

## 9. Garde-fous / DC

- **DC1** : toutes les entrées bornées (prompts, aliases, domain, country).
- **DC2** : échec → `status=failed` + erreur explicite, jamais de retour silencieux.
- **DC5** : state machine `queued→running→completed|failed` + garde d'idempotence retry.
- **DC18** : `engine`, quota = données serveur (le client ne les impose pas).
- **Isolation** : `is_owned=false` isole du dashboard ; pas de fuite de données FGA (les
  données mesurées sont publiques — réponses IA).
- **Coût** : dédup 30 j + quota/jour (le vrai garde-fou budget Perplexity/OpenAI).

---

## 10. Tests

- Unit : agrégation résultat (0/3, 2/3, breakout position), `request_hash` déterministe,
  garde idempotence retry, dédup renvoie cache_hit.
- API : auth (401 sans clé, 403 sans scope, 200 avec `geo:audit`), validation 422
  (prompts vides/6 prompts), flux POST→poll→completed (provider mocké), 404 id inconnu,
  429 quota.

---

## 11. Phasage (DC15)

| Phase | Contenu |
|---|---|
| A | modèle `geo_audit_jobs` + migration + schémas |
| B | task Celery (création marque/prompts éphémères + run + agrégation) |
| C | endpoints POST/GET + scope + dédup + quota + enregistrement router |
| D | tests + validation (ruff/pytest) + déploiement + smoke test service-key |

---

## 12. Validation

- [ ] `ruff check app/`
- [ ] `pytest tests/` (nouveaux tests audit)
- [ ] migration relue (DC10) + `alembic upgrade` OK
- [ ] smoke test prod : créer une clé `geo:audit`, POST + poll → résultat cohérent
- [ ] vérifier que la marque éphémère **n'apparaît pas** dans le dashboard GEO
