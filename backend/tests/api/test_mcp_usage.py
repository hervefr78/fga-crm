# =============================================================================
# FGA CRM - Tests API MCP Usage (ingest + summary + by-tool)
# =============================================================================
"""Couverture :
- POST /ingest : auth service-scope requise, upsert idempotent (cumul), 422 si vide
- GET /summary : agregation par tool, cout multi-modeles, auth admin, bornes dates
- GET /by-tool : detail par (jour, modele), cout, auth admin
"""

import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.services.api_keys import create_api_key

EUR = settings.eur_usd
TODAY = date(2026, 6, 30).isoformat()


# ---------------------------------------------------------------------------
# Fixtures : service account + cle avec scope write:mcp_usage
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def mcp_service_user(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="mcp-usage@crm.internal",
        hashed_password="$2b$12$disabled",
        full_name="MCP Usage Service",
        role="service",
        is_active=True,
        is_service=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def mcp_write_headers(
    db_session: AsyncSession, mcp_service_user: User
) -> dict[str, str]:
    """Cle service avec le scope write:mcp_usage."""
    _, raw_key = await create_api_key(
        db=db_session,
        user_id=mcp_service_user.id,
        name="mcp-usage-key",
        scopes=["write:mcp_usage"],
    )
    await db_session.commit()
    return {"Authorization": f"Bearer {raw_key}"}


@pytest_asyncio.fixture
async def mcp_readonly_headers(
    db_session: AsyncSession, mcp_service_user: User
) -> dict[str, str]:
    """Cle service SANS le scope write:mcp_usage (read only)."""
    _, raw_key = await create_api_key(
        db=db_session,
        user_id=mcp_service_user.id,
        name="mcp-readonly-key",
        scopes=["read:deals"],
    )
    await db_session.commit()
    return {"Authorization": f"Bearer {raw_key}"}


def _event(**kwargs) -> dict:
    base = {
        "day": TODAY,
        "tool_name": "unipile_get_messages",
        "model": "claude-haiku-4-5-20251001",
        "calls": 1,
        "input_tokens": 1000,
        "output_tokens": 500,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Ingest — auth
# ---------------------------------------------------------------------------

class TestIngestAuth:
    async def test_ingest_requires_service_key(self, client: AsyncClient):
        """Sans cle service -> 401."""
        resp = await client.post(
            "/api/v1/mcp-usage/ingest", json={"events": [_event()]}
        )
        assert resp.status_code == 401

    async def test_ingest_wrong_scope_forbidden(
        self, client: AsyncClient, mcp_readonly_headers: dict
    ):
        """Cle sans scope write:mcp_usage -> 403."""
        resp = await client.post(
            "/api/v1/mcp-usage/ingest",
            json={"events": [_event()]},
            headers=mcp_readonly_headers,
        )
        assert resp.status_code == 403

    async def test_ingest_jwt_admin_rejected(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Un JWT admin (pas une cle service) -> 401 (endpoint service-auth)."""
        resp = await client.post(
            "/api/v1/mcp-usage/ingest",
            json={"events": [_event()]},
            headers=auth_headers,
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Ingest — comportement + upsert
# ---------------------------------------------------------------------------

class TestIngestBehavior:
    async def test_ingest_ok(self, client: AsyncClient, mcp_write_headers: dict):
        resp = await client.post(
            "/api/v1/mcp-usage/ingest",
            json={"events": [_event(), _event(tool_name="other_tool")]},
            headers=mcp_write_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["ingested"] == 2

    async def test_ingest_empty_events_422(
        self, client: AsyncClient, mcp_write_headers: dict
    ):
        """Batch vide rejete (min_length=1, DC1)."""
        resp = await client.post(
            "/api/v1/mcp-usage/ingest", json={"events": []}, headers=mcp_write_headers
        )
        assert resp.status_code == 422

    async def test_ingest_negative_tokens_422(
        self, client: AsyncClient, mcp_write_headers: dict
    ):
        resp = await client.post(
            "/api/v1/mcp-usage/ingest",
            json={"events": [_event(input_tokens=-5)]},
            headers=mcp_write_headers,
        )
        assert resp.status_code == 422

    async def test_upsert_idempotent_cumulates(
        self, client: AsyncClient, mcp_write_headers: dict, auth_headers: dict
    ):
        """2 ingests de la MEME cle -> sommes cumulees (pas ecrasees)."""
        ev = _event(calls=2, input_tokens=1000, output_tokens=400)
        r1 = await client.post(
            "/api/v1/mcp-usage/ingest", json={"events": [ev]}, headers=mcp_write_headers
        )
        assert r1.status_code == 200
        r2 = await client.post(
            "/api/v1/mcp-usage/ingest", json={"events": [ev]}, headers=mcp_write_headers
        )
        assert r2.status_code == 200

        # Verifier via summary : calls et tokens doivent etre doubles
        summary = await client.get(
            f"/api/v1/mcp-usage/summary?date_from={TODAY}&date_to={TODAY}",
            headers=auth_headers,
        )
        assert summary.status_code == 200
        data = summary.json()
        assert data["total"]["calls"] == 4
        assert data["total"]["tokens_in"] == 2000
        assert data["total"]["tokens_out"] == 800

    async def test_upsert_distinct_models_separate_rows(
        self, client: AsyncClient, mcp_write_headers: dict, auth_headers: dict
    ):
        """Meme tool, modeles differents -> lignes distinctes, tokens non fusionnes."""
        events = [
            _event(model="claude-haiku-4-5", input_tokens=1000),
            _event(model="claude-opus-4", input_tokens=1000),
        ]
        resp = await client.post(
            "/api/v1/mcp-usage/ingest",
            json={"events": events},
            headers=mcp_write_headers,
        )
        assert resp.status_code == 200

        by_tool = await client.get(
            f"/api/v1/mcp-usage/by-tool?tool=unipile_get_messages"
            f"&date_from={TODAY}&date_to={TODAY}",
            headers=auth_headers,
        )
        assert by_tool.status_code == 200
        rows = by_tool.json()["rows"]
        models = {r["model"] for r in rows}
        assert models == {"claude-haiku-4-5", "claude-opus-4"}


# ---------------------------------------------------------------------------
# Summary — auth + agregation + cout
# ---------------------------------------------------------------------------

class TestSummary:
    async def test_summary_requires_admin(
        self, client: AsyncClient, sales_headers: dict
    ):
        """Un sales (non admin) -> 403."""
        resp = await client.get(
            "/api/v1/mcp-usage/summary", headers=sales_headers
        )
        assert resp.status_code == 403

    async def test_summary_requires_auth(self, client: AsyncClient):
        # Endpoint JWT : HTTPBearer(auto_error=True) leve 403 sans header
        # (comportement cohérent avec tout le projet, cf. GEO /brands).
        resp = await client.get("/api/v1/mcp-usage/summary")
        assert resp.status_code == 403

    async def test_summary_empty_ok(self, client: AsyncClient, auth_headers: dict):
        """Aucune donnee -> total a zero, by_tool vide."""
        resp = await client.get("/api/v1/mcp-usage/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"]["calls"] == 0
        assert data["total"]["cost_eur"] == 0.0
        assert data["by_tool"] == []

    async def test_summary_aggregates_by_tool(
        self, client: AsyncClient, mcp_write_headers: dict, auth_headers: dict
    ):
        """Agregation par tool + cout correct sur multi-modeles."""
        events = [
            # tool A : 1M input Haiku (=1$) + 1M output Haiku (=5$) = 6$
            _event(
                tool_name="tool_a",
                model="claude-haiku-4-5",
                calls=1,
                input_tokens=1_000_000,
                output_tokens=1_000_000,
            ),
            # tool B : 1M input Opus (=5$) = 5$
            _event(
                tool_name="tool_b",
                model="claude-opus-4",
                calls=1,
                input_tokens=1_000_000,
                output_tokens=0,
            ),
        ]
        await client.post(
            "/api/v1/mcp-usage/ingest",
            json={"events": events},
            headers=mcp_write_headers,
        )
        resp = await client.get(
            f"/api/v1/mcp-usage/summary?date_from={TODAY}&date_to={TODAY}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        by_tool = {t["tool_name"]: t for t in data["by_tool"]}
        assert set(by_tool) == {"tool_a", "tool_b"}
        assert by_tool["tool_a"]["cost_eur"] == pytest.approx((1.0 + 5.0) * EUR, rel=1e-6)
        assert by_tool["tool_b"]["cost_eur"] == pytest.approx(5.0 * EUR, rel=1e-6)

        # Total = somme des deux
        assert data["total"]["cost_eur"] == pytest.approx((6.0 + 5.0) * EUR, rel=1e-6)
        assert data["total"]["calls"] == 2
        assert data["total"]["tokens_in"] == 2_000_000

        # by_tool trie par cout decroissant : tool_a (6$) avant tool_b (5$)
        assert data["by_tool"][0]["tool_name"] == "tool_a"

    async def test_summary_cost_sums_models_within_tool(
        self, client: AsyncClient, mcp_write_headers: dict, auth_headers: dict
    ):
        """Un tool avec 2 modeles : le cout du tool = somme des couts par modele."""
        events = [
            _event(
                tool_name="multi",
                model="claude-haiku-4-5",
                input_tokens=1_000_000,
                output_tokens=0,
            ),  # 1$
            _event(
                tool_name="multi",
                model="claude-sonnet-4",
                input_tokens=1_000_000,
                output_tokens=0,
            ),  # 3$
        ]
        await client.post(
            "/api/v1/mcp-usage/ingest",
            json={"events": events},
            headers=mcp_write_headers,
        )
        resp = await client.get(
            f"/api/v1/mcp-usage/summary?date_from={TODAY}&date_to={TODAY}",
            headers=auth_headers,
        )
        data = resp.json()
        tool = next(t for t in data["by_tool"] if t["tool_name"] == "multi")
        assert tool["cost_eur"] == pytest.approx((1.0 + 3.0) * EUR, rel=1e-6)
        assert tool["input_tokens"] == 2_000_000


# ---------------------------------------------------------------------------
# Summary — bornes dates (DC1 / DC11)
# ---------------------------------------------------------------------------

class TestSummaryDateBounds:
    async def test_date_from_after_date_to_422(
        self, client: AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/mcp-usage/summary?date_from=2026-06-30&date_to=2026-06-01",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_window_too_large_422(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Fenetre > 366 jours rejetee."""
        resp = await client.get(
            "/api/v1/mcp-usage/summary?date_from=2024-01-01&date_to=2026-06-30",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_bad_date_format_422(
        self, client: AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/mcp-usage/summary?date_from=not-a-date",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_default_window_ok(self, client: AsyncClient, auth_headers: dict):
        """Sans dates -> fenetre par defaut acceptee (200)."""
        resp = await client.get("/api/v1/mcp-usage/summary", headers=auth_headers)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# By-tool
# ---------------------------------------------------------------------------

class TestByTool:
    async def test_by_tool_requires_admin(
        self, client: AsyncClient, sales_headers: dict
    ):
        resp = await client.get(
            "/api/v1/mcp-usage/by-tool?tool=x", headers=sales_headers
        )
        assert resp.status_code == 403

    async def test_by_tool_requires_tool_param(
        self, client: AsyncClient, auth_headers: dict
    ):
        """tool obligatoire -> 422 sans."""
        resp = await client.get("/api/v1/mcp-usage/by-tool", headers=auth_headers)
        assert resp.status_code == 422

    async def test_by_tool_rows_per_day_model(
        self, client: AsyncClient, mcp_write_headers: dict, auth_headers: dict
    ):
        """Detail : une ligne par (jour, modele) avec cout."""
        yesterday = (date(2026, 6, 30) - timedelta(days=1)).isoformat()
        events = [
            _event(tool_name="detail", day=TODAY, model="claude-haiku-4-5",
                   input_tokens=1_000_000, output_tokens=0),
            _event(tool_name="detail", day=yesterday, model="claude-haiku-4-5",
                   input_tokens=1_000_000, output_tokens=0),
        ]
        await client.post(
            "/api/v1/mcp-usage/ingest",
            json={"events": events},
            headers=mcp_write_headers,
        )
        resp = await client.get(
            f"/api/v1/mcp-usage/by-tool?tool=detail"
            f"&date_from={yesterday}&date_to={TODAY}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tool_name"] == "detail"
        assert len(data["rows"]) == 2
        for row in data["rows"]:
            assert row["cost_eur"] == pytest.approx(1.0 * EUR, rel=1e-6)
        # Tri par jour croissant
        assert data["rows"][0]["day"] == yesterday
        assert data["rows"][1]["day"] == TODAY

    async def test_by_tool_unknown_tool_empty(
        self, client: AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/mcp-usage/by-tool?tool=inexistant", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["rows"] == []
