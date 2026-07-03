# =============================================================================
# FGA CRM - Tests Import CSV (Contacts + Companies)
# =============================================================================

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.contact import Contact


@pytest.mark.asyncio
async def test_import_contacts_valid(client: AsyncClient, auth_headers: dict):
    """Import de contacts valides."""
    response = await client.post("/api/v1/contacts/import", json={
        "rows": [
            {"first_name": "Alice", "last_name": "Import1"},
            {"first_name": "Bob", "last_name": "Import2", "email": "bob@test.com"},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert len(data["errors"]) == 0


@pytest.mark.asyncio
async def test_import_contacts_mixed(client: AsyncClient, auth_headers: dict):
    """Import mix valide/invalide : les valides passent, erreurs collectees."""
    response = await client.post("/api/v1/contacts/import", json={
        "rows": [
            {"first_name": "Valid", "last_name": "Contact"},
            {"first_name": "", "last_name": "Invalid"},  # first_name vide
            {"first_name": "Also", "last_name": "Valid"},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert len(data["errors"]) >= 1
    assert data["errors"][0]["row"] == 2


@pytest.mark.asyncio
async def test_import_contacts_all_invalid(client: AsyncClient, auth_headers: dict):
    """Import ou toutes les lignes sont invalides."""
    response = await client.post("/api/v1/contacts/import", json={
        "rows": [
            {"last_name": "Missing First"},  # first_name manquant
            {"first_name": "A", "last_name": "B", "status": "invalid_status"},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert len(data["errors"]) >= 2


@pytest.mark.asyncio
async def test_import_contacts_empty(client: AsyncClient, auth_headers: dict):
    """Import avec une liste vide."""
    response = await client.post("/api/v1/contacts/import", json={
        "rows": [],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert len(data["errors"]) == 0


@pytest.mark.asyncio
async def test_import_contacts_unauthenticated(client: AsyncClient):
    """Import sans token = 403."""
    response = await client.post("/api/v1/contacts/import", json={"rows": []})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_import_companies_valid(client: AsyncClient, auth_headers: dict):
    """Import d'entreprises valides."""
    response = await client.post("/api/v1/companies/import", json={
        "rows": [
            {"name": "ImportCo1"},
            {"name": "ImportCo2", "country": "France", "size_range": "11-50"},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 2
    assert len(data["errors"]) == 0


@pytest.mark.asyncio
async def test_import_companies_invalid_size_range(client: AsyncClient, auth_headers: dict):
    """Import avec size_range invalide."""
    response = await client.post("/api/v1/companies/import", json={
        "rows": [
            {"name": "BadCo", "size_range": "not-a-range"},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert len(data["errors"]) >= 1
    assert data["errors"][0]["field"] == "size_range"


@pytest.mark.asyncio
async def test_import_companies_missing_name(client: AsyncClient, auth_headers: dict):
    """Import sans nom d'entreprise."""
    response = await client.post("/api/v1/companies/import", json={
        "rows": [
            {"country": "France"},  # name manquant
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert len(data["errors"]) >= 1


# ---------------------------------------------------------------------------
# FIX #1 — IntegrityError (collision d'unicite) isolee par ligne, batch preserve
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_import_companies_duplicate_domain_in_batch(
    client: AsyncClient, auth_headers: dict, db_session: AsyncSession,
):
    """FIX #1 : deux lignes avec le meme domaine -> 200, la 1re est importee,
    la 2e est signalee (pas de 500, pas de batch entierement perdu)."""
    response = await client.post("/api/v1/companies/import", json={
        "rows": [
            {"name": "A", "domain": "acme.com"},
            {"name": "B", "domain": "acme.com"},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 2
    assert data["errors"][0]["field"] == "domain"

    # La 1re societe EST bien creee en base (le batch n'est pas perdu).
    row = (await db_session.execute(
        select(Company).where(Company.name == "A")
    )).scalar_one_or_none()
    assert row is not None
    assert row.domain == "acme.com"


@pytest.mark.asyncio
async def test_import_companies_domain_already_in_org(
    client: AsyncClient, auth_headers: dict, test_user, db_session: AsyncSession,
):
    """FIX #1 : un domaine deja present dans l'org -> erreur ligne, pas de 500."""
    existing = Company(
        name="Existing", domain="taken.com",
        owner_id=test_user.id, organization_id=test_user.organization_id,
    )
    db_session.add(existing)
    await db_session.commit()

    response = await client.post("/api/v1/companies/import", json={
        "rows": [{"name": "New", "domain": "taken.com"}],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 0
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 1
    assert data["errors"][0]["field"] == "domain"


@pytest.mark.asyncio
async def test_import_contacts_integrity_error_isolated(
    client: AsyncClient, auth_headers: dict, monkeypatch,
):
    """FIX #1 : une IntegrityError DB sur une ligne n'avorte pas tout le batch
    (200, pas 500). Contact n'a pas de contrainte unique naturelle sur email ->
    on INJECTE une IntegrityError sur la ligne marquee pour prouver l'isolation
    par savepoint (le flush par ligne dans begin_nested)."""
    marker = "boom@dup.test"
    original_flush = AsyncSession.flush

    async def flaky_flush(self, *args, **kwargs):
        # Simule une violation d'integrite DB uniquement sur la ligne marquee.
        if any(isinstance(o, Contact) and o.email == marker for o in self.new):
            raise IntegrityError("INSERT", {}, Exception("forced integrity error"))
        return await original_flush(self, *args, **kwargs)

    monkeypatch.setattr(AsyncSession, "flush", flaky_flush)

    response = await client.post("/api/v1/contacts/import", json={
        "rows": [
            {"first_name": "Ok", "last_name": "Row"},
            {"first_name": "Bad", "last_name": "Row", "email": marker},
        ],
    }, headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 2
