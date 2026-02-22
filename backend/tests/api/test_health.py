# =============================================================================
# FGA CRM - Test API Health Check
# =============================================================================

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Le endpoint /health doit repondre 200 avec le statut."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data
    assert "version" in data
