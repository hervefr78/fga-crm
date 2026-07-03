"""Tests des filtres RGPD (classification des emails pro/perso/generique)."""

from __future__ import annotations

import pytest

from app.services.enrichment.rgpd import (
    classify_email,
    is_generic_local,
    is_personal_domain,
)


@pytest.mark.parametrize("email,expected", [
    # personnel (bloquant RGPD)
    ("jean@gmail.com", "personal"),
    ("marie@yahoo.fr", "personal"),
    ("paul@hotmail.com", "personal"),
    ("luc@outlook.fr", "personal"),
    ("x@free.fr", "personal"),
    ("y@orange.fr", "personal"),
    ("z@icloud.com", "personal"),
    # generique (non nominatif)
    ("contact@acme.com", "generic"),
    ("info@editeur.fr", "generic"),
    ("sales@acme.io", "generic"),
    ("dpo@acme.com", "generic"),
    # pro nominatif (cible)
    ("jean.dupont@acme.com", "pro"),
    ("j.martin@editeur.fr", "pro"),
])
def test_classify_email(email: str, expected: str):
    assert classify_email(email) == expected


def test_is_personal_domain():
    assert is_personal_domain("gmail.com") is True
    assert is_personal_domain("yahoo.co.uk") is True   # base yahoo, TLD variable
    assert is_personal_domain("acme.com") is False


def test_is_generic_local():
    assert is_generic_local("contact") is True
    assert is_generic_local("CONTACT") is True
    assert is_generic_local("jean.dupont") is False


def test_invalid_emails_are_personal():
    assert classify_email("") == "personal"
    assert classify_email("notanemail") == "personal"
    assert classify_email("a@b@c.com") == "personal"
    assert classify_email("nolocal@") == "personal"
