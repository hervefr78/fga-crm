# =============================================================================
# FGA CRM - Tests Funding Sync (Phase B 2026-05)
# =============================================================================
"""Tests pour l'extension funding multi-source du sync Startup Radar :
- create_funding_activity : creation + idempotence par subject (amount+series)
- create_qualification_task : creation + idempotence sur task ouverte
- sync_startups : mapping des nouveaux champs (siren, funding_*, etc.)
- sync_contacts : mapping enrichment (enrichment_source, email_pattern_used, etc.)
- _parse_iso_date : tolerance valeurs invalides
"""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.task import Task
from app.models.user import User
from app.services.startup_radar_sync import (
    _parse_iso_date,
    create_funding_activity,
    create_qualification_task,
    sync_contacts,
    sync_startups,
)


# ---------------------------------------------------------------------------
# Mock SR Client (minimal — fournit get_startups, get_contacts, authenticate)
# ---------------------------------------------------------------------------


class _MockSRClient:
    """Mock minimal du StartupRadarClient pour tests sync."""

    def __init__(self, startups: list[dict] | None = None, contacts: list[dict] | None = None):
        self.startups = startups or []
        self.contacts = contacts or []

    async def authenticate(self) -> None:
        return None

    async def get_startups(self) -> list[dict]:
        return self.startups

    async def get_contacts(self) -> list[dict]:
        return self.contacts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_admin(db: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"admin-{uuid.uuid4().hex[:6]}@fga.fr",
        hashed_password="x",
        full_name="Admin Sync",
        role="admin",
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def _make_company(db: AsyncSession, user: User, name: str = "Acme Co") -> Company:
    company = Company(
        id=uuid.uuid4(),
        name=name,
        lead_source="startup_radar",
        owner_id=user.id,
    )
    db.add(company)
    await db.flush()
    return company


# ---------------------------------------------------------------------------
# Tests _parse_iso_date
# ---------------------------------------------------------------------------


def test_parse_iso_date_valid():
    from datetime import date as _date

    assert _parse_iso_date("2026-05-11") == _date(2026, 5, 11)


def test_parse_iso_date_none_or_empty():
    assert _parse_iso_date(None) is None
    assert _parse_iso_date("") is None


def test_parse_iso_date_invalid_returns_none():
    """Tolere les formats invalides au lieu de raise."""
    assert _parse_iso_date("not-a-date") is None
    assert _parse_iso_date("2026-13-01") is None  # mois 13 invalide
    assert _parse_iso_date("11/05/2026") is None  # format FR pas ISO


# ---------------------------------------------------------------------------
# Tests create_funding_activity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_funding_activity_creates_activity(db_session: AsyncSession):
    user = await _make_admin(db_session)
    company = await _make_company(db_session, user)

    startup_data = {
        "name": "Test Startup",
        "amount": 5_000_000,
        "series": "Serie A",
        "source_names": ["lespepitestech", "maddyness"],
        "investors": ["VC One", "VC Two"],
        "funding_date": "2026-05-01",
        "siren": "123456789",
    }

    created = await create_funding_activity(db_session, company.id, user.id, startup_data)
    assert created is True
    await db_session.flush()  # autoflush=False sur la session de test

    # Verifier que l'activity existe avec les bons champs
    stmt = select(Activity).where(
        Activity.company_id == company.id,
        Activity.type == "funding_detected",
    )
    activity = (await db_session.execute(stmt)).scalar_one()
    assert "5.0M€" in activity.subject
    assert "Serie A" in activity.subject
    assert activity.metadata_["amount_eur"] == 5_000_000
    assert activity.metadata_["siren"] == "123456789"
    assert "VC One" in activity.metadata_["investors"]


@pytest.mark.asyncio
async def test_create_funding_activity_no_amount_skipped(db_session: AsyncSession):
    """Sans amount, pas d'activity creee."""
    user = await _make_admin(db_session)
    company = await _make_company(db_session, user)

    created = await create_funding_activity(
        db_session, company.id, user.id, {"name": "x", "amount": 0},
    )
    assert created is False

    created = await create_funding_activity(
        db_session, company.id, user.id, {"name": "x"},  # pas de cle amount
    )
    assert created is False


@pytest.mark.asyncio
async def test_create_funding_activity_idempotent_same_round(db_session: AsyncSession):
    """Meme amount + meme series → pas de doublon."""
    user = await _make_admin(db_session)
    company = await _make_company(db_session, user)

    data = {"name": "x", "amount": 2_000_000, "series": "Seed"}
    assert await create_funding_activity(db_session, company.id, user.id, data) is True
    # Deuxieme appel : skip car meme subject
    assert await create_funding_activity(db_session, company.id, user.id, data) is False

    # Verifier qu'on a bien une seule activity
    stmt = select(Activity).where(
        Activity.company_id == company.id,
        Activity.type == "funding_detected",
    )
    activities = (await db_session.execute(stmt)).scalars().all()
    assert len(activities) == 1


@pytest.mark.asyncio
async def test_create_funding_activity_distinct_rounds(db_session: AsyncSession):
    """Nouveau round (amount + series different) → nouvelle activity."""
    user = await _make_admin(db_session)
    company = await _make_company(db_session, user)

    assert await create_funding_activity(
        db_session, company.id, user.id,
        {"name": "x", "amount": 1_000_000, "series": "Seed"},
    ) is True
    assert await create_funding_activity(
        db_session, company.id, user.id,
        {"name": "x", "amount": 5_000_000, "series": "Serie A"},
    ) is True

    stmt = select(Activity).where(
        Activity.company_id == company.id,
        Activity.type == "funding_detected",
    )
    activities = (await db_session.execute(stmt)).scalars().all()
    assert len(activities) == 2


# ---------------------------------------------------------------------------
# Tests create_qualification_task
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_qualification_task_creates_task(db_session: AsyncSession):
    user = await _make_admin(db_session)
    company = await _make_company(db_session, user)

    created = await create_qualification_task(
        db_session, company.id, user.id,
        {"name": "Test SAS", "amount": 5_000_000, "series": "Serie A"},
    )
    assert created is True

    stmt = select(Task).where(
        Task.company_id == company.id,
        Task.type == "qualification",
    )
    task = (await db_session.execute(stmt)).scalar_one()
    assert "Test SAS" in task.title
    assert "5.0M€" in task.title
    assert task.is_completed is False
    assert task.priority == "medium"
    assert task.due_date is not None


@pytest.mark.asyncio
async def test_create_qualification_task_idempotent_open_task(db_session: AsyncSession):
    """Une task ouverte existe deja → skip."""
    user = await _make_admin(db_session)
    company = await _make_company(db_session, user)

    data = {"name": "x", "amount": 2_000_000, "series": "Seed"}
    assert await create_qualification_task(db_session, company.id, user.id, data) is True
    # Meme contexte : ne pas creer une 2e task
    assert await create_qualification_task(db_session, company.id, user.id, data) is False

    stmt = select(Task).where(
        Task.company_id == company.id,
        Task.type == "qualification",
    )
    tasks = (await db_session.execute(stmt)).scalars().all()
    assert len(tasks) == 1


@pytest.mark.asyncio
async def test_create_qualification_task_recreates_after_completion(db_session: AsyncSession):
    """Une task completee n'empeche pas la creation d'une nouvelle (round suivant)."""
    user = await _make_admin(db_session)
    company = await _make_company(db_session, user)

    data = {"name": "x", "amount": 2_000_000, "series": "Seed"}
    assert await create_qualification_task(db_session, company.id, user.id, data) is True

    # Marquer la premiere task comme completee
    stmt = select(Task).where(Task.company_id == company.id, Task.type == "qualification")
    task = (await db_session.execute(stmt)).scalar_one()
    task.is_completed = True
    await db_session.flush()

    # Maintenant on peut creer une nouvelle (nouveau round 6 mois plus tard)
    data2 = {"name": "x", "amount": 10_000_000, "series": "Serie A"}
    assert await create_qualification_task(db_session, company.id, user.id, data2) is True

    stmt_all = select(Task).where(
        Task.company_id == company.id, Task.type == "qualification",
    )
    all_tasks = (await db_session.execute(stmt_all)).scalars().all()
    assert len(all_tasks) == 2


@pytest.mark.asyncio
async def test_create_qualification_task_no_amount_skipped(db_session: AsyncSession):
    user = await _make_admin(db_session)
    company = await _make_company(db_session, user)
    assert await create_qualification_task(
        db_session, company.id, user.id, {"name": "x", "amount": 0},
    ) is False


# ---------------------------------------------------------------------------
# Tests sync_startups : nouveau mapping funding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_startups_maps_new_funding_fields_on_insert(db_session: AsyncSession):
    """Une nouvelle startup SR avec funding fields → Company avec tous les champs."""
    user = await _make_admin(db_session)
    mock_client = _MockSRClient(startups=[{
        "id": "sr-funding-1",
        "name": "NewFunded Co",
        "website": "https://newfunded.example",
        "sector": "SaaS",
        "siren": "987654321",
        "funding_date": "2026-04-15",
        "amount": 8_000_000,
        "series": "Serie B",
        "source_names": ["eldorado", "bodacc"],
        "investors": ["Big VC"],
    }])

    result, sr_to_crm = await sync_startups(db_session, mock_client, user)  # type: ignore[arg-type]

    assert result.companies_created == 1
    assert result.funding_activities_created == 1
    assert result.qualification_tasks_created == 1

    # Recharger la company
    company = (await db_session.execute(
        select(Company).where(Company.startup_radar_id == "sr-funding-1")
    )).scalar_one()
    assert company.siren == "987654321"
    assert company.funding_amount == 8_000_000
    assert company.funding_series == "Serie B"
    assert company.funding_sources == ["eldorado", "bodacc"]
    assert company.funding_date is not None
    assert company.funding_date.isoformat() == "2026-04-15"


@pytest.mark.asyncio
async def test_sync_startups_merges_funding_sources_on_update(db_session: AsyncSession):
    """Update : merge des funding_sources existantes + nouvelles."""
    user = await _make_admin(db_session)

    # 1er sync : 1 source
    mock_client = _MockSRClient(startups=[{
        "id": "sr-merge-1",
        "name": "MergeCo",
        "amount": 1_000_000,
        "series": "Seed",
        "source_names": ["lespepitestech"],
    }])
    await sync_startups(db_session, mock_client, user)  # type: ignore[arg-type]

    # 2eme sync : nouvelle source ajoutee
    mock_client2 = _MockSRClient(startups=[{
        "id": "sr-merge-1",
        "name": "MergeCo",
        "amount": 1_000_000,
        "series": "Seed",
        "source_names": ["maddyness"],  # nouvelle source
    }])
    await sync_startups(db_session, mock_client2, user)  # type: ignore[arg-type]

    company = (await db_session.execute(
        select(Company).where(Company.startup_radar_id == "sr-merge-1")
    )).scalar_one()
    # Sources mergees (tri alpha)
    assert set(company.funding_sources) == {"lespepitestech", "maddyness"}


@pytest.mark.asyncio
async def test_sync_startups_keeps_highest_amount_on_update(db_session: AsyncSession):
    """Update : garde le montant le plus eleve (round le plus important)."""
    user = await _make_admin(db_session)
    mock_client = _MockSRClient(startups=[{
        "id": "sr-amount-1", "name": "AmountCo", "amount": 2_000_000, "series": "Seed",
    }])
    await sync_startups(db_session, mock_client, user)  # type: ignore[arg-type]

    # Nouveau round, montant plus eleve
    mock_client2 = _MockSRClient(startups=[{
        "id": "sr-amount-1", "name": "AmountCo", "amount": 10_000_000, "series": "Serie A",
    }])
    await sync_startups(db_session, mock_client2, user)  # type: ignore[arg-type]

    company = (await db_session.execute(
        select(Company).where(Company.startup_radar_id == "sr-amount-1")
    )).scalar_one()
    assert company.funding_amount == 10_000_000

    # Round suivant avec montant plus faible → ne pas regresser
    mock_client3 = _MockSRClient(startups=[{
        "id": "sr-amount-1", "name": "AmountCo", "amount": 500_000, "series": "Pre-seed",
    }])
    await sync_startups(db_session, mock_client3, user)  # type: ignore[arg-type]

    company2 = (await db_session.execute(
        select(Company).where(Company.startup_radar_id == "sr-amount-1")
    )).scalar_one()
    assert company2.funding_amount == 10_000_000  # inchange


@pytest.mark.asyncio
async def test_sync_startups_invalid_funding_date_tolerated(db_session: AsyncSession):
    """Une funding_date invalide ne bloque pas l'insert (champs autres OK)."""
    user = await _make_admin(db_session)
    mock_client = _MockSRClient(startups=[{
        "id": "sr-bad-date",
        "name": "BadDateCo",
        "amount": 1_000_000,
        "series": "Seed",
        "funding_date": "invalid-date-string",
    }])

    result, _ = await sync_startups(db_session, mock_client, user)  # type: ignore[arg-type]
    assert result.companies_created == 1
    assert result.errors == []  # pas d'erreur fatale

    company = (await db_session.execute(
        select(Company).where(Company.startup_radar_id == "sr-bad-date")
    )).scalar_one()
    assert company.funding_date is None  # tolere → None
    assert company.funding_amount == 1_000_000  # le reste OK


# ---------------------------------------------------------------------------
# Tests sync_contacts : mapping enrichment
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sync_contacts_maps_enrichment_fields(db_session: AsyncSession):
    """Contacts avec enrichment fields → Contact avec tous les champs."""
    user = await _make_admin(db_session)
    company = await _make_company(db_session, user)

    sr_to_crm = {"sr-startup-1": company.id}
    mock_client = _MockSRClient(contacts=[{
        "id": "sr-contact-1",
        "first_name": "Alice",
        "last_name": "Martin",
        "email": "alice@example.com",
        "email_status": "unknown",
        "title": "CEO",
        "linkedin_url": "https://linkedin.com/in/alicemartin",
        "is_decision_maker": True,
        "startup_id": "sr-startup-1",
        "enrichment_source": "pappers",
        "email_pattern_used": "first.last",
        "linkedin_url_status": "candidate",
    }])

    result = await sync_contacts(db_session, mock_client, user, sr_to_crm)  # type: ignore[arg-type]
    assert result.contacts_created == 1

    contact = (await db_session.execute(
        select(Contact).where(Contact.startup_radar_id == "sr-contact-1")
    )).scalar_one()
    assert contact.enrichment_source == "pappers"
    assert contact.email_pattern_used == "first.last"
    assert contact.linkedin_url_status == "candidate"
    assert contact.company_id == company.id


@pytest.mark.asyncio
async def test_sync_contacts_email_pattern_preserved_on_update(db_session: AsyncSession):
    """email_pattern_used : conserve la premiere valeur (heuristique stable)."""
    user = await _make_admin(db_session)
    company = await _make_company(db_session, user)
    sr_to_crm = {"sr-startup-2": company.id}

    # 1er sync : pattern "first.last"
    mock_client = _MockSRClient(contacts=[{
        "id": "sr-contact-2",
        "first_name": "Bob",
        "last_name": "Smith",
        "startup_id": "sr-startup-2",
        "email_pattern_used": "first.last",
    }])
    await sync_contacts(db_session, mock_client, user, sr_to_crm)  # type: ignore[arg-type]

    # 2eme sync : pattern different → pas ecrase
    mock_client2 = _MockSRClient(contacts=[{
        "id": "sr-contact-2",
        "first_name": "Bob",
        "last_name": "Smith",
        "startup_id": "sr-startup-2",
        "email_pattern_used": "flast",
    }])
    await sync_contacts(db_session, mock_client2, user, sr_to_crm)  # type: ignore[arg-type]

    contact = (await db_session.execute(
        select(Contact).where(Contact.startup_radar_id == "sr-contact-2")
    )).scalar_one()
    assert contact.email_pattern_used == "first.last"  # premiere valeur conservee


@pytest.mark.asyncio
async def test_sync_contacts_linkedin_status_overwritable(db_session: AsyncSession):
    """linkedin_url_status : ecrasable (candidate → verified par revue manuelle SR)."""
    user = await _make_admin(db_session)
    company = await _make_company(db_session, user)
    sr_to_crm = {"sr-startup-3": company.id}

    mock_client = _MockSRClient(contacts=[{
        "id": "sr-contact-3",
        "first_name": "Carol",
        "last_name": "Doe",
        "startup_id": "sr-startup-3",
        "linkedin_url_status": "candidate",
    }])
    await sync_contacts(db_session, mock_client, user, sr_to_crm)  # type: ignore[arg-type]

    mock_client2 = _MockSRClient(contacts=[{
        "id": "sr-contact-3",
        "first_name": "Carol",
        "last_name": "Doe",
        "startup_id": "sr-startup-3",
        "linkedin_url_status": "verified",
    }])
    await sync_contacts(db_session, mock_client2, user, sr_to_crm)  # type: ignore[arg-type]

    contact = (await db_session.execute(
        select(Contact).where(Contact.startup_radar_id == "sr-contact-3")
    )).scalar_one()
    assert contact.linkedin_url_status == "verified"
