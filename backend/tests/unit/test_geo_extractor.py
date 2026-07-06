"""Tests de l'adaptation du schema d'extraction GEO au mode strict OpenAI.

Regression : OpenAI structured outputs (strict) rejette un schema Pydantic brut
avec 400 "additionalProperties is required to be false" + refuse minimum/maxLength.
"""

from __future__ import annotations

import json

from app.schemas.geo import ExtractionResult
from app.services.openai_strict import build_response_format, to_openai_strict


def _build_response_format() -> dict:
    """Helper de test : response_format strict pour le schema d'extraction GEO."""
    return build_response_format(ExtractionResult, name="extraction")


def _iter_objects(node):
    """Parcourt recursivement tous les noeuds objet (type == 'object')."""
    if isinstance(node, dict):
        if node.get("type") == "object" and "properties" in node:
            yield node
        for v in node.values():
            yield from _iter_objects(v)
    elif isinstance(node, list):
        for it in node:
            yield from _iter_objects(it)


def test_response_format_is_strict():
    rf = _build_response_format()
    assert rf["json_schema"]["strict"] is True
    schema = rf["json_schema"]["schema"]

    objects = list(_iter_objects(schema))
    assert len(objects) >= 2  # ExtractionResult + MarqueTrouvee
    for obj in objects:
        # additionalProperties:false obligatoire (cause du 400)
        assert obj.get("additionalProperties") is False
        # required doit lister TOUTES les proprietes (mode strict)
        assert set(obj["required"]) == set(obj["properties"].keys())


def test_unsupported_keywords_stripped():
    rf = _build_response_format()
    dumped = json.dumps(rf)
    # ge=1 -> minimum ; max_length=500 -> maxLength : non supportes en strict
    for kw in ("minimum", "maximum", "maxLength", "minLength", "pattern", "multipleOf"):
        assert f'"{kw}"' not in dumped


def test_to_openai_strict_is_recursive():
    node = {
        "type": "object",
        "properties": {
            "a": {"type": "string", "maxLength": 10},
            "b": {"type": "object", "properties": {"c": {"type": "integer", "minimum": 1}}},
        },
    }
    to_openai_strict(node)
    assert node["additionalProperties"] is False
    assert node["required"] == ["a", "b"]
    assert "maxLength" not in node["properties"]["a"]
    # objet imbrique traite aussi
    inner = node["properties"]["b"]
    assert inner["additionalProperties"] is False
    assert inner["required"] == ["c"]
    assert "minimum" not in inner["properties"]["c"]
