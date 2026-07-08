# Workflows IA natifs — FGA CRM

> Implémentation de la spec `spec-workflows-ia-fga-crm.md` (juillet 2026).
> Livré en 4 slices : PR #47 (socle + scoring), #48 (qualification), #49 (insights),
> fga-mcp `e308ac5` (tools MCP). Ce document décrit **ce qui est en production**,
> y compris les écarts assumés vs la spec d'origine (§8).

## 1. Principe d'architecture

La logique IA vit **dans le backend FGA CRM**, pas dans Claude Desktop : le CRM
déclenche, le CRM stocke, le CRM affiche. Le serveur `fga-mcp` expose les mêmes
endpoints en tools MCP — un seul code, deux surfaces d'usage.

```
UI FGA CRM (boutons Scorer / Qualifier / carte Insights)
        │
        ▼
Backend FastAPI — app/api/v1/ai_workflows.py
   ├── POST /deals/{id}/score          ──┐
   ├── POST /contacts/{id}/qualify       ├──► OpenAI (structured outputs, JSON strict)
   └── GET  /insights/weekly           ──┘         │
        │                                          │
        ▼                                          ▼
   Colonnes dédiées (deals.ai_*,          Signaux lus EN BASE uniquement :
   contacts.ai_*, table ai_insights)      audit SR (dérivé), funding, activités
        │
        └── ai_workflow_runs : audit org-scopé de chaque appel
            (workflow, cible, prompt_version, model, tokens, statut)

fga-mcp : crm_score_deal / crm_qualify_contact / crm_get_insights
          → appellent ces mêmes endpoints (auth JWT auto-login existante)
```

Règles communes (implémentées) :
1. Sortie JSON **stricte** : schéma Pydantic envoyé en `response_format`
   (`services/openai_strict.py`, partagé avec GEO/Trends) et **validé au parse**.
   Jamais de parsing texte fragile.
2. Rien d'inventable : tout signal absent va dans `missing_signals` / `unknown`.
3. Chaque résultat porte `model` + `prompt_version` + date (auditabilité).
4. Échec LLM → l'entité reste **intacte**, run d'échec tracé, HTTP 502.
   Le CRM reste fonctionnel.

## 2. Configuration

```bash
# .env backend — réutilise la clé OpenAI existante (stack LLM unique)
OPENAI_API_KEY=sk-...            # déjà utilisée par GEO/Trends
AI_WORKFLOWS_ENABLED=true        # kill switch global (503 si false)
AI_WORKFLOWS_MODEL=gpt-4o-mini   # défaut ; configurable
AI_SCORE_TTL_DAYS=7              # cache du score deal
```

Décision : **OpenAI pour l'instant** (cohérence avec la stack existante, zéro
nouvelle clé). Le client est derrière `services/ai_workflows/client.py` — une
bascule Anthropic ultérieure ne toucherait que ce module.

## 3. Workflow 1 — Lead Scoring (`POST /deals/{id}/score`)

Score 0-100 + tier A/B/C, décomposé **Fit /50 · Intent /30 · Message /20**.
Tiers : A ≥ 70, B ≥ 40, C sinon. Prompt versionné **`scoring-v1`**
(`services/ai_workflows/scoring.py`).

Signaux — **100 % lus en base**, aucun appel externe hors LLM :

| Famille | Source |
|---|---|
| Fit ICP | Company : secteur, taille, pays, levée (date/montant/série), provenance |
| Opportunité message | Score d'audit SR **/75** + flags messaging/détaillé/GEO — champs **dérivés** via `_fetch_audit_flags` (réutilisé des routes companies) |
| Intent | 20 dernières activités du deal + du contact (type, sujet, date, récence) |

- Colonnes : `deals.ai_score`, `ai_tier` (indexé), `ai_score_rationale`,
  `ai_score_missing` (JSONB), `ai_scored_at`, `ai_score_meta`
  ({model, prompt_version, recommended_product, fit/intent/message_points}).
  Et `deals.product` (`audit-999 | founder-499 | advisory`, indexé).
- **Cache** : un score < `AI_SCORE_TTL_DAYS` (7 j) est servi tel quel
  (`cached: true`), sauf `?force_rescore=true`.
- RBAC : tous les rôles ; un `sales` ne score que **ses** deals (403 sinon),
  cross-org → 404.
- UI : carte **« Score IA »** sur la fiche deal (`DealScoreCard`), colonne
  **« Score IA »** (badge tier) dans le Pipeline.

## 4. Workflow 2 — Qualification SPICED (`POST /contacts/{id}/qualify`)

Grille SPICED (situation / pain / impact / critical_event / decision), chaque
dimension `{value, source}` — `unknown` si non traçable à une donnée fournie.
Prompt versionné **`qualif-v1`** (`services/ai_workflows/qualification.py`).

Routages (jamais de disqualification automatique) :

| Routage | Condition | Effet |
|---|---|---|
| `fast_track` | pain/échéance explicite + décisionnaire + fit ICP | **Deal créé automatiquement** : stage `new`, produit suggéré, owner = déclencheur |
| `standard` | fit probable, dimensions clés unknown | — |
| `human_review` | signaux contradictoires / hors ICP / données insuffisantes | File de revue |

- Body optionnel : `{"submission_text": "..."}` (formulaire/email brut, max 4000).
- Colonnes : `contacts.ai_qualification` (JSONB), `ai_routing` (indexé),
  `ai_qualified_at`. Pas de cache : re-qualifier est une action explicite.
- **File « À revoir »** : `GET /contacts?ai_routing=human_review`
  (filtre « Routage IA » sur la liste Contacts).
- UI : carte **« Qualification IA »** sur la fiche contact
  (`ContactQualificationCard`) avec lien vers le deal créé.
- Déclenchement automatique sur webhook de formulaire : **V2** — point
  d'ancrage naturel : les intégrations nomo / plein-phare qui créent déjà
  les contacts inbound (`lead_source`).

## 5. Workflow 3 — Sales Insights (`GET /insights/weekly`)

Synthèse du pipeline en langage naturel : santé vs période précédente, deals
stagnants, patterns de perte, **3 actions prioritaires max**, caveats.
Prompt versionné **`insights-v1`** (`services/ai_workflows/insights.py`).

- Agrégats calculés en base (org-scopés) = **seule source de chiffres du LLM** :
  pipeline par stage, nouveaux deals période vs précédente, deals par produit,
  perdus avec `loss_reason`, stagnants. Règle : < 5 deals → le dire
  (`data_caveats`) au lieu de forcer un pattern.
- **Seuils de stagnation par stage réel** (jours sans activité, sinon dernière
  mise à jour) : `new` 14 · `contacted` 10 · `meeting` 10 · `proposal` 7 ·
  `negotiation` 7.
- Persistance : table **`ai_insights`** (org-scopée, historisée). La synthèse
  < 24 h est servie du cache (`cached: true`) ; `?refresh=true` régénère.
- **RBAC : manager+ uniquement** — la synthèse porte sur le pipeline de l'org
  entière ; l'exposer à un `sales` (qui ne voit que ses deals ailleurs)
  violerait l'ownership.
- UI : carte **« Insights IA — pipeline »** sur le Dashboard (`InsightsCard`),
  visible managers/admins, bouton **Actualiser**.

## 6. Audit des appels — `ai_workflow_runs`

Chaque appel LLM est tracé (org-scopé) : `workflow` (scoring | qualification |
insights), `target_type`/`target_id`, `prompt_version`, `model`,
`input_tokens`/`output_tokens`, `status` (`ok | parse_error | api_error`),
`error`. Sert au débogage, au suivi des coûts et à l'itération des prompts.

Coût estimé au volume actuel : **< 5 €/mois** (gpt-4o-mini, ~3K tokens in /
500 out par appel). Le kill switch protège d'un emballement.

## 7. Tools MCP (`fga-mcp`)

`src/fga_mcp/tools/crm_ai_tools.py` — scope `mcp:crm`, adapter CRM existant
(auth JWT auto-login) :

| Tool | Endpoint appelé |
|---|---|
| `crm_score_deal(deal_id, force_rescore)` | `POST /deals/{id}/score` |
| `crm_qualify_contact(contact_id, submission_text)` | `POST /contacts/{id}/qualify` |
| `crm_get_insights(period_days, refresh)` | `GET /insights/weekly` (manager+) |

La stack fga-mcp passe à **32 tools**. Redémarrer le serveur MCP après mise à
jour pour que Claude Desktop les voie.

## 8. Écarts assumés vs la spec d'origine

| Spec d'origine | Implémenté | Pourquoi |
|---|---|---|
| Anthropic (claude-sonnet) + parsing ```json | **OpenAI structured outputs** | Stack LLM unique déjà en prod (GEO/Trends) ; parsing strict plus robuste ; bascule possible via `client.py` |
| Stages `lead` / `qualified` | Stages **réels** (`new`, `contacted`, …) | `DEAL_STAGES` du domaine — `qualified` n'existe pas (fast_track → `new`) |
| Appels live Startup Radar / PPD pour les signaux | **Lecture DB** (audit dérivé, funding, activités) | Les données SR sont déjà synchronisées en base ; zéro dépendance réseau au scoring |
| `ai_workflow_runs` sans isolation | **org-scopée** (`organization_id` partout, y c. `ai_insights`) | Multi-tenant = fondation Compass |
| Insights pour tous | **manager+** | Vue pipeline org entière vs ownership sales |
| Table `ai_insights_cache` éphémère | Table `ai_insights` **historisée** | La dernière synthèse reste affichable après 24 h ; l'historique sert la calibration |
| Enrichir `GET /deals/stats` (prérequis §2.2C) | Agrégats calculés **dans le service insights** | Pas de régression de contrat sur l'endpoint public ; à enrichir si le MCP en a besoin directement |

## 9. Calibration et itération des prompts

Les prompts sont versionnés dans le code (`scoring-v1`, `qualif-v1`,
`insights-v1`) et chaque résultat/run porte sa version. Processus d'itération :

1. Scorer 15-20 deals réels, comparer les tiers au jugement humain.
2. Qualifier les derniers inbound réels (avec `submission_text` si dispo).
3. Si un biais systématique apparaît → modifier le prompt **et** incrémenter
   la version (`scoring-v2`) ; les anciens résultats restent identifiables.

## 10. Fichiers clés

```
backend/app/services/ai_workflows/   client.py, runs.py, scoring.py,
                                     qualification.py, insights.py
backend/app/api/v1/ai_workflows.py   les 3 endpoints (routes absolues)
backend/app/schemas/ai_workflows.py  sorties LLM strictes + réponses API
backend/app/models/ai_workflow.py    AiWorkflowRun, AiInsight
backend/alembic/versions/            ai_scoring_001, ai_qualification_001,
                                     ai_insights_001
backend/tests/api/test_ai_workflows.py   13 tests (LLM mocké)
frontend/src/components/pipeline/DealScoreCard.tsx
frontend/src/components/contact/ContactQualificationCard.tsx
frontend/src/components/dashboard/InsightsCard.tsx
fga-mcp/src/fga_mcp/tools/crm_ai_tools.py   (+ tests/test_crm_ai_tools.py)
```
