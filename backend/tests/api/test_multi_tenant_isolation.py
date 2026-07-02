# =============================================================================
# FGA CRM - Tests isolation multi-tenant (IDOR cross-org)
# =============================================================================
"""Valide empiriquement l'isolation row-level : un user de l'org A ne doit JAMAIS
voir/lire/modifier/supprimer une entite de l'org B. Le super-admin bypasse.

org A = fixture conftest `test_org` (+ test_user admin). org B = cree ici.
"""

import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.deal import Deal
from app.models.organization import Organization
from app.models.task import Task
from app.models.user import User


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token({'sub': str(user.id)})}"}


@pytest_asyncio.fixture
async def org_b(db_session: AsyncSession) -> Organization:
    org = Organization(
        id=uuid.uuid4(), name="Org B", slug=f"orgb-{uuid.uuid4().hex[:8]}", is_active=True,
    )
    db_session.add(org)
    await db_session.commit()
    return org


@pytest_asyncio.fixture
async def admin_b(db_session: AsyncSession, org_b: Organization) -> User:
    user = User(
        id=uuid.uuid4(), email="admin-b@fga.fr", hashed_password="x",
        full_name="Admin B", role="admin", is_active=True, organization_id=org_b.id,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def seed_b(db_session: AsyncSession, org_b: Organization, admin_b: User) -> dict:
    """Une entite de chaque type dans l'org B."""
    company = Company(
        id=uuid.uuid4(), name="Company B", domain="company-b.fr",
        organization_id=org_b.id, owner_id=admin_b.id,
    )
    db_session.add(company)
    await db_session.flush()
    contact = Contact(
        id=uuid.uuid4(), first_name="Contact", last_name="B", email="contact-b@b.fr",
        company_id=company.id, organization_id=org_b.id, owner_id=admin_b.id,
    )
    deal = Deal(
        id=uuid.uuid4(), title="Deal B", stage="new",
        organization_id=org_b.id, owner_id=admin_b.id,
    )
    task = Task(
        id=uuid.uuid4(), title="Task B", assigned_to=admin_b.id, organization_id=org_b.id,
    )
    activity = Activity(
        id=uuid.uuid4(), type="note", subject="Activity B",
        user_id=admin_b.id, organization_id=org_b.id,
    )
    db_session.add_all([contact, deal, task, activity])
    await db_session.commit()
    return {"company": company, "contact": contact, "deal": deal, "task": task, "activity": activity}


_PATHS = [
    ("companies", "company"),
    ("contacts", "contact"),
    ("deals", "deal"),
    ("tasks", "task"),
    ("activities", "activity"),
]


@pytest.mark.asyncio
async def test_list_excludes_other_org(client: AsyncClient, auth_headers: dict, seed_b: dict):
    """Les listes de l'org A n'exposent aucune entite de l'org B."""
    for path, key in _PATHS:
        resp = await client.get(f"/api/v1/{path}", headers=auth_headers)
        assert resp.status_code == 200, f"{path}: {resp.text}"
        ids = [it["id"] for it in resp.json()["items"]]
        assert str(seed_b[key].id) not in ids, f"FUITE cross-org sur GET /{path}"


@pytest.mark.asyncio
async def test_get_detail_other_org_404(client: AsyncClient, auth_headers: dict, seed_b: dict):
    """GET detail d'une entite de l'org B -> 404 (ne divulgue pas l'existence)."""
    for path, key in _PATHS:
        resp = await client.get(f"/api/v1/{path}/{seed_b[key].id}", headers=auth_headers)
        assert resp.status_code == 404, f"{path}: attendu 404, recu {resp.status_code}"


@pytest.mark.asyncio
async def test_delete_other_org_404(client: AsyncClient, auth_headers: dict, seed_b: dict):
    """DELETE d'une entite de l'org B -> 404, et l'entite survit."""
    for path, key in _PATHS:
        resp = await client.delete(f"/api/v1/{path}/{seed_b[key].id}", headers=auth_headers)
        assert resp.status_code == 404, f"{path}: attendu 404, recu {resp.status_code}"


@pytest.mark.asyncio
async def test_cross_fk_attach_rejected(client: AsyncClient, auth_headers: dict, seed_b: dict):
    """Impossible de rattacher un nouveau contact a la company d'une autre org."""
    resp = await client.post(
        "/api/v1/contacts",
        headers=auth_headers,
        json={"first_name": "Intrus", "last_name": "X", "company_id": str(seed_b["company"].id)},
    )
    assert resp.status_code in (404, 422), resp.text


@pytest.mark.asyncio
async def test_users_list_excludes_other_org(
    client: AsyncClient, auth_headers: dict, admin_b: User
):
    """Un admin ne voit que les users de son org."""
    resp = await client.get("/api/v1/users", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    ids = [u["id"] for u in resp.json()["items"]]
    assert str(admin_b.id) not in ids


@pytest.mark.asyncio
async def test_superadmin_sees_other_org(
    client: AsyncClient, db_session: AsyncSession, test_org, seed_b: dict
):
    """Un super-admin (org A) accede a une entite de l'org B (bypass tenant)."""
    su = User(
        id=uuid.uuid4(), email="super@fga.fr", hashed_password="x",
        full_name="Super Admin", role="admin", is_active=True,
        organization_id=test_org.id, is_superadmin=True,
    )
    db_session.add(su)
    await db_session.commit()

    resp = await client.get(f"/api/v1/companies/{seed_b['company'].id}", headers=_headers(su))
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == str(seed_b["company"].id)
