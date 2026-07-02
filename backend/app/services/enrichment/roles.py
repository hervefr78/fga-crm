# =============================================================================
# FGA CRM - Enrichissement : normalisation des titres -> role
# =============================================================================
"""Mappe un intitule de poste (FR/EN, casse/accents insensibles) vers un role
cible {CTO, CPO, CMO, FOUNDER, OTHER}. Regles ordonnees : premiere correspondance
gagne. Cf. spec §9.1.
"""

from __future__ import annotations

import re
import unicodedata

# Regles ordonnees (role, patterns regex). Premiere correspondance gagne.
_ROLE_RULES: list[tuple[str, list[str]]] = [
    ("CTO", [
        r"\bcto\b",
        r"chief\s+tech(nology)?\s+officer",
        r"directeur\s+technique|directrice\s+technique",
        r"vp\s+eng(ineering)?|head\s+of\s+eng(ineering)?",
        r"directeur\s+r&?d",
    ]),
    ("CPO", [
        r"\bcpo\b",
        r"chief\s+product\s+officer",
        r"directeur\s+produit|directrice\s+produit",
        r"head\s+of\s+product|vp\s+product|product\s+lead",
    ]),
    ("CMO", [
        r"\bcmo\b",
        r"chief\s+marketing\s+officer",
        r"directeur\s+marketing|directrice\s+marketing",
        r"head\s+of\s+marketing|vp\s+marketing|growth\s+lead",
    ]),
    ("FOUNDER", [
        r"\bfounde?r\b|co-?founder",
        r"fondateur|cofondateur|co-?fondateur",
        r"\bceo\b|president|dirigeant|gerant",
    ]),
]

# Faux-amis : si l'un matche, on force OTHER (evite DSI->CTO, Dir. commercial->CMO,
# Product Owner->CPO). Verifie AVANT les regles de role.
_EXCLUSIONS: list[str] = [
    r"\bdsi\b",
    r"directeur\s+des\s+systemes",
    r"directeur\s+commercial|directrice\s+commerciale",
    r"product\s+owner",
    r"account\s+manager|sales\s+manager",
]


def _normalize(text: str) -> str:
    """Minuscule + suppression des accents (NFD) pour un matching robuste."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def normalize_title(title_raw: str) -> str:
    """Retourne le role {CTO|CPO|CMO|FOUNDER|OTHER} pour un intitule brut."""
    t = _normalize(title_raw)
    if not t:
        return "OTHER"
    if any(re.search(p, t) for p in _EXCLUSIONS):
        return "OTHER"
    for role, patterns in _ROLE_RULES:
        if any(re.search(p, t) for p in patterns):
            return role
    return "OTHER"
