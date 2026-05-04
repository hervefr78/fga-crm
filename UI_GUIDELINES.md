# FGA CRM — UI Guidelines

> Document de référence pour concevoir et implémenter **toute page** du CRM.
> Cible : équipe design + dev front. À garder à jour à chaque évolution majeure de la stack.

**Stack** : React 18 · TypeScript · Tailwind 3.4 · Lucide icons · TanStack Query v5
**Audience produit** : équipes commerciales (sales, BDR, CSM) — usage quotidien intense, lecture rapide, navigation au clavier.
**Ton de la marque** : sérieux, sobre, efficace. **Pas** de gimmick, pas d'emoji, pas de gradients agressifs, pas d'icône décorative. Chaque pixel doit servir.

---

## 1. Principes directeurs

### 1.1 Lecture-first, pas action-first
Une page CRM est consultée 10× plus souvent qu'éditée. La hiérarchie visuelle doit toujours servir la **lecture** : titre → état → KPI → contexte → actions secondaires. Les CTA d'édition se rangent dans le coin haut-droit, jamais au centre.

### 1.2 Information density élevée mais respirante
Les utilisateurs scannent. On préfère un tableau dense bien typographié à une carte visuellement chargée. Espacement vertical entre lignes : 12–16px. Espacement entre groupes : 24–32px.

### 1.3 Cohérence > créativité
Mieux vaut 80% de pages identiques que 100% de pages "originales". Tout pattern récurrent (header de fiche, KPI strip, timeline, tabs, side cards) doit utiliser **les mêmes composants** avec la même API.

### 1.4 Pas de chrome sans contenu
Ne jamais afficher une carte vide. Toujours un empty state explicite + CTA d'amorce.

### 1.5 Realisme > données slop
Pas de stat inventée. Si on n'a pas le chiffre, on affiche `—` (em-dash). Pas de fake percentage, pas de "+12% vs Q1" si la donnée n'existe pas côté backend.

---

## 2. Charte visuelle

### 2.1 Palette

#### Couleur de marque
```
primary-50   #eff6ff
primary-100  #dbeafe
primary-200  #bfdbfe
primary-500  #3b82f6
primary-600  #2563eb   ← bleu signature, CTA principal
primary-700  #1d4ed8
primary-800  #1e40af
primary-900  #1e3a8a
```

#### Neutres (utilisés à 90% du temps)
```
slate-50    #f8fafc   ← fond app
slate-100   #f1f5f9   ← séparateurs, hover
slate-200   #e2e8f0   ← bordures
slate-300   #cbd5e1   ← bordures actives
slate-400   #94a3b8   ← texte tertiaire, icônes inactives
slate-500   #64748b   ← texte secondaire
slate-700   #334155   ← texte body
slate-800   #1e293b   ← titres
slate-900   #0f172a   ← contrastes max
```

#### Sémantique (par état)
| État | Background | Text | Usage |
|---|---|---|---|
| **Success** | `emerald-50` | `emerald-700` | Won, qualifié, score haut |
| **Warning** | `amber-50` | `amber-700` | Proposition, négociation, score moyen |
| **Danger** | `red-50` | `red-600` | Lost, unqualifié, retard |
| **Info** | `blue-50` | `blue-700` | Contacted, en cours |
| **Neutral** | `slate-100` | `slate-600` | New, sans état |
| **AI** | `violet-50/40` → `indigo-50/30` (gradient subtil) | `violet-700` | Suggestions IA |

> **Règle** : pour les badges de stage (Deal), de statut (Contact), d'activité — toujours utiliser une variante du tableau ci-dessus, jamais inventer.

### 2.2 Typographie

```css
font-family: 'Inter', system-ui, sans-serif;
```

| Usage | Class Tailwind | Pixels |
|---|---|---|
| Display (rarement, jamais sur fiches) | `text-3xl font-semibold tracking-tight` | 30 / 36 |
| H1 page (nom de la fiche) | `text-2xl font-semibold tracking-tight` | 24 / 32 |
| H2 section | `text-lg font-semibold` | 18 / 28 |
| H3 carte | `text-sm font-semibold` | 14 / 20 |
| Body | `text-sm leading-relaxed` | 14 / 20 |
| Body small / méta | `text-xs` | 12 / 16 |
| Eyebrow | `text-[11px] uppercase tracking-wider font-medium text-slate-400` | 11 / 16 |
| Tabular numbers (KPI, montants) | ajouter `tabular-nums` | — |

**Règles** :
- `tracking-tight` sur les titres ≥ 18px uniquement
- `text-pretty` ou `text-balance` sur les paragraphes longs (>40 mots)
- Jamais de `font-bold` (700) — on s'arrête à `font-semibold` (600)

### 2.3 Espacements & rayons

```
Padding interne carte : p-4 (16px)
Padding latéral page  : px-7 ou px-8 (28-32px)
Gap entre cartes      : gap-4 (16px)
Gap entre sections    : gap-6 (24px) ou pt-5 + border-t

Radius :
  Petit (badge, input)   : rounded-md (6px)
  Moyen (bouton, carte)  : rounded-lg (8px) / rounded-xl (12px)
  Avatar carré (logo)    : rounded-2xl (16px)
  Avatar circulaire      : rounded-full
```

### 2.4 Bordures & ombres
- Bordure standard : `border border-slate-200` — **pas** `border-slate-300`
- Bordure soft : `border border-slate-100` (séparateurs internes)
- Ombre : `shadow-sm` uniquement (sidebar, header). Jamais `shadow-md+` (impression cheap).
- **Pas** de `ring-*` sauf focus accessibilité.

### 2.5 Iconographie
- Source unique : **lucide-react**
- Taille standard : `w-3.5 h-3.5` (14px) en inline, `w-4 h-4` (16px) dans bouton, `w-5 h-5` (20px) dans nav
- Couleur héritée du parent (`text-slate-400` par défaut, `text-primary-600` actif)
- **Pas** d'icône décorative en H1 ou en eyebrow — l'icône n'arrive qu'en métadonnée (KPI label, side link)

---

## 3. Layout global

### 3.1 Structure
```
┌─ Sidebar 256px ─┬─────────── Main ────────────┐
│                 │ Header 48px (recherche)     │
│ Logo            ├─────────────────────────────┤
│                 │ Page                        │
│ Nav             │ ┌─ List 340px ─┬─ Detail ─┐ │
│                 │ │              │          │ │
│                 │ │              │          │ │
│ User            │ └──────────────┴──────────┘ │
└─────────────────┴─────────────────────────────┘
```

### 3.2 Patterns de page

#### A. Liste pure (Companies, Contacts, Pipeline en mode tableau)
```
[ Toolbar : H1 + count + filtres + actions + recherche globale ]
[ Tableau pleine largeur ]
[ Pagination en bas ]
```

#### B. Fiche détail (Company / Contact / Deal)
```
[ Liste split-view 340px ] [ Toolbar slim 44px ]
                           [ Header : avatar + titre + KPI strip ]
                           [ Grid 2 col : main + sidebar 320px    ]
                             ├─ AI card "Next best action"
                             ├─ Description / Tarification (Deal)
                             ├─ Tabs : Activité | Deals | Contacts | Tâches
                             └─ Side : Liens, Méta, Profil
```

#### C. Vue Kanban (Pipeline en mode board)
```
[ Toolbar : filtres par stage / owner / priorité ]
[ 6 colonnes (new → won) avec cartes drag-and-drop ]
[ Footer par colonne : sum + count ]
```

#### D. Dashboard / Home
```
[ KPI strip 4-6 colonnes ]
[ Grid : 2/3 main (timeline équipe) + 1/3 side (tasks du jour) ]
[ AI card "Next best actions de la semaine" en pleine largeur ]
```

### 3.3 Responsive
Le CRM est **desktop-first**. Breakpoints utiles :
- `xl: 1280px` — layout standard
- `lg: 1024px` — split-view se transforme en liste OU détail (toggle)
- `md: 768px` — nav devient drawer, sidebar de fiche passe sous le main
- `<md` — non prioritaire (mobile = lecture seule, pas d'édition)

---

## 4. Composants

### 4.1 Atomiques (déjà existants — `components/ui/`)
- `Button` — `variant: primary | secondary | danger | ghost`, `size: sm | md`, `icon`, `loading`
- `Badge` — `variant: default | success | warning | danger | info`
- `Input`, `Select`, `Textarea` — formulaires
- `Modal`, `ConfirmDialog` — overlays
- `Tabs` — barre d'onglets standard
- `FilterBar`, `SearchInput`, `Pagination`, `EmptyState`, `LoadingSpinner`

**Règle** : **toujours** réutiliser ces atomes. Si un besoin n'est pas couvert, étendre le composant existant plutôt que d'en créer un parallèle.

### 4.2 Patterns récurrents (à fixer en composants partagés)

#### `<DetailHeader>`
```tsx
<DetailHeader
  avatar={<Avatar ... />}
  eyebrow="Entreprise · Startup Radar"
  title="Acme Corp"
  badges={[<Badge variant="success">Active</Badge>]}
  meta={[
    { icon: MapPin, label: "Paris, France" },
    { icon: Briefcase, label: "50-200" },
  ]}
  actions={[
    <Button variant="secondary" icon={Edit2}>Modifier</Button>,
    <Button variant="primary" icon={Plus}>Opportunité</Button>,
  ]}
/>
```

#### `<KpiStrip>`
4 colonnes par défaut. Chaque KPI : icône + label uppercase + valeur tabular-nums + suffix + trend.
Bordures internes via `gap-px bg-slate-200` (technique tableau).

#### `<AiCard>`
Carte violette discrète. Toujours avec :
- Eyebrow "Next best action"
- Titre court (≤ 12 mots)
- Body explicatif (1 phrase, max 35 mots)
- 3 boutons : action primaire / secondaire / "Ignorer"

#### `<ActivityTimeline>`
- Groupée par jour ("Aujourd'hui", "Hier", "12 mai")
- Trait vertical à 31px
- Icône typée par activité (mail, call, meeting, note, linkedin, task, audit)
- Composer multi-canal au-dessus

#### `<SideCard>`
Carte 320px, header avec titre + icône optionnelle, body padding 16px.

#### `<SplitView>`
Layout liste + détail avec :
- Liste 340px à gauche (entête + recherche + items)
- Item actif : `bg-slate-50 shadow-sm`
- Hover : `hover:bg-slate-50`

---

## 5. Patterns d'interaction

### 5.1 Navigation
- **Cmd/Ctrl + K** — palette de recherche globale (toutes entités)
- **G + C** / **G + P** / **G + T** — go to Companies/Pipeline/Tasks (vim-like, optionnel)
- **J / K** — naviguer dans les listes (split-view)
- **N** — créer (contextuel selon page)
- **E** — éditer la fiche courante
- **Esc** — fermer modal / annuler édition

### 5.2 États de chargement
- **Skeleton** : pour la première charge d'une page (silhouettes grises animées)
- **LoadingSpinner** : pour les actions ponctuelles dans un bouton
- **Refetch silencieux** : utiliser `placeholderData` de TanStack Query pour ne pas re-skeleton

### 5.3 États vides
Toujours :
- Icône 36×36 dans un fond `slate-50`
- Texte court ("Aucune activité enregistrée")
- CTA d'amorce si action possible ("Ajouter une note")

### 5.4 Erreurs
- **Inline** dans un formulaire (rouge sous le champ)
- **Toast** pour les actions globales (top-right, 4s, dismissible)
- **Bannière** rouge en haut de page pour les erreurs bloquantes (404, 403)

### 5.5 Confirmations
- Action destructive (delete) → `<ConfirmDialog variant="danger">`
- Action réversible (archive) → toast avec "Annuler" pendant 5s
- Action critique (changement de stage Deal) → modal récap

### 5.6 Édition
**Privilégier l'édition inline** sur les champs simples (nom, titre, montant). Pattern :
- Click sur le champ → bordure apparaît
- Enter → save
- Esc → annule
- Mutation optimiste, rollback sur erreur

Pour l'édition complexe (>4 champs) : panneau latéral droit (drawer) ou modal.

---

## 6. Données & affichage

### 6.1 Format des nombres
- Montants : `42 500 €` (espace fine, locale fr-FR)
- Pourcentages : `42 %` (espace fine)
- Compactés en KPI : `42,5 k €` (1 décimale, suffix séparé)
- Toujours `tabular-nums` pour aligner verticalement

### 6.2 Format des dates
- Long : "12 mai 2026"
- Court : "12 mai"
- Dans timeline : "Aujourd'hui" / "Hier" / "il y a 5 j" / "12 mai"
- Heure : "14:32" (24h)

### 6.3 Format des libellés
- Stage Deal : Nouveau / Contacté / Meeting / Proposition / Négociation / Gagné / Perdu
- Statut Contact : Nouveau / Contacté / Qualifié / Non qualifié / Nurturing
- Priority : Basse / Moyenne / Haute / Urgente
- Type Activity : Email / Appel / Meeting / Note / LinkedIn / Tâche / Audit SR

> Dictionnaires centralisés dans `frontend/src/types/` ou `frontend/src/i18n/`.

### 6.4 Truncation
- Toujours `truncate` sur les titres dans les listes
- `line-clamp-3` sur les contenus d'activité dans la timeline
- Tooltip sur hover si tronqué (composant à créer)

---

## 7. Règles spécifiques par type de page

### 7.1 Liste / Tableau (Companies, Contacts, Pipeline tableau)
- En-tête sticky (`sticky top-0 bg-white`)
- Hauteur de ligne : 48px (compact) ou 56px (avec avatar)
- Hover row : `bg-slate-50/60`
- Click row → navigue vers la fiche (pas de bouton "Voir")
- Checkbox de sélection multiple à gauche, action bar contextuelle qui apparaît en haut quand >0 sélectionnés
- Tri : icône `ChevronUp/Down` après le label de colonne, click pour cycler asc/desc/null

### 7.2 Fiche détail (pattern unifié)
Voir section 3.2.B et les 3 fichiers livrés (`CompanyDetail`, `ContactDetail`, `DealDetail`).

**Règles spécifiques** :
- KPI strip toujours 4 colonnes max
- AI card en haut du main (pas en sidebar — c'est l'action prioritaire de la session)
- Tabs : 3 à 5 onglets max ; au-delà, repenser la fiche
- Sidebar : 2 à 4 cartes, jamais plus

### 7.3 Kanban Pipeline
- Colonne 280px de large, scroll horizontal si > 6 colonnes
- Carte deal : titre + entreprise + montant + jours en colonne + tags priorité
- Drag = preview ghost à 50% opacity, drop zones surlignées en `primary-50`
- Footer colonne : sum + count en `text-xs text-slate-500`

### 7.4 Formulaires
- Layout 1 colonne par défaut, 2 colonnes si >8 champs
- Label au-dessus du champ (`text-xs font-medium text-slate-700 mb-1`)
- Aide sous le champ (`text-xs text-slate-400 mt-1`)
- Erreur sous le champ (`text-xs text-red-600 mt-1`)
- Champs requis : asterisque rouge après le label
- Boutons en bas : "Annuler" (ghost) à gauche, "Enregistrer" (primary) à droite, séparé par `border-t pt-4`

### 7.5 Modals
- Largeur max : 480px (form simple), 640px (form complexe), 920px (preview)
- Header avec titre + close button
- Footer sticky avec actions
- Overlay : `bg-slate-900/40 backdrop-blur-sm`

### 7.6 Onboarding / Empty states (page entière)
Quand un utilisateur arrive sur une section vide (ex: "Aucun deal créé") :
- Illustration discrète (icône 64px dans un cercle slate-100)
- Titre H2 "Pas encore de deal"
- Body 1 phrase
- CTA primaire "Créer mon premier deal"
- Lien secondaire "Importer depuis CSV"

---

## 8. IA dans le CRM (pattern dédié)

### 8.1 Quand intégrer l'IA
- **Suggestions d'action** ("Next best action") — sur chaque fiche
- **Génération de contenu** (email de relance, résumé d'activité, note de meeting)
- **Scoring & prédiction** (audit Startup Radar, score d'engagement, probabilité de win ajustée)
- **Extraction structurée** (notes voix → tâches, email → activité enregistrée)

### 8.2 Pattern visuel IA
- **Couleur dédiée** : violet/indigo (`violet-700` text, `violet-50/40` bg)
- **Sparkles icon** systématiquement sur les éléments IA-generated
- **Badge "IA"** ou eyebrow "Suggestion IA" pour distinguer du contenu humain
- **Toujours actionnable** : pas de carte IA sans CTA primaire
- **Toujours dismissable** : "Plus tard" + "Ignorer" obligatoires

### 8.3 Honnêteté
- Préfixer les contenus générés ("Suggéré par l'IA")
- Permettre l'édition avant envoi (jamais d'auto-send)
- Afficher la confiance si pertinent ("Confiance : élevée / moyenne / faible")
- Logger en backend pour A/B test et amélioration continue

---

## 9. Accessibilité

### 9.1 Contraste
- Texte body sur fond blanc : `slate-700` minimum (WCAG AA)
- Texte secondaire : `slate-500` minimum
- Jamais `slate-300` ou `slate-400` pour du texte lisible (uniquement icônes désactivées ou placeholders)

### 9.2 Focus
- Anneau visible sur tous les éléments interactifs : `focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2`
- Ordre de tabulation logique (haut→bas, gauche→droite)
- Skip link "Aller au contenu" en haut de page

### 9.3 ARIA
- `role="tablist"` / `role="tab"` / `aria-selected` sur les tabs
- `aria-label` sur les boutons icône-only
- `aria-live="polite"` sur les zones qui se mettent à jour (toasts, refetch)
- `aria-current="page"` sur le lien actif de la nav

### 9.4 Clavier
- Tout doit être accessible sans souris
- Modals : `Esc` ferme, focus trap actif, focus retourne au déclencheur à la fermeture

---

## 10. Performance

- **Lazy load** les routes (React.lazy + Suspense)
- **TanStack Query** : `staleTime: 30s` par défaut, `gcTime: 5min`
- **Virtualisation** des listes > 200 items (react-window)
- **Debounce** des recherches : 250ms
- **Optimistic updates** sur les mutations fréquentes (toggle done, change stage)
- **Prefetch** la fiche au hover dans la liste split-view

---

## 11. Anti-patterns à proscrire

| ❌ Ne pas faire | ✅ Faire |
|---|---|
| Gradients tape-à-l'œil en background | Surfaces `bg-white` ou `bg-slate-50` |
| Emojis dans l'UI (🚀, 💼, 🔥) | Icônes lucide neutres |
| `text-bold` (700) | `font-semibold` (600) max |
| `shadow-lg` ou `shadow-2xl` | `shadow-sm` ou rien |
| Containers à coin arrondi avec border accent gauche | Border standard `border-slate-200` |
| Inventer des KPI ("12% vs Q1") sans données | `—` si la donnée n'existe pas |
| Ouvrir une page entière pour éditer 1 champ | Édition inline ou drawer |
| Multiplier les couleurs sémantiques par état | S'en tenir aux 5 du tableau §2.1 |
| `border-l-4 border-primary-500` style "bandeau" | Badge ou Tag à la place |
| Animations longues (>300ms) | Transitions courtes (`transition-colors` 150ms) |
| Texte > 70 caractères par ligne | `max-w-prose` ou colonne 320–680px |
| Boutons primaires multiples par section | 1 seul CTA primaire visible à la fois |

---

## 12. Checklist de revue (avant merge)

À cocher pour chaque PR qui touche l'UI :

- [ ] Utilise les composants UI existants (`Button`, `Badge`, `Tabs`...) — pas de nouveau composant parallèle
- [ ] Couleurs uniquement depuis la palette §2.1
- [ ] Typographie respecte l'échelle §2.2
- [ ] Espacements multiples de 4 (Tailwind defaults)
- [ ] Empty states présents pour toutes les listes
- [ ] Loading states présents (skeleton ou spinner)
- [ ] Erreurs gérées (catch + toast ou inline)
- [ ] Focus accessible au clavier
- [ ] Pas d'emoji, pas de gradient agressif, pas de shadow-md+
- [ ] Textes en français, sans faute, sans accent oublié sur les `é/è/à`
- [ ] Numbers en `tabular-nums`
- [ ] Format dates/montants conforme §6
- [ ] Mobile : à minima la page reste lisible (pas forcément éditable)
- [ ] `npx tsc --noEmit` passe sans erreur
- [ ] `npx eslint` passe sans warning

---

## 13. Versionning de ce document

| Version | Date | Auteur | Changement |
|---|---|---|---|
| 1.0 | 2026-05-04 | Claude / Hervé | Création initiale, fixe charte + patterns détail |

> Toute évolution majeure (nouveau pattern récurrent, nouvelle palette, refonte d'un composant atomique) doit être ajoutée ici **avant** d'être implémentée.

---

## Annexes

### A. Glossaire métier
- **Deal** = Opportunité commerciale
- **Stage** = Étape dans le pipeline (new → won/lost)
- **Audit SR** = Audit Startup Radar (scoring + recommandations)
- **Décisionnaire** = Contact avec pouvoir de signature (`is_decision_maker: true`)
- **Pipeline pondéré** = Σ (montant × probabilité) sur les deals ouverts

### B. Liens utiles
- Tailwind config : `frontend/tailwind.config.js`
- Composants UI : `frontend/src/components/ui/`
- Types métier : `frontend/src/types/`
- Refonte v2 livrée : `refactor-output/`
