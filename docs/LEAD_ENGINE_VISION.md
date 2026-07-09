# Lead Engine — couche d'orchestration de génération de leads

> Vision métier + design technique. Répond au constat : toutes les briques de
> génération de leads existent dans FGA CRM (sources, enrichissement, scoring,
> qualification, drafts) mais **aucune couche ne les orchestre** — chaque étape
> se déclenche à la main, page par page.
>
> Benchmark : Yuzu Leads. Note de méthode : `yuzuleads.com` est inaccessible aux
> robots (403) et non indexé ; l'analyse s'appuie sur **Yuzuu**
> (https://www.yuzuu.co — « the first revenue engine for marketing agencies »,
> même famille de produit) et les patterns du marché (Clay, Pharow, AI-SDR).
>
> Date : 9 juillet 2026. Statut : **vision validée à challenger — rien n'est codé**.

---

## 1. Ce que fait Yuzu(u) — et pourquoi ce n'est pas notre modèle

### 1.1 Leur workflow

```
Google Maps (commerces locaux) → ICP défini en call d'onboarding
→ scoring par signaux d'intention génériques (reviews non traitées,
  pas de booking en ligne, site incomplet, réseaux inactifs, pas de
  tracking Google Ads)
→ drafts d'outreach email auto + relances automatiques
→ le prospect book lui-même un call (Calendly)
Dashboard : ~350 leads/mois, ~24 RDV/mois, valeur pipeline
```

### 1.2 Ce qui est bien pensé (à garder)

1. **Boucle fermée** : de la source au rendez-vous dans un seul flux, avec un
   funnel mesuré. C'est exactement la couche qui nous manque.
2. **Signal-based, pas liste-based** : on ne prospecte pas « une liste », on
   prospecte « un problème détecté ». Le lead arrive avec sa raison de contact.
3. **File d'attente scorée** : le commercial ouvre une queue priorisée, pas un
   tableur.
4. **Zéro friction** : les drafts sont pré-rédigés, la relance est gérée.

### 1.3 Ce qu'on challenge (et pourquoi notre position est plus forte)

| Yuzu(u) | Notre challenge | Notre atout |
|---|---|---|
| Sourcing Google Maps (commerces locaux) | Hors sujet pour FGA : nos cibles sont des **startups B2B FR post-levée**, invisibles sur Maps | **Startup Radar** détecte les levées multi-sources ; base gouv/SIRENE souveraine (déjà branchée : résolution SIREN, NAF) |
| Signaux d'intention **génériques** (reviews, booking…) — n'importe quel concurrent peut les copier | Un signal copiable n'est pas un avantage | **Signal propriétaire** : score de clarté du message (audit SR /75) + GEO-readiness. « Cette startup vient de lever ET son message est mesurablement flou » — personne d'autre ne produit ce croisement |
| Outreach **entièrement automatique** | Risque marque/délivrabilité inacceptable pour un cabinet advisory premium (tickets 999 € → 150 K€) : un email raté coûte plus qu'un lead gagné | Pattern **« Drafts à valider »** déjà en prod : l'IA rédige, l'humain approuve. Human-in-the-loop = qualité constante |
| **Volume-first** (350 leads/mois) | FGA n'a pas la bande passante d'une agence : 350 leads tièdes = du bruit | **Pertinence-first** : 20-30 leads/mois tier A avec angle personnalisé battent 350 génériques, à notre ACV |
| Mono-canal email | Les fondateurs de startups vivent sur LinkedIn | **Unipile/LinkedIn** déjà intégrés dans fga-mcp (V2 UI) |
| ICP figé à l'onboarding (un call) | Le marché bouge | **Trends** mesure la demande en continu ; l'ICP peut suivre les sujets qui montent |

**Conclusion** : on garde leur *forme* (boucle fermée, signal-based, queue
scorée, zéro friction) et on remplace leur *fond* (sourcing, signaux, canal,
degré d'automatisation) par nos atouts propriétaires.

---

## 2. Vision métier — les « Plays »

### 2.1 Concept central

Un **Play** est une recette d'orchestration nommée et versionnée :

```
TRIGGER (signal détecté)
  → CIBLAGE (filtre ICP : secteur, taille, série, exclusions)
    → ENRICHISSEMENT (décideurs CTO/CPO/CMO/CEO + emails vérifiés — Icypeas)
      → SCORING IA (tier A/B/C — workflow scoring existant)
        → ROUTAGE (auto si tier A + confiance haute, sinon revue humaine)
          → ACTION (draft d'outreach contextualisé À VALIDER / deal / tâche)
            → MESURE (funnel par play : signal → enrichi → contacté → répondu → RDV → deal)
```

Trois modes par play : **manuel** (chaque étape validée), **semi-auto**
(pipeline auto jusqu'au draft, envoi validé — mode recommandé), **auto**
(réservé aux plays rodés, jamais pour un premier contact sortant).

### 2.2 Les 4 plays de lancement

| Play | Trigger (signal) | Angle d'outreach | Produit visé |
|---|---|---|---|
| **P1 — Levée fraîche** | SR détecte une levée Seed/Série A < 30 j sur une société fit ICP | « Vous venez de lever : c'est maintenant que votre message doit porter » | audit-999 → advisory |
| **P2 — Message flou** | Audit SR < 30/75 sur une société active du CRM | « Votre clarté de message est mesurée à X/75 — voici ce que ça vous coûte » | audit-999 |
| **P3 — Inbound chaud** | Contact créé par nomo-ia / plein-phare / formulaire (lead_source) | Qualification SPICED auto → fast_track → réponse < 24 h | selon SPICED |
| **P4 — Trend surfer** | Sujet Trends en forte hausse recoupant un segment NAF | Outreach « insight » : partage d'analyse (Observatoire), pas de pitch | nurturing → founder-499 |

P1 × P2 se cumulent : levée fraîche **ET** message flou = lead parfait,
priorité absolue de la queue (c'est le croisement que Yuzu ne peut pas faire).

### 2.3 Le funnel mesuré (état d'un lead dans un play)

```
detected → targeted → enriched → scored → routed → drafted → sent → replied → meeting → deal
```

Chaque play affiche son funnel : où ça fuit, quel angle convertit. Après 3 mois,
on saura si « Levée fraîche » convertit mieux que « Message flou » — et le
pricing du futur Compass Reach s'appuiera sur ces chiffres réels (dogfooding).

### 2.4 Garde-fous non négociables

- **Jamais d'envoi automatique d'un premier contact** : tout outreach sortant
  passe par la file « Drafts à valider » (existante). L'auto-mode ne peut
  automatiser que les étapes *internes* (enrichir, scorer, router, drafter).
- **RGPD** : emails pro nominatifs uniquement (pipeline Icypeas existant),
  suppression list respectée à chaque étape (existante), mention de la source
  du contact dans chaque draft (intérêt légitime B2B), opt-out honoré.
- **Budgets bornés** : plafonds de crédits Icypeas et d'appels LLM par play et
  par jour (quota journalier existant + `ai_workflow_runs`).
- **Dédup** : un signal déjà traité (même société, même type, fenêtre 90 j) ne
  redéclenche pas ; un contact déjà en séquence n'est pas re-ciblé.

---

## 3. UI dédiée — module « Lead Engine »

Nouvelle entrée **Lead Engine** dans le groupe **Marketing** de la sidebar
(managers/admins ; les sales voient la queue et les drafts qui leur sont routés).

### 3.1 Écran 1 — Vue d'ensemble (landing du module)

```
┌─ Lead Engine ────────────────────────────────────────────────────────┐
│ [KPI strip] Signaux 7j · Leads enrichis · Tier A · Drafts en attente │
│             · Envoyés · Réponses · RDV · Deals générés               │
├──────────────────────────────────────────────────────────────────────┤
│ ┌─ Funnel par play ────────────┐  ┌─ File d'attente (queue) ───────┐ │
│ │ P1 Levée fraîche  12→8→5→2   │  │ ● Sopht (A·82) levée+audit 28  │ │
│ │ P2 Message flou    9→6→4→1   │  │ ● Beams (A·78) levée fraîche   │ │
│ │ P3 Inbound         5→5→3→2   │  │ ● Acme  (B·64) message flou    │ │
│ │ P4 Trend surfer    —         │  │   [Ouvrir] [Drafter] [Écarter] │ │
│ └──────────────────────────────┘  └────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

La **queue** est la vue de travail quotidienne : leads priorisés
(tier × fraîcheur du signal), chacun avec sa raison (« levée Série A il y a
12 j + audit 28/75 ») et ses actions 1-clic.

### 3.2 Écran 2 — Signal Inbox

Flux chronologique des signaux détectés, avant tout traitement :

```
● il y a 2 h   Levée détectée — Sopht (Série A, 4,5 M€)      [Lancer P1] [Ignorer]
● il y a 5 h   Audit bas — Acme (28/75)                       [Lancer P2] [Ignorer]
● hier         Inbound nomo-ia — Léa Martin (CTO, Beams)      [P3 auto ✓ qualifiée fast_track]
● il y a 2 j   Trend +140 % — « agent ia sdr » (NAF 5829C)    [Explorer]
```

Un signal ignoré est mémorisé (pas de re-nag). Un play en mode semi-auto/auto
consomme ses signaux sans intervention et l'inbox montre le résultat.

### 3.3 Écran 3 — Plays

Liste des plays (statut actif/pause, mode, funnel 30 j) + **éditeur de play** :
un formulaire structuré en 5 blocs verticaux (Trigger / Ciblage /
Enrichissement / Scoring & routage / Action) — délibérément **pas un canvas
node-based** type n8n : 4 plays bien faits valent mieux qu'un builder générique
que personne ne maîtrise. Le canvas est un piège d'over-engineering à notre
échelle.

### 3.4 Écran 4 — File de validation

Réutilise et unifie l'existant : **Drafts à valider** (emails d'outreach
générés) + contacts `human_review` (qualification). Une seule file, avec le
contexte du play et du signal à côté de chaque draft (pourquoi ce lead,
pourquoi cet angle).

### 3.5 Écran 5 — Runs

Historique des exécutions par play (pattern de la table des jobs
d'enrichissement) : statut, compteurs par étape, erreurs, crédits consommés.

---

## 4. Stack technique — existant vs rajouts

### 4.1 Ce qu'on a déjà (réutilisé tel quel)

| Brique | État |
|---|---|
| **Sources / triggers** : sync Startup Radar (levées multi-sources, `funding_*`), intégrations nomo-ia & plein-phare (inbound, `lead_source`), audits SR (score /75 dérivé), Trends (+ recommandations LLM), GEO | ✅ prod |
| **Enrichissement** : Icypeas (find-people décideurs + find-email + verify), modes company/batch/ICP/source/contacts, bulk webhook, freshness Redis, quota journalier, RGPD pro-only, suppression list | ✅ prod |
| **Intelligence** : scoring deals (tier A/B/C), qualification SPICED (fast_track → deal auto), insights hebdo, audit `ai_workflow_runs`, kill switch | ✅ prod (PR #47-49) |
| **Actionnement** : Drafts à valider (revue humaine), templates + envoi email SMTP, tâches, activités, pipeline | ✅ prod |
| **Infra** : Celery + Redis (jobs async, beat), Alembic, multi-tenant org-scopé, MCP 32 tools (dont **Unipile/LinkedIn**) | ✅ prod |

**~80 % du Lead Engine existe déjà.** La valeur du module est la couche
d'orchestration + l'UI, pas de nouvelles briques lourdes.

### 4.2 Les rajouts nécessaires

| # | Rajout | Description | Taille |
|---|---|---|---|
| 1 | **Modèles** `LeadSignal`, `LeadPlay`, `PlayRun`, `PlayLead` | Signal détecté (dédupliqué, org-scopé) ; recette de play (config JSONB versionnée) ; exécution ; état d'un lead dans le funnel (machine à états `detected→…→deal`) | 1 migration |
| 2 | **Détecteur de signaux** (Celery beat) | Scan périodique : nouvelles levées SR non traitées, audits < seuil, inbound non qualifié, trends en hausse → `LeadSignal` + déclenchement des plays en mode auto/semi-auto | ~1 j |
| 3 | **Orchestrateur de play** | Chaîne les briques existantes avec checkpoint par étape (pattern de l'orchestrateur d'enrichissement) : enrich → score → qualify → draft. Reprise sur erreur, budgets bornés | ~1,5 j |
| 4 | **Workflow IA `outreach-v1`** | 4ᵉ workflow du socle `ai_workflows` : génère le draft d'outreach contextualisé par le signal (levée/audit/trend) + le play, sortie dans Drafts à valider. Même patterns (JSON strict, prompt versionné, runs) | ~0,5 j |
| 5 | **UI Lead Engine** | 5 écrans §3 (vue d'ensemble, inbox, plays, validation unifiée, runs) — patterns UI existants (KpiCard, tables, badges, files) | ~2 j |
| 6 | **Canal LinkedIn** (V2) | Remonter l'adapter Unipile de fga-mcp dans le backend CRM ; type de draft `linkedin_dm` dans la file de validation | V2 |
| 7 | **Booking** (V2) | Lien de RDV dans les drafts (Cal.com self-hosted ou Calendly) + détection du RDV pris (webhook) pour fermer le funnel | V2 |

Aucune dépendance externe nouvelle en V1 (OpenAI, Icypeas, SR, Redis, Celery
déjà en place).

### 4.3 Phasage proposé

- **V1 (~5 j)** — Signal Inbox + queue + **P1/P2/P3 câblés** (plays définis en
  config, éditeur minimal pause/mode/seuils) + workflow `outreach-v1` + file de
  validation unifiée + funnel. Objectif : premiers drafts « levée fraîche »
  validés et envoyés en semaine 1.
- **V2 (~3 j)** — P4 Trends, éditeur de play complet, LinkedIn (Unipile),
  booking, relances J+3/J+7 (séquence courte, toujours drafts-first).
- **V3 (Compass Reach)** — séquenceur multicanal complet, multi-boîtes,
  warm-up : ce module devient la préfiguration mesurée de Compass Reach, avec
  les taux de conversion réels de FGA comme preuve.

### 4.4 Risques et points de vigilance

- **Délivrabilité email** : volumes faibles en V1 (< 30/semaine) → OK sur le
  SMTP OVH actuel ; au-delà, domaine d'envoi dédié + warm-up (V2/V3).
- **Qualité des drafts** : mesurer le taux d'édition avant envoi (si l'humain
  réécrit tout, le prompt `outreach-v1` doit itérer → `-v2`).
- **Fatigue de la cible** : dédup 90 j inter-plays obligatoire (une société
  touchée par P1 est exclue de P2 pendant la fenêtre).
- **LinkedIn** : rester dans les limites Unipile/LinkedIn (quotas d'invitations)
  — jamais d'automatisation d'envoi sans validation en V1/V2.

---

## 5. Résumé exécutif

Yuzu(u) a raison sur la **forme** : une boucle fermée signal → outreach → RDV,
mesurée, sans friction. Il a tort (pour nous) sur le **fond** : sourcing
générique, signaux copiables, automatisation aveugle, volume avant pertinence.

Le Lead Engine FGA inverse ces choix : **signaux propriétaires** (levées SR ×
clarté du message ×  Trends), **souveraineté des données** (gouv/SIRENE),
**human-in-the-loop** sur tout contact sortant, **pertinence d'abord** — le
tout en orchestrant des briques dont ~80 % sont déjà en production. La couche
manquante est mince : 4 modèles, un détecteur de signaux, un orchestrateur,
un 4ᵉ workflow IA et 5 écrans.

C'est aussi un actif stratégique : chaque play mesuré est un argument
commercial pour Compass (« voici notre propre funnel, chiffré »), et le module
migrera tel quel dans Compass Pipeline/Reach.

---

*Sources : [Yuzuu](https://www.yuzuu.co/) (produit analysé — yuzuleads.com
inaccessible aux robots), [Yuzu Labs](https://www.yuzulabs.io/),
[Pharow](https://www.pharow.com/), patterns Clay/AI-SDR du marché.*
