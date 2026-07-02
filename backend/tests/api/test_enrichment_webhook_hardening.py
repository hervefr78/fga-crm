"""Tests C4 (bug hunt) : durcissement de l'endpoint webhook public Icypeas —
borne de taille du corps (#8) et refus en prod si verification desactivee (#9)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import settings

WEBHOOK = "/api/v1/integrations/icypeas/webhook"


@pytest.mark.asyncio
async def test_webhook_rejects_oversized_body(client: AsyncClient):
    # #8 : corps > 2 Mo -> 413 (avant meme la verif HMAC)
    payload = {"data": {"blob": "A" * (2 * 1024 * 1024 + 1000)}}
    r = await client.post(WEBHOOK, json=payload)
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_webhook_refuses_unverified_in_production(client: AsyncClient, monkeypatch):
    # #9 : verify=False + prod -> 503 (endpoint deviendrait un injecteur de contacts)
    monkeypatch.setattr(settings, "icypeas_webhook_verify", False)
    monkeypatch.setattr(settings, "app_env", "production")
    r = await client.post(WEBHOOK, json={"data": {"file": "x", "results": []}})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_webhook_unverified_allowed_in_dev(client: AsyncClient, monkeypatch):
    # En dev, verify=False autorise le traitement (bulk inconnu -> matched False)
    monkeypatch.setattr(settings, "icypeas_webhook_verify", False)
    monkeypatch.setattr(settings, "app_env", "development")
    r = await client.post(WEBHOOK, json={"data": {"file": "nope", "results": []}})
    assert r.status_code == 200
    assert r.json()["received"] is True
