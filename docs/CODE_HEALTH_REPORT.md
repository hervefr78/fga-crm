# Rapport Code-Health — FGA CRM

> Date : 2026-07-03
> Périmètre : `backend/app/` + `frontend/src/` (hors tests, hors `node_modules`, hors `__pycache__`)
> Objectif : (A) ménage du code mort, (B) repérage des drifts de taille (> 500 lignes), (C) proposition d'optimisation.

---

## Résumé exécutif

| Axe | Constat | État |
|-----|---------|------|
| **Code mort supprimé** | 1 fichier + 1 dépendance + 3 symboles backend | ✅ Fait (PR #14) |
| **Code mort candidat** | 9 exports API + 31 types + 23 constantes | ⏳ Décision utilisateur (voir §A.2) |
| **Modules > 500 lignes** | 10 modules (drift confirmé) | 📋 Plan §C |
| **Modules 400–500 lignes** | 3 modules (watch-list) | 👁️ Surveillance |

Aucun de ces points n'est bloquant pour la prod. Le code mort réel a été retiré ; le reste est de la **dette de lisibilité** à résorber progressivement, en suivant le pattern d'extraction déjà validé sur `Trends.tsx` et `GEO.tsx`.

---

## Partie A — Code mort

### A.1 — Supprimé (PR #14, iso-comportement)

Détecté via **knip** (frontend, comprend les barrels/entry-points) + analyse manuelle backend (en ignorant les faux positifs `vulture` : décorateurs FastAPI/Celery, `cls` Pydantic).

| Type | Symbole | Fichier | Preuve |
|------|---------|---------|--------|
| Fichier | `TaskProgress.tsx` | `frontend/src/components/dashboard/` | 0 import dans tout le repo |
| Dépendance | `date-fns` | `frontend/package.json` + lockfile | 0 usage dans `src/` |
| Fonction | `is_pro_nominative()` | `backend/app/services/enrichment/rgpd.py` | wrapper redondant sur `classify_email`, 0 appel applicatif |
| Classe | `UserListResponse` | `backend/app/api/v1/users.py` | alias de `UserResponse` jamais référencé |
| Enum | `TrendJobStatus` | `backend/app/schemas/trends.py` | statuts stockés en `str`, enum jamais instancié |

**Validation** : ruff 0 · pytest 625 · tsc 0 · eslint 0 · vitest 65.

### A.2 — Candidats NON supprimés (décision requise)

Ces symboles sont inutilisés *aujourd'hui* mais relèvent de la **complétude de contrat** (client API exhaustif, types miroir du backend, constantes documentaires). Les retirer casserait la symétrie front/back et compliquerait l'ajout de features. **Recommandation : conserver**, sauf volonté explicite de minimiser la surface.

**Frontend — 9 exports API inutilisés** (`api/*.ts`)
`register`, `getTask`, `getActivity`, `getUser`, `getEmailTemplate` (`client.ts`) · `getDraft` (`drafts.ts`) · `getEnrichmentJob` (`enrichment.ts`, réf. mock test) · `deleteGeoBrand` (`geo.ts`) · `getTrendHealth` (`trends.ts`, réf. mock test).
→ *Client API complet vis-à-vis du backend. Les `getX` unitaires complètent les `listX` déjà utilisés.*

**Frontend — 31 exports de types inutilisés** (`types/*.ts`, `api/enrichment.ts`, `api/geo.ts`, `api/trends.ts`)
→ *Types miroir des schémas Pydantic backend. Supprimer désynchronise le contrat.*

**Backend — 23 constantes documentaires**
`ENRICHMENT_ROLES`, `DOMAIN_TYPES`, `VERIFICATION_STATUSES`, `ENRICHMENT_SOURCES`, `SUPPRESSION_REASONS`, `ENRICHMENT_MODES`, `ENRICHMENT_JOB_STATUSES`, `ENRICHMENT_BULK_STATUSES`, `ENRICHMENT_BULK_ITEM_STATUSES` (`models/enrichment.py`) · `GEO_ENGINES`, `INTENTS`, `SENTIMENTS`, `AUDIT_STATUSES` (`models/geo.py`) · `TREND_MODES`, `JOB_STATUSES`, `SOURCE_KINDS`, `SEED_SOURCES` (`models/trends.py`) · `NEXT_ACTION_TYPES`, `TEMPLATE_VARIABLE_PATTERN`, `KNOWN_VARIABLES` (schemas) · `VISIBILITY_FLOOR` (`geo/alerts.py`).
→ *Énumèrent les valeurs autorisées d'un champ `str` (self-documentation du domaine). À conserver comme référence, ou migrer vers des `StrEnum` réellement utilisés dans les schémas si on veut les rendre « vivants ».*

---

## Partie B — Drift de taille des modules

Seuil projet : **400 lignes** (règle CLAUDE.md « aucune fonction > 400 lignes » → étendue au fichier comme signal de responsabilité multiple).

### B.1 — Drift confirmé (> 500 lignes)

| # | Module | Lignes | Nature | Cause du drift |
|---|--------|-------:|--------|----------------|
| 1 | `frontend/src/pages/CompanyDetail.tsx` | 1093 | Page React | 12 `useQuery/useMutation` + tous les panneaux inline |
| 2 | `frontend/src/pages/DealDetail.tsx` | 1051 | Page React | 11 hooks query + sections inline |
| 3 | `backend/app/api/v1/integrations.py` | 1019 | Routes API | **3 intégrations** dans 1 fichier (SR + Nomo-IA + Plein Phare) + schémas inline |
| 4 | `backend/app/api/v1/geo.py` | 1012 | Routes API | **18 endpoints** (brands/prompts/runs/metrics) dans 1 fichier |
| 5 | `backend/app/services/startup_radar_sync.py` | 976 | Service | fetch + mapping + upsert/dedup mélangés |
| 6 | `frontend/src/pages/ContactDetail.tsx` | 733 | Page React | 9 hooks query + sections inline |
| 7 | `backend/app/services/enrichment/orchestrator.py` | 683 | Service | 4 modes (company/batch/icp/contacts) dans 1 orchestrateur |
| 8 | `frontend/src/pages/GEO.tsx` | 633 | Page React | déjà réduite de 1031→633 (extraction en cours) |
| 9 | `frontend/src/types/index.ts` | 614 | Types barrel | tous les types CRM dans 1 fichier (faible risque) |
| 10 | `frontend/src/components/audit/AuditResultPanel.tsx` | 601 | Composant | ~39 sous-fonctions de rendu inline |

### B.2 — Watch-list (400–500 lignes)

| Module | Lignes | Note |
|--------|-------:|------|
| `backend/app/api/v1/deals.py` | 484 | 7 endpoints + logique pricing — acceptable, surveiller |
| `backend/app/services/geo/collector.py` | 455 | collecte multi-moteur — cohésif |
| `backend/app/api/v1/mcp_usage.py` | 421 | agrégations MCP — cohésif |

---

## Partie C — Propositions d'optimisation

> **Pattern de référence** (déjà validé sur ce repo — commits `4cebbfa`, `cf15cea`, `1f5b911`) :
> extraire vers des siblings `components/<feature>/` :
> `<Feature>Atoms.tsx` (PageHeader, KpiTile, atomes présentationnels) ·
> `<feature>Utils.ts` (constantes + helpers purs) ·
> `<Feature>ReportView.tsx` / panneaux de section ·
> `<Feature>Modal.tsx` (modales/forms).
> Résultat obtenu : `Trends.tsx` 547→209, `GEO.tsx` 1031→633, **iso-comportement**, tsc/eslint/vitest verts.

### C.1 — Backend : `integrations.py` (1019 → ~3×300) — **priorité haute**

Un seul fichier héberge 3 intégrations indépendantes. Découpe par intégration :

```
api/v1/integrations/
├── __init__.py           # router agrégateur (include les 3 sous-routers)
├── _auth.py              # verify_integration_auth (Bearer crm_xxx + fallback X-Nomo, partagé)
├── startup_radar.py      # sync SR → CRM (audit avancé)
├── nomo.py               # POST /nomo/... (NomoNewSubscription*)
└── plein_phare.py        # POST /plein-phare/... (order + refund)
```
Schémas Pydantic inline → `schemas/integrations.py`. Gain : chaque intégration testable/modifiable isolément, auth mutualisée (DC8).

### C.2 — Backend : `geo.py` (1012 → 4 fichiers) — **priorité haute**

18 endpoints = 4 sous-ressources. Découpe par ressource (le routeur `geo_audit.py` est déjà séparé — même approche) :

```
api/v1/geo/
├── __init__.py     # router agrégateur
├── brands.py       # CRUD marques (GET/POST/DELETE brands)
├── prompts.py      # CRUD prompts + génération
├── runs.py         # lancement runs + résultats
└── metrics.py      # métriques daily + rankings + gaps
```
Les helpers `_entity_to_response` / `_parse_uuid` communs → `geo/_common.py`.

### C.3 — Backend : `startup_radar_sync.py` (976 → 3 couches) — **priorité moyenne**

Service mélangeant 3 responsabilités. Séparer en couches :

```
services/startup_radar/
├── client.py     # fetch SR (HTTP, pagination, retry)
├── mapper.py     # transform payload SR → dict CRM (pur, testable)
└── sync.py       # orchestration upsert/dedup (startup_radar_id) + transaction
```
Le `mapper.py` pur devient trivialement testable (edge cases DC11 sans mock HTTP).

### C.4 — Backend : `enrichment/orchestrator.py` (683 → handlers par mode) — **priorité moyenne**

4 modes (`company`/`batch`/`icp`/`contacts`) dans un orchestrateur. Extraire un handler par mode :

```
services/enrichment/
├── orchestrator.py     # dispatch + pipeline commun (waterfall, rgpd, credit_ledger)
└── modes/
    ├── company.py      # enrichissement inline 1 société
    ├── bulk.py         # batch + icp (recherche par lot Icypeas + webhook)
    └── contacts.py     # Feature B : enrichir/re-vérifier contacts existants
```
L'orchestrateur garde le pipeline transverse (RGPD, suppression, provenance, crédits) ; chaque mode ne décrit que sa cible.

### C.5 — Frontend : pages Detail (CompanyDetail 1093 / DealDetail 1051 / ContactDetail 733) — **priorité haute**

Même recette pour les 3. Exemple `CompanyDetail.tsx` :

```
components/company/
├── companyUtils.ts             # TYPE_COLORS, formatage, helpers purs
├── CompanyHeader.tsx           # DetailHeader (nom, badges, actions)
├── CompanyInfoCard.tsx         # SideCard infos société
├── CompanyContactsPanel.tsx    # liste contacts liés
├── CompanyDealsPanel.tsx       # deals liés
└── CompanyActivityTimeline.tsx # timeline activités
```
La page ne garde que : hooks `useQuery` + layout `SplitView` + assemblage des panneaux. Cible < 300 lignes/page. Réutilise les primitives UI existantes (`DetailHeader`, `KpiStrip`, `SideCard`, `ActivityTimeline` — cf. `UI_GUIDELINES.md`).

### C.6 — Frontend : `AuditResultPanel.tsx` (601, ~39 sous-fonctions) — **priorité basse**

Composant présentationnel pur (0 hook query). Extraire les sous-panneaux :
`AuditScoreCard.tsx`, `AuditGapList.tsx`, `AuditEngineBreakdown.tsx`, `auditUtils.ts` (formatage/couleurs). Chaque sous-panneau reçoit ses props typées.

### C.7 — Frontend : `types/index.ts` (614) — **priorité basse**

Barrel de types. Découpe par domaine (`types/crm.ts`, `types/deals.ts`, `types/activities.ts`) réexportés par `types/index.ts`. **Faible ROI** (fichier plat, pas de logique) — à faire seulement si l'IDE rame ou lors d'un passage sur la zone.

### C.8 — Frontend : `GEO.tsx` (633) — **priorité basse (déjà en cours)**

Extraction déjà entamée (1031→633 : `GeoAtoms`, `geoUtils`, `BrandSelector`, `BrandModal`, `PromptsModal`). Poursuivre : extraire `GeoReportView.tsx` (panneau résultats) sur le modèle de `TrendReportView.tsx`. Cible < 350 lignes.

---

## Partie D — Feuille de route recommandée

Ordre par ROI (impact lisibilité/testabilité ÷ risque). Chaque item = 1 PR iso-comportement, ≤ 5 fichiers, validé quality-enforcer (règle DC15 : phaser les refactors > 5 fichiers).

| Ordre | Cible | Effort | Risque | Justification |
|-------|-------|--------|--------|---------------|
| 1 | `integrations.py` → 3 routers | M | Faible | 3 responsabilités nettes, endpoints externes → isolation = sécurité |
| 2 | `geo.py` → 4 routers | M | Faible | 18 routes ingérables dans 1 fichier |
| 3 | `CompanyDetail` + `DealDetail` + `ContactDetail` | L (3 PR) | Faible | pattern déjà rodé, gros gain lisibilité |
| 4 | `startup_radar_sync.py` → 3 couches | M | Moyen | touche le sync prod → tests mapper d'abord |
| 5 | `enrichment/orchestrator.py` → modes | M | Moyen | cœur du module enrichissement → couverture de test avant |
| 6 | `AuditResultPanel`, `GEO.tsx` (fin), `types/index.ts` | S | Faible | cosmétique, à l'occasion |

**Règles d'exécution** (DC15) :
- 1 refacto = 1 PR, iso-comportement strict (aucun changement de logique).
- Étape 0 avant chaque refacto d'un fichier > 300 LOC : nettoyer imports/dead code du fichier, committer à part.
- Validation obligatoire par PR : `ruff` + `pytest` (backend) / `tsc` + `eslint` + `vitest` (frontend), scores ≥ référence.
- Ne jamais dépasser 5 fichiers par phase ; re-lire les fichiers clés entre phases.

---

## Points à vérifier manuellement (DC17)

- **`getEnrichmentJob` / `getTrendHealth`** ne sont référencés que par des mocks de test → si on garde la fonction, s'assurer qu'un usage réel est prévu (sinon knip les reflaggera à chaque run). *Fragilité latente, pas un bug.*
- **`integrations.py:137`** — fallback auth `X-Nomo-API-Key` marqué « supprimer après 2026-07-01 » : **la date est passée**. Vérifier que la migration Bearer est complète côté Nomo-IA avant de retirer le fallback (dette technique datée).
- Les 23 constantes documentaires backend gagneraient à devenir des `StrEnum` *utilisés* dans les schémas Pydantic (valide les entrées + supprime le « faux mort ») — chantier optionnel.
