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
> Date : 9 juillet 2026. Statut : **V1 livrée** (PR #53 + #55) — Signal Inbox,
> détecteur P1/P2/P3 (mmf_gap, funding_detected, inbound_new), queue priorisée
> gap × fraîcheur des fonds, workflow `outreach-v1` (draft → relecture →
> composer, envoi humain), funnel par play. V2 (§4.3) : P4 Trends, éditeur de
> plays, LinkedIn (Unipile), booking, relances.

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
| Sourcing Google Maps (commerces locaux) | Hors sujet pour FGA : nos cibles sont des **startups B2B FR**, invisibles sur Maps | **Startup Radar** détecte les startups et leurs levées multi-sources ; base gouv/SIRENE souveraine (déjà branchée : résolution SIREN, NAF) |
| Signaux d'intention **génériques** (reviews, booking…) — n'importe quel concurrent peut les copier | Un signal copiable n'est pas un avantage | **Signal propriétaire = le Message-Market Fit mesuré** : score de clarté du message (audit SR /75) + GEO-readiness. C'est LE driver — le problème que FGA vend. La levée de fonds n'est qu'un **qualificateur de solvabilité** (la startup a-t-elle le budget ?), jamais un déclencheur d'outreach |
| Outreach **entièrement automatique** | Risque marque/délivrabilité inacceptable pour un cabinet advisory premium (tickets 999 € → 150 K€) : un email raté coûte plus qu'un lead gagné | Pattern **« Drafts à valider »** déjà en prod : l'IA rédige, l'humain approuve. Human-in-the-loop = qualité constante |
| **Volume-first** (350 leads/mois) | FGA n'a pas la bande passante d'une agence : 350 leads tièdes = du bruit | **Pertinence-first** : 20-30 leads/mois tier A avec angle personnalisé battent 350 génériques, à notre ACV |
| Mono-canal email | Les fondateurs de startups vivent sur LinkedIn | **Unipile/LinkedIn** déjà intégrés dans fga-mcp (V2 UI) |
| ICP figé à l'onboarding (un call) | Le marché bouge | **Trends** mesure la demande en continu ; l'ICP peut suivre les sujets qui montent |

**Conclusion** : on garde leur *forme* (boucle fermée, signal-based, queue
scorée, zéro friction) et on remplace leur *fond* (sourcing, signaux, canal,
degré d'automatisation) par nos atouts propriétaires.

---

## 2. Vision métier — les « Plays »

### 2.0 Hiérarchie des signaux : le MMF est le driver

Règle métier structurante (à ne jamais inverser) :

- **Driver (déclencheur d'outreach)** : le **Message-Market Fit (MMF)** — la
  clarté du message mesurée (audit SR /75, GEO-readiness). C'est le problème
  que FGA résout ; c'est donc le seul signal qui justifie un premier contact.
- **Qualificateurs (jamais déclencheurs)** : la **levée de fonds** dit si la
  startup **a les moyens de payer** (budget, timing) ; le secteur/taille disent
  si elle est dans l'ICP. Ils filtrent et priorisent, ils ne déclenchent pas.

Une levée détectée ne déclenche donc **pas un outreach** : elle déclenche
**un audit du message**. Si l'audit révèle un MMF gap, alors — et seulement
alors — le lead entre dans le play d'outreach, avec une priorité boostée par
la fraîcheur des fonds.

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

| Play | Trigger (signal) | Rôle | Angle d'outreach | Produit visé |
|---|---|---|---|---|
| **P1 — MMF Gap** (le play principal) | Audit SR < seuil (ex. 30/75) sur une société fit ICP | **Outreach** | « Votre clarté de message est mesurée à X/75 — voici ce que ça vous coûte » ; si fonds récents : « …et c'est maintenant que votre message doit porter » | audit-999 → advisory |
| **P2 — Nouvel entrant à auditer** | SR détecte une levée / nouvelle startup fit ICP | **Alimentation** (pas d'outreach) : déclenche l'**audit du message** ; si MMF gap → le lead bascule dans P1 avec priorité « fonds frais » | — | — |
| **P3 — Inbound chaud** | Contact créé par nomo-ia / plein-phare / formulaire (lead_source) | Outreach (réponse) | Qualification SPICED auto → fast_track → réponse < 24 h | selon SPICED |
| **P4 — Trend surfer** | Sujet Trends en forte hausse recoupant un segment NAF | Nurturing | Outreach « insight » : partage d'analyse (Observatoire), pas de pitch | nurturing → founder-499 |

La mécanique P2 → P1 est le cœur du système : la levée **alimente** (nouvelles
sociétés à auditer + solvabilité connue), le MMF gap **déclenche**. Le lead
prioritaire de la queue = MMF gap profond × fonds frais — le croisement que
Yuzu ne peut pas produire.

### 2.3 Le funnel mesuré (état d'un lead dans un play)

```
detected → targeted → enriched → scored → routed → drafted → sent → replied → meeting → deal
```

Chaque play affiche son funnel : où ça fuit, quel angle convertit. Après 3 mois,
on saura si les MMF gaps « fonds frais » convertissent mieux que les autres — et le
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
│ │ P1 MMF Gap        12→8→5→2   │  │ ● Sopht (A·82) audit 24/75     │ │
│ │ P2 À auditer       9 audits  │  │   + levée 4,5 M€ il y a 12 j   │ │
│ │ P3 Inbound         5→5→3→2   │  │ ● Acme  (A·76) audit 28/75     │ │
│ │ P4 Trend surfer    —         │  │ ● Beams (B·61) audit 33/75     │ │
│ └──────────────────────────────┘  │   [Ouvrir] [Drafter] [Écarter] │ │
│                                   └────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

La **queue** est la vue de travail quotidienne : leads priorisés par
**profondeur du MMF gap × fraîcheur des fonds**, chacun avec sa raison
(« audit 24/75 · levée Série A il y a 12 j ») et ses actions 1-clic. Le gap
de message s'affiche en premier : c'est lui qu'on vend.

### 3.2 Écran 2 — Signal Inbox

Flux chronologique des signaux détectés, avant tout traitement :

```
● il y a 1 h   MMF gap — Acme : audit 28/75 (fonds : levée 2M€ mars)  [Lancer P1] [Ignorer]
● il y a 2 h   Levée détectée — Sopht (Série A, 4,5 M€)      [Auditer le message → P2] [Ignorer]
● il y a 6 h   Audit terminé — Sopht : 24/75 → MMF gap        [P1 prêt : Drafter]
● hier         Inbound nomo-ia — Léa Martin (CTO, Beams)      [P3 auto ✓ qualifiée fast_track]
● il y a 2 j   Trend +140 % — « agent ia sdr » (NAF 5829C)    [Explorer]
```

Le cycle Sopht illustre la mécanique : la levée déclenche **l'audit** (P2),
le résultat d'audit (24/75) crée le **signal MMF gap** qui déclenche
l'outreach (P1) — jamais l'inverse.

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
| 2 | **Détecteur de signaux** (Celery beat) | Scan périodique : audits < seuil (**MMF gap = signal d'outreach**), nouvelles levées/startups SR fit ICP (→ **déclenche l'audit du message**, pipeline SR existant), inbound non qualifié, trends en hausse → `LeadSignal` + déclenchement des plays en mode auto/semi-auto | ~1 j |
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
  validation unifiée + funnel. Objectif : premiers drafts « MMF gap » validés
  et envoyés en semaine 1 (chaîne complète P2 → audit → P1).
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

Le Lead Engine FGA inverse ces choix. Son driver est le **Message-Market Fit
mesuré** : le MMF gap (audit SR bas) est le **seul déclencheur d'outreach** —
c'est le problème que FGA vend. La levée de fonds joue son vrai rôle :
**qualifier la solvabilité** et alimenter le flux d'audits (P2 → P1), jamais
déclencher un contact. S'y ajoutent la **souveraineté des données**
(gouv/SIRENE), le **human-in-the-loop** sur tout contact sortant et la
**pertinence d'abord** — le tout en orchestrant des briques dont ~80 % sont
déjà en production. La couche manquante est mince : 4 modèles, un détecteur
de signaux, un orchestrateur, un 4ᵉ workflow IA et 5 écrans.

C'est aussi un actif stratégique : chaque play mesuré est un argument
commercial pour Compass (« voici notre propre funnel, chiffré »), et le module
migrera tel quel dans Compass Pipeline/Reach.

---

*Sources : [Yuzuu](https://www.yuzuu.co/) (produit analysé — yuzuleads.com
inaccessible aux robots), [Yuzu Labs](https://www.yuzulabs.io/),
[Pharow](https://www.pharow.com/), patterns Clay/AI-SDR du marché.*
