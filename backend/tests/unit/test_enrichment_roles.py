"""Tests de normalize_title (mapping intitule -> role, FR/EN, faux-amis)."""

from __future__ import annotations

import pytest

from app.services.enrichment.roles import normalize_title


@pytest.mark.parametrize("title,expected", [
    # CTO
    ("CTO", "CTO"),
    ("Chief Technology Officer", "CTO"),
    ("Directeur Technique", "CTO"),
    ("Directrice technique", "CTO"),
    ("VP Engineering", "CTO"),
    ("Head of Engineering", "CTO"),
    ("Directeur R&D", "CTO"),
    # CPO
    ("CPO", "CPO"),
    ("Chief Product Officer", "CPO"),
    ("Directeur Produit", "CPO"),
    ("Head of Product", "CPO"),
    ("Product Lead", "CPO"),
    # CMO
    ("CMO", "CMO"),
    ("Chief Marketing Officer", "CMO"),
    ("Directrice Marketing", "CMO"),
    ("Growth Lead", "CMO"),
    # FOUNDER
    ("Founder", "FOUNDER"),
    ("Co-founder", "FOUNDER"),
    ("Fondateur", "FOUNDER"),
    ("Cofondateur", "FOUNDER"),
    ("CEO", "FOUNDER"),
    ("Président", "FOUNDER"),
    ("Dirigeant", "FOUNDER"),
    # OTHER (dont faux-amis)
    ("DSI", "OTHER"),
    ("Directeur Commercial", "OTHER"),
    ("Product Owner", "OTHER"),
    ("Sales Manager", "OTHER"),
    ("Développeur Full Stack", "OTHER"),
    ("", "OTHER"),
])
def test_normalize_title(title: str, expected: str):
    assert normalize_title(title) == expected


def test_accents_and_case_insensitive():
    assert normalize_title("DIRECTEUR TECHNIQUE") == "CTO"
    assert normalize_title("prÉsident") == "FOUNDER"


def test_none_safe():
    assert normalize_title(None) == "OTHER"  # type: ignore[arg-type]
