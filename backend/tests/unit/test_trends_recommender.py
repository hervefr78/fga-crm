"""Tests du recommender Trends (OpenAI mocke). Best-effort : jamais de levee."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.config import settings
from app.services.trends import recommender

SIGNALS = {
    "market_pulse": {"interest_index": 62.5, "direction": "up"},
    "rising_queries": [{"query": "prospection ia", "growth": 320, "breakout": True}],
    "top_queries": [{"query": "crm"}],
    "related_topics": [{"topic": "sales automation"}],
}

VALID_JSON = (
    '{"strategy":"Accelerer","target_keywords":['
    '{"keyword":"prospection ia","cluster":"IA","rationale":"forte croissance"}],'
    '"watch_queries":[{"query":"agent ia sdr","reason":"emergent"}],'
    '"content_angles":["Guide IA de prospection"]}'
)


def _fake_openai(*, content: str | None = None, exc: Exception | None = None):
    """Fabrique une classe AsyncOpenAI factice (chat.completions.create)."""

    async def _create(**_kwargs):
        if exc is not None:
            raise exc
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    class _Client:
        def __init__(self, *a, **k):
            self.chat = SimpleNamespace(completions=SimpleNamespace(create=_create))

    return _Client


async def test_recommender_disabled_without_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_api_key", None)
    out = await recommender.generate_recommendations(
        category_label="Prospection", signals=SIGNALS, score=70, objective="seo",
    )
    assert out is None


async def test_recommender_maps_output(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr("openai.AsyncOpenAI", _fake_openai(content=VALID_JSON))
    out = await recommender.generate_recommendations(
        category_label="Prospection", signals=SIGNALS, score=70, objective="seo",
    )
    assert out is not None
    assert out.objective == "seo"                       # objectif ajoute cote serveur
    assert out.strategy == "Accelerer"
    assert out.target_keywords[0].keyword == "prospection ia"
    assert out.watch_queries[0].query == "agent ia sdr"
    assert out.content_angles == ["Guide IA de prospection"]


async def test_recommender_fallback_on_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr("openai.AsyncOpenAI", _fake_openai(exc=RuntimeError("boom")))
    out = await recommender.generate_recommendations(
        category_label="X", signals=SIGNALS, score=50, objective=None,
    )
    assert out is None  # erreur LLM -> None, jamais de levee


async def test_recommender_truncates_outputs(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    kws = ",".join(
        f'{{"keyword":"k{i}","cluster":"c","rationale":"r"}}' for i in range(20)
    )
    content = (
        '{"strategy":"s","target_keywords":[' + kws + '],'
        '"watch_queries":[],"content_angles":[]}'
    )
    monkeypatch.setattr("openai.AsyncOpenAI", _fake_openai(content=content))
    out = await recommender.generate_recommendations(
        category_label="X", signals=SIGNALS, score=50, objective="ads",
    )
    assert out is not None
    assert len(out.target_keywords) == 8  # borne DC1 (_MAX_TARGET_KEYWORDS)
