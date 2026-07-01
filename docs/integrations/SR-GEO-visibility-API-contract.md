# Contrat d'API — Mesure de visibilité GEO (FGA-CRM ← Startup Radar)

> **Destinataire : équipe Startup Radar.**
> Ce document décrit l'API exposée par **FGA-CRM** que Startup Radar appelle pour
> enrichir l'audit détaillé avec une **mesure réelle de visibilité** dans les moteurs
> génératifs. SR fabrique les prompts (il a déjà le contexte de l'audit), les envoie
> à FGA-CRM qui exécute la recherche et renvoie le résultat.
>
> **SR ne stocke rien côté CRM** au-delà de l'appel. FGA-CRM gère la mesure, le cache
> et le coût.
>
> Version du contrat : **v1** · Statut : proposition à valider · Base URL prod :
> `https://crm.fast-growth.fr/api/v1`

---

## 1. Vue d'ensemble

```
Audit SR détaillé (schema.org, FAQ, titres-questions, contenus…)
        │  SR fabrique 3 prompts d'acheteur à partir du contexte
        ▼
  POST /geo/audit-visibility   ──►  FGA-CRM crée une marque éphémère,
        │                            lance 1 run Perplexity sur les 3 prompts
        │  { audit_id }
        ▼
  GET /geo/audit-visibility/{audit_id}  (polling ~toutes les 3 s)
        │
        ▼
  { visible: false, visibility_rate: 0, competitors_found: [...],
    summary: "0/3 — invisible sur Perplexity" }
        │
        ▼
  SR intègre le résultat dans l'audit → argument de vente
```

- **Moteur** : Perplexity uniquement (v1).
- **Asynchrone** : la mesure prend ~15–30 s (3 prompts + extraction). SR appelle POST
  puis **poll** GET jusqu'à `status = completed`.
- **Coût** : supporté par FGA-CRM (clés API côté CRM). D'où le cache + les quotas (§6).

---

## 2. Authentification

Toutes les requêtes exigent une **clé de service** fournie par FGA (Hervé la génère
dans le CRM et vous la transmet). Elle porte le scope `geo:audit`.

```
Authorization: Bearer crm_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

- Format : `crm_` suivi de 32 octets hex.
- Sans clé valide → **401**. Clé sans le scope `geo:audit` → **403**.
- La clé est un secret : à stocker côté SR en variable d'environnement, jamais en clair
  dans le code ni les logs.

---

## 3. Endpoint — Lancer une mesure

### `POST /geo/audit-visibility`

Crée une mesure de visibilité et renvoie un `audit_id` à poller.

**Request body** (JSON) :

| Champ | Type | Requis | Contraintes |
|---|---|---|---|
| `company_name` | string | ✅ | 1–255 car. |
| `domain` | string | ✅ | 1–255 car. (ex. `acme.com`, sans `https://`) |
| `aliases` | string[] | — | ≤ 10 éléments, chacun ≤ 255 car. Variantes de nom pour la détection (ex. `["Acme", "Acme Corp"]`) |
| `prompts` | string[] | ✅ | **1 à 5** éléments, chacun 1–1000 car. (SR envoie ses 3 prompts) |
| `country` | string | — | défaut `FR`, ≤ 8 car. |
| `language` | string | — | défaut `fr`, ≤ 8 car. |
| `refresh` | bool | — | défaut `false`. `true` force une nouvelle mesure même si un résultat récent existe en cache |

> **Détection de la marque** : la présence de l'entreprise dans les réponses est
> détectée par `company_name` **+** `aliases`. Fournir des aliases pertinents améliore
> nettement le rappel (nom commercial, acronyme, nom sans suffixe juridique…).

**Exemple** :

```bash
curl -X POST https://crm.fast-growth.fr/api/v1/geo/audit-visibility \
  -H "Authorization: Bearer crm_xxx" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Acme Corp",
    "domain": "acme.com",
    "aliases": ["Acme", "AcmeCorp"],
    "prompts": [
      "Quel est le meilleur logiciel de gestion de projet pour PME ?",
      "Meilleurs outils de collaboration B2B en France ?",
      "Quelle solution SaaS pour piloter des équipes distribuées ?"
    ],
    "country": "FR",
    "language": "fr"
  }'
```

**Response `200`** :

```json
{ "audit_id": "9b8e1f0c-…", "status": "queued", "cache_hit": false }
```

- `cache_hit = true` + `status = "completed"` → un résultat récent identique existait
  (§6) : passez directement au GET, le résultat est déjà disponible.

**Erreurs** : `401` (pas de clé) · `403` (scope manquant) · `422` (validation :
prompts vides / trop longs, domain manquant…) · `429` (quota dépassé, §6).

---

## 4. Endpoint — Récupérer le résultat (polling)

### `GET /geo/audit-visibility/{audit_id}`

**Response `200`** :

```json
{
  "audit_id": "9b8e1f0c-…",
  "status": "completed",
  "engine": "perplexity",
  "company_name": "Acme Corp",
  "domain": "acme.com",
  "created_at": "2026-07-01T17:10:00Z",
  "result": {
    "visible": false,
    "runs_total": 3,
    "runs_completed": 3,
    "mentions": 0,
    "visibility_rate": 0.0,
    "best_position": null,
    "recommended": false,
    "sentiment": null,
    "competitors_found": [
      { "name": "HubSpot", "mentions": 2 },
      { "name": "monday.com", "mentions": 2 },
      { "name": "Asana", "mentions": 1 }
    ],
    "per_prompt": [
      { "prompt": "Quel est le meilleur logiciel…", "mentioned": false, "position": null },
      { "prompt": "Meilleurs outils de collaboration…", "mentioned": false, "position": null },
      { "prompt": "Quelle solution SaaS…", "mentioned": false, "position": null }
    ],
    "summary": "0/3 — Acme Corp n'apparaît dans aucune réponse Perplexity ; les acteurs cités sont HubSpot, monday.com, Asana."
  }
}
```

- **`status`** : `queued` → `running` → `completed` (ou `failed`).
- **`result`** vaut `null` tant que `status ≠ completed`.
- **`404`** si `audit_id` inconnu.

### Signification des champs `result`

| Champ | Sens |
|---|---|
| `visible` | `true` si la marque est citée dans ≥ 1 réponse |
| `mentions` / `runs_total` | nombre de réponses citant la marque / nombre total de mesures |
| `visibility_rate` | `mentions / runs_total × 100` (%) |
| `best_position` | meilleur rang d'apparition (1 = citée en premier), `null` si absente |
| `recommended` | `true` si l'IA la met activement en avant dans ≥ 1 réponse |
| `sentiment` | `positif` / `neutre` / `negatif` / `null` (si absente) |
| `competitors_found` | marques citées **à la place** (matière pour l'argumentaire concurrentiel) |
| `per_prompt` | détail prompt par prompt |
| `summary` | **phrase prête à l'emploi** pour l'audit / le pitch |

---

## 5. Protocole de polling recommandé

```
POST → audit_id
répéter GET toutes les 3 s :
  status ∈ {queued, running} → continuer
  status = completed         → utiliser result
  status = failed            → afficher un fallback, ne pas bloquer l'audit
timeout conseillé : 60 s (au-delà, considérer failed et continuer l'audit sans la mesure)
```

Si `cache_hit = true` au POST, le premier GET renvoie déjà `completed`.

---

## 6. Cache, coût et quotas

- **Cache** : une mesure pour un même `domain` + mêmes `prompts` + même moteur est
  **mise en cache 30 jours**. Un POST identique dans cette fenêtre renvoie
  `cache_hit = true` sans re-facturer d'appels IA. Utiliser `refresh: true` pour forcer.
- **Quota** : un plafond quotidien par clé (valeur communiquée avec la clé, ex. 100
  mesures/jour). Dépassement → `429` avec `Retry-After`.
- **Bonnes pratiques SR** : ne lancer la mesure que pour les audits qui en ont besoin
  (pas en masse systématique), et réutiliser le cache (ne pas envoyer `refresh: true`
  par défaut).

---

## 7. Codes d'erreur

| Code | Cause | Action SR |
|---|---|---|
| `401` | Clé absente / invalide | Vérifier `Authorization` |
| `403` | Clé sans scope `geo:audit` | Demander une clé correctement scopée |
| `422` | Body invalide (prompts, domain…) | Corriger la requête (voir `detail`) |
| `404` | `audit_id` inconnu | Vérifier l'id retourné par le POST |
| `429` | Quota dépassé | Respecter `Retry-After`, réessayer plus tard |
| `5xx` | Erreur serveur | Réessayer avec backoff ; ne pas bloquer l'audit |

---

## 8. Notes de version (v1)

- Moteur **Perplexity** uniquement. (OpenAI/Google AIO possibles en v2 si besoin.)
- `n_runs = 1` par prompt (une passe). La variance IA existe : un résultat « 0/3 » est
  un signal fort, un « 1/3 » est à lire comme « visibilité faible/instable ».
- Le résumé (`summary`) est en français, calibré pour un usage direct dans l'audit.
- Les marques créées pour l'audit sont **éphémères** côté CRM (non visibles dans le
  dashboard GEO de FGA) et purgées automatiquement.

---

## 9. Ce que SR doit implémenter (récap)

1. À la fin de l'audit détaillé, **fabriquer 3 prompts d'acheteur** à partir du contexte
   déjà extrait (positionnement, secteur, recommandations).
2. `POST /geo/audit-visibility` avec `company_name`, `domain`, `aliases`, `prompts`.
3. **Poller** `GET /geo/audit-visibility/{audit_id}` jusqu'à `completed` (timeout 60 s).
4. Intégrer `result` dans l'audit (score de visibilité réel + concurrents + `summary`).
5. Gérer les erreurs (401/403/422/429/5xx) sans bloquer l'audit.

> Contact FGA pour la clé de service (`crm_…`, scope `geo:audit`) et la valeur du quota.
