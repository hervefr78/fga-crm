# =============================================================================
# FGA CRM - Tests API Drafts Review (proxy compass-core)
# =============================================================================
# On mocke les appels HTTP compass-core en stubbant les methodes du
# CompassClient (le repo ne dispose pas de respx — meme approche que les autres
# tests : monkeypatch / dependency_overrides).

from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from app.api.v1.drafts_review import get_compass_client
from app.main import app

# ---------------------------------------------------------------------------
# Constantes & helpers
# ---------------------------------------------------------------------------

PENDING_URL = "/api/v1/drafts-review/pending"
EXPORT_URL = "/api/v1/drafts-review/export.csv"


def _draft_payload(**overrides) -> dict:
    """Reponse JSON compass-core type (shape DraftRecord)."""
    base = {
        "draft_id": "d-123",
        "lead_id": "lead-1",
        "type": "linkedin_dm",
        "content": "Bonjour, ravi de vous contacter.",
        "status": "to-review",
        "brand": "fga",
        "sequence_day": 1,
        "voice_pack_used": "fga-voice-v1",
        "voice_check_passed": True,
        "published_url": None,
        "created_by": "mcp",
        "created_at": datetime(2026, 6, 23, 10, 0, 0, tzinfo=UTC).isoformat(),
        "metadata": {"source": "test"},
    }
    base.update(overrides)
    return base


class FakeCompassClient:
    """Stub du CompassClient : enregistre les appels et renvoie des reponses."""

    def __init__(self):
        self.pending_calls: list[dict] = []
        self.status_calls: list[dict] = []
        self.get_calls: list[str] = []
        self.list_calls: list[dict] = []
        # Reponses configurables par test.
        self.pending_response: list[dict] = []
        self.list_response: list[dict] = []
        self.draft_response: dict = _draft_payload()
        self.status_response: dict = _draft_payload(status="approved")
        # Exception a lever (pour tester 404/502/503).
        self.raise_exc: Exception | None = None

    async def list_pending_drafts(self, brand, max_age_hours):
        self.pending_calls.append({"brand": brand, "max_age_hours": max_age_hours})
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.pending_response

    async def list_drafts_by_status(self, status, brand, limit=1000):
        self.list_calls.append({"status": status, "brand": brand, "limit": limit})
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.list_response

    async def get_draft(self, draft_id):
        self.get_calls.append(draft_id)
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.draft_response

    async def update_draft_status(self, draft_id, status, reviewer):
        self.status_calls.append(
            {"draft_id": draft_id, "status": status, "reviewer": reviewer}
        )
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.status_response


@pytest.fixture
def fake_compass():
    """Override la dependance get_compass_client par un stub, restaure apres."""
    fake = FakeCompassClient()
    app.dependency_overrides[get_compass_client] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_compass_client, None)


# ---------------------------------------------------------------------------
# Auth — toutes les routes exigent un user authentifie
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pending_requires_auth(client: AsyncClient, fake_compass: FakeCompassClient):
    """Sans header d'auth → 401, et compass n'est jamais appele."""
    resp = await client.get(PENDING_URL)
    assert resp.status_code == 401, resp.text
    assert fake_compass.pending_calls == []


@pytest.mark.asyncio
async def test_get_draft_requires_auth(client: AsyncClient, fake_compass: FakeCompassClient):
    resp = await client.get("/api/v1/drafts-review/d-123")
    assert resp.status_code == 401, resp.text
    assert fake_compass.get_calls == []


@pytest.mark.asyncio
async def test_patch_status_requires_auth(client: AsyncClient, fake_compass: FakeCompassClient):
    resp = await client.patch(
        "/api/v1/drafts-review/d-123/status", json={"status": "approved"}
    )
    assert resp.status_code == 401, resp.text
    assert fake_compass.status_calls == []


# ---------------------------------------------------------------------------
# GET /pending — forward brand + max_age, renvoie la liste
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pending_forwards_brand_and_max_age(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    """brand + max_age_hours sont forwardes ; la liste est renvoyee."""
    fake_compass.pending_response = [_draft_payload(draft_id="d-1"), _draft_payload(draft_id="d-2")]

    resp = await client.get(
        PENDING_URL, params={"brand": "nomo", "max_age_hours": 72}, headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data) == 2
    assert data[0]["draft_id"] == "d-1"
    assert data[0]["metadata"] == {"source": "test"}

    # Verifie le forward exact
    assert fake_compass.pending_calls == [{"brand": "nomo", "max_age_hours": 72}]


@pytest.mark.asyncio
async def test_pending_default_max_age(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    """Sans max_age_hours → defaut 48 ; sans brand → None."""
    resp = await client.get(PENDING_URL, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert fake_compass.pending_calls == [{"brand": None, "max_age_hours": 48}]


@pytest.mark.asyncio
async def test_pending_invalid_brand_422(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    """brand hors {fga,nomo,ppd} → 422, compass non appele."""
    resp = await client.get(
        PENDING_URL, params={"brand": "evil"}, headers=auth_headers
    )
    assert resp.status_code == 422, resp.text
    assert fake_compass.pending_calls == []


@pytest.mark.asyncio
async def test_pending_max_age_out_of_bounds_422(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    """max_age_hours hors bornes (>720) → 422."""
    resp = await client.get(
        PENDING_URL, params={"max_age_hours": 10000}, headers=auth_headers
    )
    assert resp.status_code == 422, resp.text

    resp = await client.get(
        PENDING_URL, params={"max_age_hours": 0}, headers=auth_headers
    )
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# GET /{draft_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_draft_returns_draft(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    fake_compass.draft_response = _draft_payload(draft_id="d-abc")
    resp = await client.get("/api/v1/drafts-review/d-abc", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["draft_id"] == "d-abc"
    assert fake_compass.get_calls == ["d-abc"]


@pytest.mark.asyncio
async def test_get_draft_404_passthrough(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    """compass 404 → 404 cote CRM."""
    from app.services.compass import CompassNotFoundError

    fake_compass.raise_exc = CompassNotFoundError("not found")
    resp = await client.get("/api/v1/drafts-review/missing", headers=auth_headers)
    assert resp.status_code == 404, resp.text


@pytest.mark.asyncio
async def test_get_draft_service_error_502(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    """compass non-2xx (hors 404) → 502 cote CRM."""
    from app.services.compass import CompassServiceError

    fake_compass.raise_exc = CompassServiceError("boom")
    resp = await client.get("/api/v1/drafts-review/d-1", headers=auth_headers)
    assert resp.status_code == 502, resp.text


# ---------------------------------------------------------------------------
# PATCH /{draft_id}/status — reviewer impose server-side (DC18)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_status_sets_reviewer_to_current_user(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    """Le reviewer envoye a compass = email du user authentifie (test@fga.fr)."""
    resp = await client.patch(
        "/api/v1/drafts-review/d-123/status",
        json={"status": "approved"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text

    assert len(fake_compass.status_calls) == 1
    call = fake_compass.status_calls[0]
    assert call["draft_id"] == "d-123"
    assert call["status"] == "approved"
    # DC18 : reviewer = email du user authentifie (defini dans conftest)
    assert call["reviewer"] == "test@fga.fr"


@pytest.mark.asyncio
async def test_patch_status_ignores_client_reviewer(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    """Un reviewer fourni par le client est rejete (extra='forbid' → 422)."""
    resp = await client.patch(
        "/api/v1/drafts-review/d-123/status",
        json={"status": "approved", "reviewer": "attacker@evil.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text
    assert fake_compass.status_calls == []


@pytest.mark.asyncio
async def test_patch_status_invalid_status_422(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    """status hors {approved,rejected,to-review} → 422."""
    resp = await client.patch(
        "/api/v1/drafts-review/d-123/status",
        json={"status": "deleted"},
        headers=auth_headers,
    )
    assert resp.status_code == 422, resp.text
    assert fake_compass.status_calls == []


@pytest.mark.asyncio
async def test_patch_status_404_passthrough(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    from app.services.compass import CompassNotFoundError

    fake_compass.raise_exc = CompassNotFoundError("not found")
    resp = await client.patch(
        "/api/v1/drafts-review/missing/status",
        json={"status": "rejected"},
        headers=auth_headers,
    )
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# 503 — compass non configure (fail loud, DC2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pending_503_when_not_configured(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    """compass_api_url/key vides → 503 (proxy desactive)."""
    from app.services.compass import CompassNotConfiguredError

    fake_compass.raise_exc = CompassNotConfiguredError("compass not configured")
    resp = await client.get(PENDING_URL, headers=auth_headers)
    assert resp.status_code == 503, resp.text
    assert "not configured" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_not_configured_uses_real_client(
    client: AsyncClient, auth_headers: dict
):
    """Sans override : un client reel non configure (settings vides) → 503.

    Verifie le chemin reel _ensure_configured sans toucher au reseau.
    """
    import app.services.compass as compass_module
    from app.config import settings

    # On force la config a vide (defaut du repo) pour ce test.
    # settings est partage : on sauvegarde/restaure manuellement.
    old_url = settings.compass_api_url
    old_key = settings.compass_service_api_key
    settings.compass_api_url = ""
    settings.compass_service_api_key = ""
    # Reinitialise le client partage pour qu'il relise les settings vides.
    compass_module._compass_client = None
    try:
        resp = await client.get(PENDING_URL, headers=auth_headers)
        assert resp.status_code == 503, resp.text
        assert "not configured" in resp.json()["detail"].lower()
    finally:
        settings.compass_api_url = old_url
        settings.compass_service_api_key = old_key
        compass_module._compass_client = None


# ---------------------------------------------------------------------------
# GET /export.csv — export HeyReach (drafts approuves + identite contact CRM)
# ---------------------------------------------------------------------------


import csv  # noqa: E402  (import groupe avec les helpers d'export ci-dessous)
import io  # noqa: E402
import uuid  # noqa: E402


def _parse_csv(text: str) -> tuple[list[str], list[dict[str, str]]]:
    """Parse le CSV exporte en (header, lignes-en-dicts)."""
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    header = rows[0]
    data = [dict(zip(header, r, strict=True)) for r in rows[1:]]
    return header, data


async def _seed_two_contacts(db_session):
    """Seed 2 contacts : un AVEC linkedin_url + company, un SANS linkedin_url.

    Retourne (id_with_url, id_without_url) en str (UUID).
    """
    from app.models.company import Company
    from app.models.contact import Contact

    company = Company(id=uuid.uuid4(), name="Acme Corp")
    db_session.add(company)

    c_with = Contact(
        id=uuid.uuid4(),
        first_name="Alice",
        last_name="Martin",
        linkedin_url="https://linkedin.com/in/alice-martin",
        company_id=company.id,
    )
    c_without = Contact(
        id=uuid.uuid4(),
        first_name="Bob",
        last_name="Durand",
        linkedin_url=None,
    )
    db_session.add(c_with)
    db_session.add(c_without)
    await db_session.commit()
    return str(c_with.id), str(c_without.id)


@pytest.mark.asyncio
async def test_export_requires_auth(client: AsyncClient, fake_compass: FakeCompassClient):
    """Sans header d'auth → 401, et compass n'est jamais appele."""
    resp = await client.get(EXPORT_URL)
    assert resp.status_code == 401, resp.text
    assert fake_compass.list_calls == []


@pytest.mark.asyncio
async def test_export_pivots_and_skips_missing_url(
    client: AsyncClient,
    auth_headers: dict,
    fake_compass: FakeCompassClient,
    db_session,
):
    """CSV : header + 1 ligne (lead avec url+invitation), pivot invit/dm/relance.

    Le lead sans linkedin_url est skippe ; X-Skipped-Count le reflete.
    """
    id_with, id_without = await _seed_two_contacts(db_session)

    # Lead AVEC url : 3 drafts (invitation + dm + relance) partageant le lead_id.
    # Lead SANS url : 1 invitation (sera skippe car contact sans linkedin_url).
    fake_compass.list_response = [
        _draft_payload(
            draft_id="d-inv",
            lead_id=id_with,
            type="linkedin_invitation",
            content="Bonjour Alice, ravi de me connecter.",
            status="approved",
        ),
        _draft_payload(
            draft_id="d-dm",
            lead_id=id_with,
            type="linkedin_dm",
            content="Merci pour la connexion !",
            status="approved",
        ),
        _draft_payload(
            draft_id="d-rel",
            lead_id=id_with,
            type="linkedin_relance",
            content="Petite relance.",
            status="approved",
        ),
        _draft_payload(
            draft_id="d-inv2",
            lead_id=id_without,
            type="linkedin_invitation",
            content="Bonjour Bob.",
            status="approved",
        ),
    ]

    resp = await client.get(EXPORT_URL, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in resp.headers["content-disposition"]
    assert "heyreach_all.csv" in resp.headers["content-disposition"]

    # Le lead sans url est skippe.
    assert resp.headers["x-skipped-count"] == "1"
    assert "X-Skipped-Count" in resp.headers["access-control-expose-headers"]

    header, data = _parse_csv(resp.text)
    assert header == [
        "first_name",
        "last_name",
        "linkedin_url",
        "company",
        "brand",
        "invitation",
        "dm_followup",
        "final_relance",
    ]
    assert len(data) == 1
    row = data[0]
    assert row["first_name"] == "Alice"
    assert row["last_name"] == "Martin"
    assert row["linkedin_url"] == "https://linkedin.com/in/alice-martin"
    assert row["company"] == "Acme Corp"
    assert row["brand"] == "fga"
    # Pivot : chaque type dans la bonne colonne.
    assert row["invitation"] == "Bonjour Alice, ravi de me connecter."
    assert row["dm_followup"] == "Merci pour la connexion !"
    assert row["final_relance"] == "Petite relance."


@pytest.mark.asyncio
async def test_export_forwards_brand_to_compass(
    client: AsyncClient,
    auth_headers: dict,
    fake_compass: FakeCompassClient,
    db_session,
):
    """brand est forwarde a compass (status='approved', limit=1000)."""
    fake_compass.list_response = []
    resp = await client.get(EXPORT_URL, params={"brand": "nomo"}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    assert fake_compass.list_calls == [
        {"status": "approved", "brand": "nomo", "limit": 1000}
    ]
    # Filename reflete le brand.
    assert "heyreach_nomo.csv" in resp.headers["content-disposition"]
    # Aucun draft → header seul, 0 ligne, 0 skip.
    _, data = _parse_csv(resp.text)
    assert data == []
    assert resp.headers["x-skipped-count"] == "0"


@pytest.mark.asyncio
async def test_export_503_when_not_configured(
    client: AsyncClient, auth_headers: dict, fake_compass: FakeCompassClient
):
    """compass non configure → 503."""
    from app.services.compass import CompassNotConfiguredError

    fake_compass.raise_exc = CompassNotConfiguredError("compass not configured")
    resp = await client.get(EXPORT_URL, headers=auth_headers)
    assert resp.status_code == 503, resp.text
    assert "not configured" in resp.json()["detail"].lower()
