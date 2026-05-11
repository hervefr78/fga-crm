# FUNDING_SYNC_INTEGRATION.md — Côté FGA-CRM

> Ce document décrit l'intégration côté CRM de la nouvelle ingestion multi-source de levées de fonds qui arrive depuis Startup Radar (SR).
>
> **Document maître** (côté SR) : `/Users/master/startup-radar/FUNDING_MULTI_SOURCE_INTEGRATION.md` (sections 1-12 = pipeline SR ; section 13 = ce document).
>
> **Statut** : plan, prêt à passer à Claude Code.
> **Auteur** : Hervé / Claude — 2026-05-11

---

## Contexte rapide

Le projet Startup Radar (SR) reçoit une refonte de son pipeline de veille : il agrège désormais 5 sources (LesPepitesTech, Maddyness, Eldorado, L'Usine Digitale, BODACC) et enrichit les fondateurs avec Pappers + heuristiques email/LinkedIn.

**Conséquence côté CRM** : les startups remontent dans le CRM via le sync existant (`services/startup_radar_sync.py`), avec des champs en plus à mapper et de nouvelles activités/tasks à créer automatiquement.

Côté CRM, on ne fait **aucun scraping** — on consomme uniquement l'API SR via le sync existant, qu'on étend.

---

## 1. Vue d'ensemble du flux

```
[SR] funding_ingest multi-source quotidien (06h00)
  ↓
[SR] enrichissement fondateurs Pappers (08h30)
  ↓
[SR] API /api/v1/startups, /contacts (exposent les nouveaux champs)
  ↓
[CRM] cron sync-recent-funding (09h00, optionnel)
  ↓
[CRM] startup_radar_sync.py étendu :
   - sync_startups() → Company avec funding_date, funding_amount, funding_series,
                       siren, funding_sources
   - sync_contacts() → Contact avec enrichment_source, email_pattern_used,
                       linkedin_url_status
   - create_funding_activity() → Activity "Levée détectée"
   - create_qualification_task() → Task auto pour levées ≥ seuil
  ↓
[CRM] UI affiche bloc Funding sur fiche Company, badges Email/LinkedIn candidat
```

---

## 2. Modifications côté CRM

### 2.1 Migration Alembic

Numéro à attribuer (voir `backend/app/db/migrations/versions/` côté CRM, probablement la migration suivante).

> **À vérifier** : Alembic est-il activé côté CRM ? Le `REPO_MAP.md` mentionne `init_db create_all` (piège #6). Si Alembic n'est pas activé, soit l'activer maintenant (recommandé pour la suite), soit faire un script ad-hoc `ALTER TABLE` à exécuter manuellement en prod.

```python
"""Add funding multi-source fields synced from Startup Radar

Revision ID: XXX_funding_sync
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "XXX_funding_sync"
down_revision = "PREV_REVISION"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Company : champs funding promus en colonnes natives
    op.add_column(
        "companies",
        sa.Column("siren", sa.String(9), nullable=True),
    )
    op.create_index("ix_companies_siren", "companies", ["siren"])
    op.add_column(
        "companies",
        sa.Column("funding_date", sa.Date(), nullable=True),
    )
    op.create_index("ix_companies_funding_date", "companies", ["funding_date"])
    op.add_column(
        "companies",
        sa.Column("funding_amount", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_companies_funding_amount", "companies", ["funding_amount"])
    op.add_column(
        "companies",
        sa.Column("funding_series", sa.String(50), nullable=True),
    )
    op.add_column(
        "companies",
        sa.Column("funding_sources", postgresql.JSONB, nullable=True),
    )

    # Contact : traçabilité enrichissement
    op.add_column(
        "contacts",
        sa.Column("enrichment_source", sa.String(50), nullable=True),
    )
    op.add_column(
        "contacts",
        sa.Column("email_pattern_used", sa.String(50), nullable=True),
    )
    op.add_column(
        "contacts",
        sa.Column("linkedin_url_status", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("contacts", "linkedin_url_status")
    op.drop_column("contacts", "email_pattern_used")
    op.drop_column("contacts", "enrichment_source")
    op.drop_column("companies", "funding_sources")
    op.drop_column("companies", "funding_series")
    op.drop_index("ix_companies_funding_amount", table_name="companies")
    op.drop_column("companies", "funding_amount")
    op.drop_index("ix_companies_funding_date", table_name="companies")
    op.drop_column("companies", "funding_date")
    op.drop_index("ix_companies_siren", table_name="companies")
    op.drop_column("companies", "siren")
```

### 2.2 Extension des modèles ORM

`backend/app/models/company.py` — ajouter :

```python
from datetime import date
from sqlalchemy import BigInteger, Date

# Funding (synced from Startup Radar)
siren: Mapped[str | None] = mapped_column(String(9), nullable=True, index=True)
funding_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
funding_amount: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
funding_series: Mapped[str | None] = mapped_column(String(50), nullable=True)
funding_sources: Mapped[list | None] = mapped_column(JSONB, nullable=True)
```

`backend/app/models/contact.py` — ajouter :

```python
enrichment_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
email_pattern_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
linkedin_url_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

### 2.3 Extension des schemas Pydantic

`backend/app/schemas/company.py` — dans `CompanyResponse`, `CompanyUpdate`, `CompanyCreate` :

```python
siren: str | None = None
funding_date: date | None = None
funding_amount: int | None = None
funding_series: str | None = None
funding_sources: list[str] | None = None
```

`backend/app/schemas/contact.py` — dans `ContactResponse`, `ContactUpdate`, `ContactCreate` :

```python
enrichment_source: str | None = None
email_pattern_used: str | None = None
linkedin_url_status: str | None = None
```

### 2.4 Extension `services/startup_radar_sync.py`

#### Mapping des nouveaux champs dans `sync_startups()`

Dans la branche **update** (existing) :

```python
# --- Funding fields ---
if s.get("siren") and not existing.siren:
    existing.siren = s["siren"]
if s.get("funding_date") and not existing.funding_date:
    try:
        existing.funding_date = date.fromisoformat(s["funding_date"])
    except (ValueError, TypeError):
        pass
if s.get("amount") and (not existing.funding_amount or s["amount"] > existing.funding_amount):
    existing.funding_amount = s["amount"]
if s.get("series") and not existing.funding_series:
    existing.funding_series = s["series"]
if s.get("source_names"):
    existing_sources = set(existing.funding_sources or [])
    merged = sorted(existing_sources | set(s["source_names"]))
    existing.funding_sources = merged
```

Dans la branche **insert** (new), ajouter au constructeur `Company(...)` :

```python
siren=s.get("siren"),
funding_date=_parse_iso_date(s.get("funding_date")),
funding_amount=s.get("amount"),
funding_series=s.get("series"),
funding_sources=s.get("source_names"),
```

Avec un helper local :

```python
def _parse_iso_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None
```

#### Mapping enrichissement dans `sync_contacts()`

Dans la branche **update** :

```python
if c.get("enrichment_source"):
    existing.enrichment_source = c["enrichment_source"]
if c.get("email_pattern_used") and not existing.email_pattern_used:
    existing.email_pattern_used = c["email_pattern_used"]
if c.get("linkedin_url_status"):
    existing.linkedin_url_status = c["linkedin_url_status"]
```

Dans la branche **insert** (constructeur `Contact(...)`) :

```python
enrichment_source=c.get("enrichment_source"),
email_pattern_used=c.get("email_pattern_used"),
linkedin_url_status=c.get("linkedin_url_status"),
```

#### Nouvelle fonction `create_funding_activity()`

À ajouter dans `startup_radar_sync.py`. Idempotente :

```python
async def create_funding_activity(
    db: AsyncSession,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    startup_data: dict,
) -> bool:
    """Crée une activité 'Levée détectée'. Idempotente.

    Returns:
        True si activité créée, False si elle existait déjà ou si pas de montant.
    """
    amount_eur = startup_data.get("amount", 0)
    if not amount_eur:
        return False

    series = startup_data.get("series") or "Levée"
    sources = startup_data.get("source_names") or ["startup_radar"]
    investors = startup_data.get("investors") or []

    amount_m = amount_eur / 1_000_000
    subject = f"Levée détectée : {amount_m:.1f}M€ ({series})"

    stmt = select(Activity).where(
        Activity.company_id == company_id,
        Activity.type == "funding_detected",
        Activity.subject == subject,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        return False

    metadata = {
        "amount_eur": amount_eur,
        "series": series,
        "sources": sources,
        "investors": investors[:10],
        "funding_date": startup_data.get("funding_date"),
        "siren": startup_data.get("siren"),
    }

    content_lines = [
        f"Montant : {amount_m:.1f}M€",
        f"Série : {series}",
        f"Sources détectées : {', '.join(sources)}",
    ]
    if investors:
        content_lines.append(f"Investisseurs : {', '.join(investors[:5])}")

    activity = Activity(
        id=uuid.uuid4(),
        type="funding_detected",
        subject=subject,
        content="\n".join(content_lines),
        metadata_=metadata,
        company_id=company_id,
        user_id=user_id,
    )
    db.add(activity)
    return True
```

#### Nouvelle fonction `create_qualification_task()`

```python
from datetime import datetime, timedelta
from app.models.task import Task

QUALIFICATION_TASK_THRESHOLD_EUR = 5_000_000  # paramétrable via settings


async def create_qualification_task(
    db: AsyncSession,
    company_id: uuid.UUID,
    assigned_to: uuid.UUID,
    startup_name: str,
    amount_eur: int,
    threshold: int = QUALIFICATION_TASK_THRESHOLD_EUR,
) -> bool:
    """Crée une tâche 'Qualifier la levée' pour les levées ≥ seuil. Idempotente.

    Returns:
        True si tâche créée, False sinon.
    """
    if amount_eur < threshold:
        return False

    amount_m = amount_eur / 1_000_000
    title = f"Qualifier la levée : {startup_name} ({amount_m:.1f}M€)"

    stmt = select(Task).where(
        Task.company_id == company_id,
        Task.title == title,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        return False

    due_date = datetime.utcnow() + timedelta(days=7)

    task = Task(
        id=uuid.uuid4(),
        title=title,
        type="qualification",
        priority="medium",
        due_date=due_date,
        company_id=company_id,
        assigned_to=assigned_to,
        is_completed=False,
    )
    db.add(task)
    return True
```

#### Appel depuis `sync_startups()`

Après `db.add(company)` pour les nouvelles companies seulement :

```python
# Apres db.add(company) dans la branche "insert"
if s.get("amount"):
    await create_funding_activity(db, company_id, user.id, s)
    await create_qualification_task(
        db,
        company_id=company_id,
        assigned_to=user.id,
        startup_name=s.get("name", "Startup"),
        amount_eur=s.get("amount", 0),
    )
```

### 2.5 Nouvel endpoint : sync incrémentale

`backend/app/api/v1/integrations.py` :

```python
@router.post("/startup-radar/sync-recent-funding")
async def sync_recent_funding(
    days_back: int = 7,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Sync incrémentale : pull uniquement les startups récentes depuis SR.

    Utile pour un cron quotidien (CRM) qui synchronise les nouvelles levées
    sans refaire une full sync (coûteuse en temps et requêtes).

    Args:
        days_back: fenêtre de remontée (défaut 7 jours).
    """
    from app.services.startup_radar_sync import sync_recent_startups
    return await sync_recent_startups(db, user, days_back=days_back)
```

Et dans `startup_radar_sync.py` :

```python
async def sync_recent_startups(
    db: AsyncSession,
    user: User,
    days_back: int = 7,
) -> SyncResult:
    """Sync uniquement les startups créées dans SR depuis N jours.

    Appelle l'endpoint SR `/startups?since={iso_date}` (à créer côté SR).
    Réutilise la logique de sync_startups (sans full pagination).
    """
    from datetime import datetime, timedelta

    client = StartupRadarClient()
    try:
        await client.authenticate()
    except StartupRadarError:
        pass  # mode anonyme si pas de creds

    since = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

    # Note : nécessite que /api/v1/startups accepte ?since= côté SR
    try:
        data = await client._get(f"/startups?since={since}&size=200")
    except StartupRadarError as e:
        result = SyncResult()
        result.errors.append(f"Fetch recent startups: {e}")
        return result

    items = data.get("items", []) if data else []

    # Refactor : extraire la logique de mapping en helper réutilisable
    result = SyncResult()
    sr_to_crm: dict[str, uuid.UUID] = {}

    for s in items:
        # Réutiliser la même logique que sync_startups (à factoriser dans
        # une helper _upsert_company_from_sr)
        await _upsert_company_from_sr(db, s, user, sr_to_crm, result)

    # Sync contacts liés à ces startups uniquement
    contacts = await client.get_contacts()
    relevant_contacts = [
        c for c in contacts
        if str(c.get("startup_id", "")) in sr_to_crm
    ]
    for c in relevant_contacts:
        await _upsert_contact_from_sr(db, c, user, sr_to_crm, result)

    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        result.errors.append(f"Commit: {e}")

    return result
```

> **À noter** : nécessite que **côté SR**, l'endpoint `GET /api/v1/startups` accepte un paramètre query `since: datetime | None` qui filtre `WHERE scraped_at >= since`. À ajouter dans `backend/app/api/v1/startups.py` côté SR. Voir doc maître section 13.2 / 13.3.

### 2.6 UI à étendre

#### `CompanyDetail.tsx` — bloc Funding

Nouveau bloc affiché si `company.funding_date` ou `company.funding_amount` est renseigné :

```tsx
{(company.funding_date || company.funding_amount) && (
  <Card className="mb-4">
    <h3 className="font-semibold mb-2 flex items-center gap-2">
      <TrendingUp size={16} />
      Dernière levée détectée
    </h3>
    <div className="flex flex-wrap items-center gap-3">
      {company.funding_amount && (
        <Badge variant="success" size="lg">
          {formatAmountMillions(company.funding_amount)}
        </Badge>
      )}
      {company.funding_series && (
        <Badge variant="outline">{company.funding_series}</Badge>
      )}
      {company.funding_date && (
        <span className="text-sm text-gray-500">
          {formatDate(company.funding_date)}
        </span>
      )}
    </div>
    {company.funding_sources && company.funding_sources.length > 0 && (
      <div className="mt-3">
        <span className="text-xs text-gray-500 mr-2">Sources :</span>
        {company.funding_sources.map((src) => (
          <Badge key={src} variant="ghost" size="sm" className="mr-1">
            {src}
          </Badge>
        ))}
      </div>
    )}
    {company.siren && (
      <p className="text-xs text-gray-500 mt-2">SIREN : {company.siren}</p>
    )}
  </Card>
)}
```

Helper `formatAmountMillions(amount)` à ajouter dans `utils/format.ts` :

```ts
export function formatAmountMillions(amountEur: number): string {
  const m = amountEur / 1_000_000;
  if (m >= 1) return `${m.toFixed(1)} M€`;
  return `${(amountEur / 1_000).toFixed(0)} k€`;
}
```

#### `ContactDetail.tsx` — indicateurs de fiabilité

Pour l'email :

```tsx
<div className="flex items-center gap-2">
  <Mail size={14} />
  <a href={`mailto:${contact.email}`}>{contact.email}</a>
  {contact.email_status === "valid" && (
    <Badge variant="success" size="sm">Vérifié</Badge>
  )}
  {contact.email_status === "unknown" && (
    <Tooltip content={`Email généré par heuristique (${contact.email_pattern_used}). À vérifier avant envoi.`}>
      <Badge variant="warning" size="sm">Candidat</Badge>
    </Tooltip>
  )}
  {contact.email_status === "risky" && (
    <Badge variant="danger" size="sm">Risqué</Badge>
  )}
</div>
```

Pour LinkedIn :

```tsx
{contact.linkedin_url && (
  <div className="flex items-center gap-2">
    <Linkedin size={14} />
    <a href={contact.linkedin_url} target="_blank" rel="noreferrer">
      Profil LinkedIn
    </a>
    {contact.linkedin_url_status === "candidate" && (
      <Tooltip content="URL générée automatiquement, à vérifier manuellement">
        <Badge variant="warning" size="sm">À vérifier</Badge>
      </Tooltip>
    )}
    {contact.linkedin_url_status === "verified" && (
      <Badge variant="success" size="sm">Vérifié</Badge>
    )}
  </div>
)}
```

#### `Dashboard.tsx` — KPI "Nouvelles levées"

Côté backend `dashboard.py`, ajouter à la query stats :

```python
seven_days_ago = datetime.utcnow().date() - timedelta(days=7)
recent_funding_count = (await db.execute(
    select(func.count(Company.id)).where(
        Company.funding_date >= seven_days_ago,
        Company.lead_source == "startup_radar",
    )
)).scalar() or 0

recent_funding_amount = (await db.execute(
    select(func.coalesce(func.sum(Company.funding_amount), 0)).where(
        Company.funding_date >= seven_days_ago,
        Company.lead_source == "startup_radar",
    )
)).scalar() or 0

return DashboardStats(
    # ... champs existants
    recent_funding_count=recent_funding_count,
    recent_funding_amount=recent_funding_amount,
)
```

Étendre `schemas/dashboard.py` `DashboardStats` :

```python
recent_funding_count: int = 0
recent_funding_amount: int = 0
```

Côté frontend, ajouter une carte KPI :

```tsx
<KpiCard
  title="Nouvelles levées (7j)"
  value={stats.recent_funding_count}
  subtitle={formatAmountMillions(stats.recent_funding_amount)}
  icon={TrendingUp}
  link="/companies?funding_date_gte=last_7_days"
/>
```

#### `Companies.tsx` — filtres funding

Ajouter dans `FilterBar` :

```tsx
<Select
  label="Série"
  value={filters.funding_series}
  onChange={(v) => onChange("funding_series", v)}
  options={[
    { value: "", label: "Toutes" },
    { value: "Seed", label: "Seed" },
    { value: "Serie A", label: "Serie A" },
    { value: "Serie B", label: "Serie B" },
    { value: "Serie C", label: "Serie C+" },
  ]}
/>

<Input
  type="number"
  label="Montant min (M€)"
  value={filters.funding_amount_min_m}
  onChange={(v) => onChange("funding_amount_min_m", v)}
/>

<Input
  type="date"
  label="Depuis"
  value={filters.funding_date_after}
  onChange={(v) => onChange("funding_date_after", v)}
/>
```

Côté backend `companies.py`, ajouter les paramètres query :

```python
funding_series: str | None = None,
funding_amount_min: int | None = None,  # en euros
funding_date_after: date | None = None,

# Dans la query :
if funding_series:
    query = query.where(Company.funding_series == funding_series)
if funding_amount_min:
    query = query.where(Company.funding_amount >= funding_amount_min)
if funding_date_after:
    query = query.where(Company.funding_date >= funding_date_after)
```

### 2.7 Types TypeScript frontend

`frontend/src/types/index.ts` — étendre :

```ts
export interface Company {
  // ... champs existants
  siren?: string | null;
  funding_date?: string | null;  // ISO date
  funding_amount?: number | null;
  funding_series?: string | null;
  funding_sources?: string[] | null;
}

export interface Contact {
  // ... champs existants
  enrichment_source?: string | null;
  email_pattern_used?: string | null;
  linkedin_url_status?: "candidate" | "verified" | "invalid" | null;
}

export interface DashboardStats {
  // ... champs existants
  recent_funding_count: number;
  recent_funding_amount: number;
}
```

---

## 3. Phases d'implémentation CRM

Alignées avec les phases SR (cf. doc maître section 6 et 13.5).

### Phase A — Schemas SR (1h)

**Dépendance** : Phase 4 SR mergée (les colonnes existent en DB SR).

Côté SR uniquement :
- Étendre `backend/app/schemas/startup.py` : `StartupResponse` reçoit les nouveaux champs
- Étendre `backend/app/schemas/contact.py` : `ContactResponse` reçoit les nouveaux champs
- Ajouter `since: datetime | None` à `GET /api/v1/startups` côté SR
- Test : `GET /api/v1/startups` renvoie bien `siren`, `funding_date`, etc.

### Phase B — CRM backend (3h)

**Dépendance** : Phase A complète.

Côté CRM :
- Migration Alembic (ou script ad-hoc si Alembic non actif)
- Extension `Company` + `Contact` (models)
- Extension `CompanyResponse` + `ContactResponse` (schemas)
- Refactor `startup_radar_sync.py` :
  - Helpers `_parse_iso_date()`, `_upsert_company_from_sr()`, `_upsert_contact_from_sr()`
  - Mapping nouveaux champs
  - `create_funding_activity()` idempotente
  - `create_qualification_task()` idempotente avec seuil
  - `sync_recent_startups()` (nouvelle)
- Endpoint `POST /integrations/startup-radar/sync-recent-funding`
- Tests :
  - `test_startup_radar_sync.py` : cas nouveau funding, idempotence activité, idempotence task, seuil task
  - Mock `StartupRadarClient` qui renvoie startups avec/sans nouveaux champs
- Validation : `pytest -v` PASS sur tous les tests CRM existants + nouveaux

### Phase C — CRM frontend (4h)

**Dépendance** : Phase B complète.

- Étendre `types/index.ts` (Company, Contact, DashboardStats)
- Helper `utils/format.ts` : `formatAmountMillions()`
- Bloc Funding dans `CompanyDetail.tsx`
- Badges email/LinkedIn dans `ContactDetail.tsx` (composant `EmailIndicator`, `LinkedinIndicator` réutilisables)
- KPI Dashboard
- Filtres dans `Companies.tsx` + `FilterBar`
- Tests Vitest : `EmailIndicator.test.tsx`, `LinkedinIndicator.test.tsx` (couverture frontend faible, profiter pour ajouter)
- Validation : `npx tsc --noEmit` PASS + `npx vitest run` PASS

---

## 4. Points d'attention CRM

1. **Alembic actif côté CRM ?** Le `REPO_MAP.md` mentionne `init_db create_all` (piège #6). Avant Phase B, vérifier si Alembic est activé. Si non, soit l'activer (recommandé), soit faire un script ad-hoc `ALTER TABLE` à exécuter en prod.

2. **Idempotence du sync** : le sync peut tourner plusieurs fois par jour. Les activités et tasks doivent être idempotentes (clé : `company_id + type + subject` ou `company_id + title`). Tests dédiés obligatoires.

3. **Owner attribution sur cron** : pour un cron CRM automatique, quel user owner ? Recommandation : créer un user technique `sync@fast-growth.fr` (rôle admin, exclu de la liste users), ou utiliser le seed admin existant.

4. **Ne pas écraser le travail commercial** : la sync est additive. Si une Company a un `Deal` en pipeline avancé, ne PAS modifier ses `custom_fields` métier, ne PAS écraser son `lead_source`. Vérifier dans les tests.

5. **Volume de tasks** : seuil `QUALIFICATION_TASK_THRESHOLD_EUR = 5_000_000`. Configurable via `settings.funding_task_threshold_eur` côté CRM. Sans ce seuil, 50 nouvelles tasks/mois noient le commercial.

6. **JSONB SQLite tests** (piège #2) : le `funding_sources` JSONB doit être mappé en JSON dans `conftest.py` pour les tests SQLite in-memory.

7. **Date parsing** : Pydantic str → SQLAlchemy date (piège #1). Convertir avec `date.fromisoformat()` dans la route ou le service.

8. **Cron CRM optionnel** : ajouter un Celery beat schedule pour déclencher `sync-recent-funding` à 09h00 quotidien (après le pipeline SR à 06h+08h30). Optionnel mais recommandé pour automatisation complète.

9. **Cohérence cross-projets** : un `claude_modifications_YYYY-MM-DD.md` doit être généré au moment du déploiement pour tracer les changements (pattern existant dans le repo SR à reprendre côté CRM).

10. **Notification email récap** : envisager un email quotidien via SMTP OVH existant qui résume les nouvelles levées détectées. Format à valider avec Hervé.

---

## 5. Open questions à résoudre avant Phase B

1. **Alembic actif ?** Si non, on l'active dans Phase B ou script ad-hoc ?

2. **Seuil de création de Task** : 5 M€ ok ou autre valeur ?

3. **User technique pour cron** : créer `sync@fast-growth.fr` ou utiliser admin existant ?

4. **Cron CRM `sync-recent-funding`** : à activer maintenant ou plus tard ?

5. **Notification email récap quotidien** : à activer maintenant ou plus tard ?

---

## 6. Checklist avant Phase B

- [ ] Phase A SR complète (les endpoints SR exposent les nouveaux champs)
- [ ] Plan validé par Hervé (notamment seuil task + alembic + user technique)
- [ ] Branche feature `feature/funding-sync-multi-source` créée côté CRM
- [ ] Tests existants `pytest -v` PASS

---

## 7. Référence

- **Doc maître** : `/Users/master/startup-radar/FUNDING_MULTI_SOURCE_INTEGRATION.md`
- **Service sync existant** : `backend/app/services/startup_radar_sync.py`
- **Client SR existant** : `backend/app/services/startup_radar.py`
- **Endpoint integrations existant** : `backend/app/api/v1/integrations.py`

---

> Document prêt à passer à Claude Code.
> Commande recommandée pour démarrer (une fois Phase A SR mergée) :
> `claude --read FUNDING_SYNC_INTEGRATION.md "Démarre Phase B : migration + extension models + extension sync, puis valide pytest avant Phase C."`
