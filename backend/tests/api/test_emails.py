# =============================================================================
# FGA CRM - Tests API Emails (send + list + RBAC)
# =============================================================================

import uuid

import aiosmtplib
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.contact import Contact
from app.models.user import User

SEND_URL = "/api/v1/emails/send"
LIST_URL = "/api/v1/emails"
TEMPLATES_URL = "/api/v1/email-templates"


# ---------- Fixtures ----------


@pytest.fixture(autouse=True)
def mock_smtp(monkeypatch):
    """Mock aiosmtplib.send pour tous les tests de ce module."""
    async def fake_send(*args, **kwargs):
        return ({}, "OK")
    monkeypatch.setattr("aiosmtplib.send", fake_send)


@pytest.fixture(autouse=True)
def mock_smtp_settings(monkeypatch):
    """S'assurer que les settings SMTP sont definis pour les tests."""
    monkeypatch.setattr("app.services.email.settings.ovh_email_user", "test@fga.fr")
    monkeypatch.setattr("app.services.email.settings.ovh_email_password", "test-password")


VALID_EMAIL = {
    "to_email": "destinataire@exemple.com",
    "subject": "Bonjour",
    "body": "Ceci est un test d'envoi.",
}


# ---------- Send Email ----------


@pytest.mark.asyncio
async def test_send_email_basic(client: AsyncClient, auth_headers: dict):
    resp = await client.post(SEND_URL, json=VALID_EMAIL, headers=auth_headers)
    assert resp.status_code == 201

    data = resp.json()
    assert data["success"] is True
    assert data["activity_id"]
    assert data["sent_at"]


@pytest.mark.asyncio
async def test_send_email_with_contact(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession,
):
    # Creer un contact
    contact = Contact(
        id=uuid.uuid4(),
        first_name="Marie",
        last_name="Curie",
        email="marie@science.fr",
        owner_id=test_user.id,
    )
    db_session.add(contact)
    await db_session.commit()

    resp = await client.post(
        SEND_URL,
        json={**VALID_EMAIL, "contact_id": str(contact.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_send_email_with_template(
    client: AsyncClient,
    auth_headers: dict,
):
    # Creer un template
    tmpl_resp = await client.post(
        TEMPLATES_URL,
        json={
            "name": "Test Template",
            "subject": "Hello {{first_name}}",
            "body": "Contenu du template",
        },
        headers=auth_headers,
    )
    template_id = tmpl_resp.json()["id"]

    resp = await client.post(
        SEND_URL,
        json={**VALID_EMAIL, "template_id": template_id},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["success"] is True


@pytest.mark.asyncio
async def test_send_email_creates_activity(
    client: AsyncClient,
    auth_headers: dict,
    db_session: AsyncSession,
):
    resp = await client.post(SEND_URL, json=VALID_EMAIL, headers=auth_headers)
    assert resp.status_code == 201

    activity_id = resp.json()["activity_id"]

    # Verifier en DB que l'Activity existe avec le bon type
    result = await db_session.execute(
        select(Activity).where(Activity.id == uuid.UUID(activity_id))
    )
    activity = result.scalar_one_or_none()
    assert activity is not None
    assert activity.type == "email"
    assert activity.subject == VALID_EMAIL["subject"]
    assert activity.metadata_["to_email"] == VALID_EMAIL["to_email"]


@pytest.mark.asyncio
async def test_send_email_no_auth(client: AsyncClient):
    resp = await client.post(SEND_URL, json=VALID_EMAIL)
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_send_email_invalid_email(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        SEND_URL,
        json={**VALID_EMAIL, "to_email": "pas-un-email"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_email_missing_subject(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        SEND_URL,
        json={"to_email": "test@test.com", "body": "Hello"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_send_email_contact_not_found(client: AsyncClient, auth_headers: dict):
    resp = await client.post(
        SEND_URL,
        json={**VALID_EMAIL, "contact_id": "00000000-0000-0000-0000-000000000000"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_send_email_smtp_error(client: AsyncClient, auth_headers: dict, monkeypatch):
    """Quand SMTP echoue, retourner 503."""
    async def failing_send(*args, **kwargs):
        raise aiosmtplib.SMTPException("Connection refused")

    monkeypatch.setattr("aiosmtplib.send", failing_send)

    resp = await client.post(SEND_URL, json=VALID_EMAIL, headers=auth_headers)
    assert resp.status_code == 503


# ---------- List Emails ----------


@pytest.mark.asyncio
async def test_list_emails(client: AsyncClient, auth_headers: dict):
    # Envoyer 2 emails
    await client.post(SEND_URL, json=VALID_EMAIL, headers=auth_headers)
    await client.post(
        SEND_URL,
        json={**VALID_EMAIL, "subject": "Deuxieme email"},
        headers=auth_headers,
    )

    resp = await client.get(LIST_URL, headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert "page" in data
    assert "size" in data
    assert "pages" in data

    # Verifier les champs de chaque item
    item = data["items"][0]
    assert "id" in item
    assert "subject" in item
    assert "to_email" in item
    assert "created_at" in item


@pytest.mark.asyncio
async def test_list_emails_search(client: AsyncClient, auth_headers: dict):
    await client.post(SEND_URL, json=VALID_EMAIL, headers=auth_headers)
    await client.post(
        SEND_URL,
        json={**VALID_EMAIL, "subject": "Proposition commerciale"},
        headers=auth_headers,
    )

    resp = await client.get(LIST_URL, params={"search": "Proposition"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert "Proposition" in resp.json()["items"][0]["subject"]


@pytest.mark.asyncio
async def test_list_emails_filter_contact(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession,
):
    contact = Contact(
        id=uuid.uuid4(),
        first_name="Pierre",
        last_name="Durand",
        email="pierre@test.com",
        owner_id=test_user.id,
    )
    db_session.add(contact)
    await db_session.commit()

    # Email avec contact
    await client.post(
        SEND_URL,
        json={**VALID_EMAIL, "contact_id": str(contact.id)},
        headers=auth_headers,
    )
    # Email sans contact
    await client.post(SEND_URL, json=VALID_EMAIL, headers=auth_headers)

    resp = await client.get(
        LIST_URL,
        params={"contact_id": str(contact.id)},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


@pytest.mark.asyncio
async def test_list_emails_no_auth(client: AsyncClient):
    resp = await client.get(LIST_URL)
    assert resp.status_code in (401, 403)


# ---------- RBAC ----------


@pytest.mark.asyncio
async def test_send_email_rbac_contact_access(
    client: AsyncClient,
    sales_user: User,
    sales_headers: dict,
    sales_user_b: User,
    sales_b_headers: dict,
    db_session: AsyncSession,
):
    """Sales A ne peut pas envoyer a un contact de Sales B."""
    contact = Contact(
        id=uuid.uuid4(),
        first_name="Contact",
        last_name="De B",
        email="contact-b@test.com",
        owner_id=sales_user_b.id,
    )
    db_session.add(contact)
    await db_session.commit()

    resp = await client.post(
        SEND_URL,
        json={**VALID_EMAIL, "contact_id": str(contact.id)},
        headers=sales_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_emails_rbac_isolation(
    client: AsyncClient,
    sales_user: User,
    sales_headers: dict,
    sales_user_b: User,
    sales_b_headers: dict,
):
    """Sales A envoie un email, Sales B ne le voit pas dans la liste."""
    # Sales A envoie
    resp = await client.post(SEND_URL, json=VALID_EMAIL, headers=sales_headers)
    assert resp.status_code == 201

    # Sales A voit son email
    resp = await client.get(LIST_URL, headers=sales_headers)
    assert resp.json()["total"] == 1

    # Sales B ne voit rien
    resp = await client.get(LIST_URL, headers=sales_b_headers)
    assert resp.json()["total"] == 0
