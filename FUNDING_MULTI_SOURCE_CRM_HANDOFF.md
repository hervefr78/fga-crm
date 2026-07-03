# FUNDING_MULTI_SOURCE_CRM_HANDOFF.md

> Spec d'intégration côté **fga-crm** pour consommer les nouvelles données
> "funding multi-source" produites par **startup-radar (SR)**.
>
> Auteur : Hervé / Claude — 2026-05-11
> Statut : prêt à implémenter côté CRM
> Côté SR : Phases 1→6 livrées, validées en local, branche
> `feature/funding-multi-source` (PR à créer côté SR avant deploy).

---

## 0. Vue d'ensemble

Côté SR, l'ingestion multi-source agrège **4 sources** : LesPepitesTech,
Maddyness, Eldorado et BODACC (Usine Digitale skippé V1, anti-bot DataDome).
Les startups sont dédupliquées sur `(normalized_name, year_quarter, amount_bucket)`,
puis upsert dans la table `startups` enrichies avec :
- **Multi-source** : `source_names[]`, `source_urls{}`
- **Identité légale** : `siren` (récupéré via BODACC)
- **Date opération** : `funding_date` (DATE)
- **Identité unique** : `normalized_name` (clé de dédup)

L'enrichissement fondateurs crée des `contacts` avec :
- **Provenance** : `enrichment_source` (`scraped_founders` / `evaboot`)
- **Email candidat** : `email` (status `unknown`) + `email_pattern_used`
- **LinkedIn candidat** : `linkedin_url` + `linkedin_url_status` (`candidate` / `verified`)

**Objectif côté CRM** : étendre `Company` + `Contact` pour absorber ces nouveaux
champs via la sync existante (`services/startup_radar_sync.py`), créer une
Activity "Levée détectée" + une Task "Qualifier la levée" pour les nouveaux
deals au-dessus de **1 M€** (seuil validé Hervé).

---

## 1. Schéma API SR exposé

### 1.1 Endpoint `GET /api/v1/startups/{id}` — réponse complète

Champs **nouveaux** ajoutés en migration 030 (en plus de l'existant) :

```json
{
  "id": "uuid",
  "name": "string",
  "website": "string|null",
  "amount": "integer (EUR)",
  "series": "string|null (ex: Seed, Serie A, ...)",
  "sector": "string|null",
  "strategy": "string|null (B2B|B2C|B2B2C)",
  "description": "string|null",
  "founders": "string[]|null",
  "investors": "string[]|null",
  "source_url": "string (URL de la source primaire)",
  "scraped_at": "datetime ISO 8601",
  "week_number": "integer",
  "year": "integer",
  "status": "string (to_engage|engaged|lead|deal|lost|not_interested)",
  "has_analysis": "boolean",
  "has_detailed_audit": "boolean",
  "messaging_score": "integer|null (0-10)",
  "created_at": "datetime ISO 8601",

  // === NOUVEAUX CHAMPS PHASE 5 ===
  "siren": "string|null (9 chiffres, sans espaces)",
  "normalized_name": "string|null (lowercase, accents stripped)",
  "funding_date": "date YYYY-MM-DD|null",
  "source_names": "string[]|null (ex: [\"maddyness\", \"lespepitestech\"])",
  "source_urls": "object|null (map source → URL spécifique)",

  "contacts": [/* ContactResponse */],
  "analysis": null | {/* AnalysisResponse */},
  "competitors": [],
  "pipeline": null
}
```

### 1.2 Schema `ContactResponse` — nouveaux champs

```json
{
  "id": "uuid",
  "first_name": "string|null",
  "last_name": "string|null",
  "title": "string|null",
  "email": "string|null",
  "email_status": "string|null (safe|riskier|unknown|null)",
  "linkedin_url": "string|null",
  "headline": "string|null",
  "is_decision_maker": "boolean",
  "contact_status": "string (to_contact|contacted)",

  // === NOUVEAUX CHAMPS PHASE 5 ===
  "enrichment_source": "string|null (scraped_founders|evaboot)",
  "email_pattern_used": "string|null (firstname.lastname|firstname|f.lastname|...)",
  "linkedin_url_status": "string|null (candidate|verified)"
}
```

### 1.3 Endpoint `GET /api/v1/startups` (liste paginée)

Réponse : `{ items: StartupResponse[], total, page, size, pages }`.

`StartupResponse` (item de liste) inclut **tous les champs ci-dessus SAUF**
`contacts`, `analysis`, `competitors`, `pipeline` (uniquement dans la vue
détail). Les champs multi-source (`siren`, `normalized_name`, etc.) **sont
présents** dans la liste.

---

## 2. Exemple JSON réel capturé (2026-05-11)

### 2.1 Startup `Glimpact` (LPT seul, fondateur scrapé)

```json
{
  "id": "3ca5d906-3a58-4a3c-8233-07a09056c53c",
  "name": "Glimpact",
  "website": "http://www.glimpact.com/",
  "amount": 2600000,
  "series": "Seed",
  "sector": "Cleantech",
  "strategy": "B2B",
  "description": "Glimpact est la première plateforme digitale...",
  "founders": ["Michael Ooms"],
  "investors": ["Sparkalis"],
  "source_url": "https://lespepitestech.com/blog/2026/04/28/...",
  "scraped_at": "2026-05-11T19:50:41.886093Z",
  "week_number": 20,
  "year": 2026,
  "status": "to_engage",
  "siren": null,
  "normalized_name": "glimpact",
  "funding_date": null,
  "source_names": ["lespepitestech"],
  "source_urls": {
    "lespepitestech": "https://lespepitestech.com/blog/2026/04/28/..."
  },
  "contacts": [
    {
      "id": "a9d86287-...",
      "first_name": "Michael",
      "last_name": "Ooms",
      "title": "Co-fondateur",
      "email": "michael.ooms@glimpact.com",
      "email_status": "unknown",
      "linkedin_url": "https://www.linkedin.com/in/michael-ooms/",
      "is_decision_maker": true,
      "contact_status": "to_contact",
      "enrichment_source": "scraped_founders",
      "email_pattern_used": "firstname.lastname",
      "linkedin_url_status": "candidate"
    }
  ]
}
```

### 2.2 Startup `Aura Aero` (Eldorado + BODACC dédupliqués)

```json
{
  "id": "39f01636-b8d6-4faf-bfda-b25c2baee880",
  "name": "Aura Aero",
  "amount": 340000000,
  "series": "Series C",
  "sector": "Aérospatial",
  "siren": "842171316",
  "normalized_name": "aura aero",
  "funding_date": "2026-04-15",
  "source_names": ["bodacc", "eldorado"],
  "source_urls": {
    "bodacc": "https://www.bodacc.fr/pages/annonces-commerciales-detail/?q.id=id:B202600...",
    "eldorado": "https://eldorado.co/node/98126"
  },
  "contacts": []
}
```

**Cas d'usage clé** : Eldorado a fourni le ticket (340M€), BODACC a fourni le SIREN (842171316). Sans la dédup multi-source, on aurait eu 2 lignes parallèles.

---

## 3. Endpoints SR consommables

| Endpoint | Méthode | Auth | Usage CRM |
|----------|---------|------|-----------|
| `/api/v1/startups` | GET | JWT (ou désactivé selon `AUTH_DISABLED`) | Liste paginée pour sync full |
| `/api/v1/startups/{id}` | GET | idem | Détail individuel + contacts |
| `/api/v1/startups?since={date}` | GET | idem | **À implémenter côté SR Phase B** : filtre `scraped_at >= since` pour sync incrémentale |
| `/api/v1/scraping/multi-source` | POST | idem | Trigger manuel (admin uniquement) |
| `/api/v1/scraping/enrich-founders/{id}` | POST | idem | Trigger enrichment manuel |

**Note authentification** : SR a `AUTH_DISABLED=true` en local. En prod sur VPS,
JWT requis. Le client `StartupRadarClient` côté CRM doit déjà gérer les deux modes
(à vérifier dans `services/startup_radar_sync.py`).

**Note `?since=`** : actuellement non implémenté côté SR. **Ticket à ouvrir**
pour ajouter le filtre query param. Sans lui, sync = full pull (~200-500 startups
selon avancement).

---

## 4. Modèles ORM CRM à étendre

### 4.1 `app/models/company.py` (CRM)

Ajouter (suit le pattern `Mapped[...]` existant) :

```python
from datetime import date
from sqlalchemy import BigInteger, Date, String
from sqlalchemy.dialects.postgresql import JSONB

# Funding (synced from Startup Radar)
siren: Mapped[str | None] = mapped_column(
    String(9), nullable=True, index=True,
)
funding_date: Mapped[date | None] = mapped_column(
    Date, nullable=True, index=True,
)
funding_amount: Mapped[int | None] = mapped_column(
    BigInteger, nullable=True, index=True,
)
funding_series: Mapped[str | None] = mapped_column(
    String(50), nullable=True,
)
funding_sources: Mapped[list | None] = mapped_column(
    JSONB, nullable=True,
)
```

Conventions de nommage : on préfixe `funding_*` côté CRM pour distinguer du
champ SR `amount` (qui devient `funding_amount` côté CRM, plus explicite).

### 4.2 `app/models/contact.py` (CRM)

```python
from sqlalchemy import String

enrichment_source: Mapped[str | None] = mapped_column(
    String(50), nullable=True,
)
email_pattern_used: Mapped[str | None] = mapped_column(
    String(50), nullable=True,
)
linkedin_url_status: Mapped[str | None] = mapped_column(
    String(20), nullable=True,
)
```

---

## 5. Migration CRM (DDL complet)

⚠️ **Vérifier d'abord si Alembic est actif côté CRM** (cf. piège #6 du REPO_MAP
CRM : projet utilise historiquement `init_db create_all`).

Si Alembic actif → créer `XXX_funding_multi_source_sync.py`. Sinon → activer
Alembic d'abord OU faire un script ad-hoc.

```python
"""Add funding multi-source fields synced from Startup Radar.

Revision ID: XXX_funding_multi_source
Revises: <revision-précédente-CRM>
Create Date: 2026-05-XX
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "XXX_funding_multi_source"  # max 32 chars (DC4)
down_revision = "<previous>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Companies : nouveaux champs funding
    op.add_column("companies", sa.Column("siren", sa.String(9), nullable=True))
    op.create_index("ix_companies_siren", "companies", ["siren"])

    op.add_column("companies", sa.Column("funding_date", sa.Date(), nullable=True))
    op.create_index("ix_companies_funding_date", "companies", ["funding_date"])

    op.add_column("companies", sa.Column("funding_amount", sa.BigInteger(), nullable=True))
    op.create_index("ix_companies_funding_amount", "companies", ["funding_amount"])

    op.add_column("companies", sa.Column("funding_series", sa.String(50), nullable=True))
    op.add_column("companies", sa.Column("funding_sources", postgresql.JSONB, nullable=True))

    # 2. Contacts : provenance enrichment
    op.add_column("contacts", sa.Column("enrichment_source", sa.String(50), nullable=True))
    op.add_column("contacts", sa.Column("email_pattern_used", sa.String(50), nullable=True))
    op.add_column("contacts", sa.Column("linkedin_url_status", sa.String(20), nullable=True))


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

**Test obligatoire avant deploy** : `alembic upgrade head` puis vérifier dans psql
les colonnes + index.

---

## 6. Mapping explicite SR → CRM

### 6.1 `Startup` (SR) → `Company` (CRM)

| SR field | CRM field | Notes |
|----------|-----------|-------|
| `id` | `external_id` | Si CRM stocke l'ID SR pour dedup |
| `name` | `name` | Direct copy |
| `website` | `website` | Direct copy |
| `amount` | `funding_amount` | **Renommé pour clarté CRM** (BigInteger EUR) |
| `series` | `funding_series` | Renommé |
| `siren` | `siren` | **Nouveau** |
| `funding_date` | `funding_date` | **Nouveau** |
| `source_names` | `funding_sources` | **Nouveau** — JSONB list |
| `source_urls` | (n'est pas mappé) | Optionnel : custom_field si besoin du detail par source |
| `normalized_name` | (n'est pas mappé) | Cle interne SR pour dédup, pas besoin côté CRM |
| `description` | `description` | Direct |
| `sector` | `industry` | Si CRM nomme `industry`, sinon `sector` |
| `strategy` | `strategy` ou custom_field | B2B/B2C/B2B2C |
| `founders` | (n'est pas mappé) | Les fondateurs deviennent des `contacts` lors de la sync |
| `investors` | `investors` (JSONB list) | Si CRM gère, sinon custom_field |

### 6.2 `Contact` (SR) → `Contact` (CRM)

| SR field | CRM field | Notes |
|----------|-----------|-------|
| `first_name`, `last_name`, `title` | idem | Direct |
| `email` | `email` | Direct (status `unknown` = candidat) |
| `email_status` | `email_status` | `safe`/`riskier`/`unknown` |
| `linkedin_url` | `linkedin_url` | Direct |
| `is_decision_maker` | `is_decision_maker` | Direct |
| `enrichment_source` | `enrichment_source` | **Nouveau** |
| `email_pattern_used` | `email_pattern_used` | **Nouveau** |
| `linkedin_url_status` | `linkedin_url_status` | **Nouveau** |

---

## 7. Idempotence (CRITIQUE)

La sync CRM peut tourner plusieurs fois par jour. **Aucune création ne doit
être dupliquée.**

### 7.1 Lookup d'identité

| Entité | Clé d'identité | Source |
|--------|----------------|--------|
| Company | `(siren)` si renseigné, sinon `(name + website)` | SR ne fournit pas toujours le SIREN |
| Contact | `(company_id, first_name, last_name)` | Pattern utilisé côté SR |
| Activity `funding_detected` | `(company_id, type, subject)` | Subject contient amount → unique par opération |
| Task `qualification` | `(company_id, title)` | Title contient amount → unique |

### 7.2 Règles de mise à jour

```python
# Ne JAMAIS écraser un champ CRM-natif renseigné
if sr_data.get("siren") and not existing.siren:
    existing.siren = sr_data["siren"]
if sr_data.get("funding_date") and not existing.funding_date:
    existing.funding_date = date.fromisoformat(sr_data["funding_date"])

# Amount : on prend le max (BODACC peut donner None, garder l'existant)
if sr_data.get("amount") and (
    not existing.funding_amount or sr_data["amount"] > existing.funding_amount
):
    existing.funding_amount = sr_data["amount"]

# Sources : union (jamais d'écrasement)
if sr_data.get("source_names"):
    existing_sources = set(existing.funding_sources or [])
    existing.funding_sources = sorted(
        existing_sources | set(sr_data["source_names"])
    )
```

### 7.3 Ne PAS écraser le travail commercial

Si une `Company` a déjà :
- Un `Deal` en pipeline (stage != "to_engage")
- Un `lead_source` non vide (= deal créé manuellement)
- Des `custom_fields` métier

→ La sync ne doit **PAS** modifier ces champs. Le SR pousse uniquement de la data
factuelle (siren, funding_date, sources). Les jugements commerciaux restent CRM.

---

## 8. Activities + Tasks à créer

### 8.1 Activity `funding_detected`

Créée pour **chaque nouvelle Company** avec `funding_amount > 0`.

```python
async def create_funding_activity(
    db, company_id, user_id, sr_data: dict
) -> None:
    amount_eur = sr_data.get("amount", 0)
    if not amount_eur:
        return

    series = sr_data.get("series") or "Levée"
    sources = sr_data.get("source_names") or ["startup_radar"]
    investors = sr_data.get("investors") or []
    funding_date = sr_data.get("funding_date")

    amount_m = amount_eur / 1_000_000
    subject = f"Levée détectée : {amount_m:.1f}M€ ({series})"

    # Idempotence
    stmt = select(Activity).where(
        Activity.company_id == company_id,
        Activity.type == "funding_detected",
        Activity.subject == subject,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        return  # déjà créée

    metadata = {
        "amount_eur": amount_eur,
        "series": series,
        "sources": sources,
        "investors": investors[:10],  # cap pour éviter les blobs
        "funding_date": funding_date,
        "siren": sr_data.get("siren"),
    }

    content_lines = [
        f"Montant : {amount_m:.1f}M€",
        f"Série : {series}",
        f"Sources détectées : {', '.join(sources)}",
    ]
    if investors:
        content_lines.append(f"Investisseurs : {', '.join(investors[:5])}")
    content = "\n".join(content_lines)

    db.add(Activity(
        id=uuid.uuid4(),
        type="funding_detected",
        subject=subject,
        content=content,
        metadata_=metadata,
        company_id=company_id,
        user_id=user_id,
    ))
```

### 8.2 Task `qualification`

Créée pour les Companies avec `funding_amount >= 1_000_000` EUR (**seuil
validé Hervé : 1M€**).

```python
QUALIFICATION_TASK_THRESHOLD_EUR = 1_000_000  # configurable via settings

async def create_qualification_task(
    db, company_id, assigned_to, startup_name: str, amount_eur: int
) -> None:
    if amount_eur < QUALIFICATION_TASK_THRESHOLD_EUR:
        return

    amount_m = amount_eur / 1_000_000
    title = f"Qualifier la levée : {startup_name} ({amount_m:.1f}M€)"

    # Idempotence
    stmt = select(Task).where(
        Task.company_id == company_id,
        Task.title == title,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        return

    due_date = datetime.utcnow() + timedelta(days=7)

    db.add(Task(
        id=uuid.uuid4(),
        title=title,
        type="qualification",
        priority="medium",
        due_date=due_date,
        company_id=company_id,
        assigned_to=assigned_to,
        is_completed=False,
    ))
```

**Owner attribution** : pour un cron CRM automatique, prévoir un user technique
(`sync@fast-growth.fr`, role admin, non listé) ou réutiliser l'admin par défaut.
À trancher avec Hervé.

---

## 9. Phases CRM (alignées avec phases SR)

| Phase CRM | Effort | Dépend de |
|-----------|--------|-----------|
| **A** : Migration + Modèles + Schemas + Sync mapping | ~3h | SR Phase 5 mergée |
| **B** : Activities + Tasks + endpoint sync incrémentale | ~2h | Phase A validée |
| **C** : UI CRM (CompanyDetail bloc Funding, ContactDetail badges, Dashboard KPI) | ~4h | Phases A+B validées |

### 9.1 Phase A — Foundation
- Migration Alembic (DDL complet section 5)
- Extension `Company` + `Contact` ORM (section 4)
- Extension Pydantic `CompanyResponse` + `ContactResponse`
- `services/startup_radar_sync.py` : mapper les nouveaux champs (section 6.1, 6.2)
- Tests : `test_startup_radar_sync.py` cas nouveau funding, idempotence

**Gate** : `alembic upgrade head` PASS + tests pytest PASS + GET `/api/v1/companies/{id}` retourne les nouveaux champs.

### 9.2 Phase B — Auto Activities + Tasks
- `create_funding_activity()` (section 8.1)
- `create_qualification_task()` (section 8.2)
- Appels depuis `sync_startups()` après création Company
- Endpoint `POST /integrations/startup-radar/sync-recent-funding?days_back=7`
- Tests : idempotence Activity + Task (relance ne doit pas dupliquer)

### 9.3 Phase C — Frontend
- `CompanyDetail.tsx` : bloc "Levée détectée" avec amount, sources badges, SIREN
- `ContactDetail.tsx` : badges "Email candidat" / "LinkedIn à vérifier"
- `Dashboard.tsx` : KPI "Nouvelles levées cette semaine"
- `Companies.tsx` : filtres `funding_series`, `funding_amount_min`, `funding_date_after`

---

## 10. Pièges connus (DC17 + SHARED_ERRORS)

### 10.1 Côté implémentation
1. **JSONB SQLite tests (CRM ADR-002)** : `funding_sources` JSONB doit être
   mappé en JSON dans `conftest.py` pour les tests SQLite in-memory.
2. **Email candidat ≠ email vérifié** : afficher un badge "Candidat
   ({email_pattern_used})" pour `email_status="unknown"` ET
   `enrichment_source != "evaboot"`. Sinon Hervé risque d'envoyer des mails
   qui rebondiront.
3. **LinkedIn URL candidate** : précision ~30-50%. Toujours flagger
   `linkedin_url_status="candidate"`. Idéalement, ajouter un bouton
   "Vérifier" qui ouvre le Google search déjà préfiltrée.
4. **Idempotence Task** : si `funding_amount` est mis à jour à la hausse
   (BODACC arrive après LPT), le subject change → nouvelle Task créée. C'est
   probablement OK (chaque évolution mérite un check), mais à valider.
5. **Date conversion** : `funding_date` côté SR est un string `YYYY-MM-DD`
   dans la JSON. Convertir avec `date.fromisoformat()` avant `Mapped[date]`
   (cf. SHARED_ERRORS Python/FastAPI).
6. **Owner par défaut** : sync triggered par un cron a besoin d'un `user_id`.
   Trancher : user technique dédié OU admin par défaut.
7. **Volume** : BODACC peut amener ~150-200 nouvelles "Companies" par run
   (avec bruit). Sans seuil Task, le commercial est noyé. Le seuil 1M€
   filtre ~80% du bruit (la majorité des BODACC ont `amount=None` car
   BODACC ne fournit pas le ticket).
8. **Champs nullables** : `siren`, `funding_date`, `amount` peuvent être
   `null` dans la sync. Le code CRM doit toujours guard `if value:`.

### 10.2 Bugs SR rencontrés en local (pour info)
- `alembic_version` peut contenir 2 lignes après merge de branches → bloque
  toute migration. Solution : `DELETE FROM alembic_version WHERE version_num
  = '<ancienne>'`. **Vérifier avant le déploiement VPS** (cf. Phase 6 SR).
- BODACC API v1.0 obsolète, v2.1 active. Syntax dates : `dateparution >=
  "YYYY-MM-DD"` (sans préfixe `date`).
- Drift de pricing dans `llm_config.py` SR (Haiku 4.5 : code dit $0.80/$4
  vs doc Anthropic $1/$5). Cosmétique, ne casse rien.

---

## 11. Tests à écrire côté CRM

### 11.1 Unit tests
- `test_company_funding_fields.py` : modèle ORM accepte les nouveaux types
- `test_funding_activity_creation.py` :
  - Activity créée avec subject correct
  - Idempotent (relance = pas de doublon)
  - Metadata bien rempli (`amount_eur`, `series`, `sources`, etc.)
- `test_qualification_task_creation.py` :
  - Task créée pour `amount >= 1M€`
  - Pas de Task pour `amount < 1M€`
  - Idempotent

### 11.2 Integration tests `test_startup_radar_sync.py`
Mocker `StartupRadarClient` pour retourner :
- 1 startup avec siren + funding_date + sources multiples → vérifier création
  Company + Activity + Task
- 1 startup sans siren → Company créée, Activity OK, Task seulement si > 1M€
- Re-sync de la même startup → pas de doublon Company / Activity / Task
- Startup mise à jour (nouvelle source ajoutée) → `funding_sources` étendu
  sans écrasement
- Contact avec `enrichment_source="scraped_founders"` → champs propagés
- Contact avec `email_status="unknown"` → propagé tel quel (Évaboot peut
  vérifier plus tard)

### 11.3 Fixtures recommandées
Capturer 3 startups réelles depuis SR local :
- 1 startup mono-source LPT (Glimpact)
- 1 startup multi-sources Eldorado + BODACC (Aura Aero)
- 1 startup multi-sources Maddyness + LPT (à pêcher dans la base après run)

Stocker en JSON dans `backend/tests/fixtures/sr_*.json`.

---

## 12. Endpoint SR à ajouter avant Phase B (côté SR)

Pour permettre la sync incrémentale `?since=`, ajouter côté SR :

`backend/app/api/v1/startups.py` — modifier la route GET `/startups` :
```python
from datetime import datetime
from typing import Optional

@router.get("/")
async def list_startups(
    page: int = 1,
    size: int = 50,
    since: Optional[datetime] = None,  # NOUVEAU
    db: AsyncSession = Depends(get_db),
):
    query = select(Startup)
    if since:
        query = query.where(Startup.scraped_at >= since)
    # ... reste pagination
```

→ **À ajouter dans une PR séparée côté SR** (pas dans la branche actuelle
`feature/funding-multi-source`, qui est focus ingestion).

---

## 13. Checklist avant Phase A (CRM)

- [ ] PR SR `feature/funding-multi-source` mergée et déployée VPS
- [ ] Vérifier `alembic_version` côté CRM (1 seule ligne)
- [ ] Vérifier que `services/startup_radar_sync.py` côté CRM tourne sur la
      version SR avec les nouveaux champs (test : full sync, vérifier que
      les nouveaux champs SR sont bien retournés en JSON)
- [ ] Trancher : user technique pour cron CRM ou admin par défaut
- [ ] Trancher : seuil Task confirmé à 1M€ (déjà validé) ou ajustable via setting
- [ ] Endpoint SR `?since=` implémenté (ticket à part)

---

## 14. Récapitulatif des modifications cross-projets

| Composant | SR (livré) | CRM (à faire) |
|-----------|-----------|---------------|
| Migration DB | ✅ `030_funding_multi_source.py` | ⏳ `XXX_funding_multi_source_sync.py` |
| Modèles ORM | ✅ Startup, Contact, +BodaccAnnouncementSeen | ⏳ Company, Contact |
| Schemas Pydantic | ✅ `StartupResponse`, `ContactResponse` étendus | ⏳ `CompanyResponse`, `ContactResponse` |
| Services | ✅ funding_ingest, funding_dedupe, funding_normalizer, founder_enrichment | ⏳ `startup_radar_sync.py` étendu |
| API endpoints | ✅ `/scraping/multi-source`, `/scraping/enrich-founders/{id}` | ⏳ `/integrations/startup-radar/sync-recent-funding` |
| Scheduler | ✅ `daily_funding_ingest` cron | Optionnel : cron CRM 08h00 (après SR 06h00) |
| UI | ✅ (existant) + badges multi-sources Phase 6.B SR | ⏳ Bloc Funding CompanyDetail, badges Contact, KPI Dashboard, filtres Companies |
| Tests | ✅ 474 tests, scrapers + dedupe + normalizer + enrichment + ingest E2E | ⏳ `test_startup_radar_sync.py` nouveaux cas |

---

## 15. Contacts / questions

Pour toute question sur l'implémentation côté SR, consulter :
- `FUNDING_MULTI_SOURCE_INTEGRATION.md` (plan original)
- Le code dans `backend/app/services/funding_ingest.py`,
  `backend/app/scrapers/`, `backend/app/enrichment/`
- Les tests dans `backend/tests/test_funding_*.py`,
  `backend/tests/test_scraper_*.py`, `backend/tests/test_enrichment_*.py`

Pour les questions d'intégration côté CRM, contacter Hervé directement.

---

> Document complet — généré automatiquement à partir de l'implémentation SR
> validée en local le 2026-05-11 (run end-to-end : 5 LPT + 9 Maddyness +
> 22 Eldorado + 178 BODACC = 214 startups, 5 dédupliquées multi-sources,
> coût LLM total $0.022, durée pipeline complet ~32s).
