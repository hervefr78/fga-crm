# =============================================================================
# FGA CRM - Enrichissement : filtres RGPD (classification des emails)
# =============================================================================
"""Filtres RGPD bloquants (spec §10.2) : on ne garde que des emails PRO NOMINATIFS.

- domaine personnel (gmail, yahoo...) -> rejet (jamais d'opt-out sur du perso)
- local-part generique (contact@, info@...) -> non nominatif -> hors cible decideur
- sinon -> pro nominatif (acceptable)
"""

from __future__ import annotations

# Domaines personnels exacts (extensible via config plus tard).
_PERSONAL_EXACT: frozenset[str] = frozenset({
    "gmail.com", "googlemail.com", "icloud.com", "me.com", "mac.com",
    "free.fr", "orange.fr", "wanadoo.fr", "sfr.fr", "neuf.fr", "laposte.net",
    "bbox.fr", "numericable.fr", "aol.com", "protonmail.com", "proton.me",
    "yandex.com", "zoho.com",
})

# Bases (2ᵉ niveau) matchant n'importe quel TLD : yahoo.fr, hotmail.com, gmx.net...
_PERSONAL_BASES: frozenset[str] = frozenset({
    "yahoo", "hotmail", "outlook", "live", "msn", "gmx",
})

# Local-parts generiques (non nominatifs).
_GENERIC_LOCALS: frozenset[str] = frozenset({
    "contact", "info", "hello", "bonjour", "sales", "commercial", "support",
    "admin", "rgpd", "dpo", "team", "help", "noreply", "no-reply", "nepasrepondre",
    "service", "accueil", "compta", "facturation",
})


def _split_email(email: str) -> tuple[str, str]:
    """Retourne (local, domain) en minuscules. ('', '') si invalide."""
    e = (email or "").strip().lower()
    if e.count("@") != 1:
        return "", ""
    local, domain = e.split("@", 1)
    if not local or "." not in domain:
        return "", ""
    return local, domain


def _domain_base(domain: str) -> str:
    """Label racine (1er) : 'yahoo' pour 'yahoo.fr' ET 'yahoo.co.uk' (TLD composes).
    Les domaines d'email de fournisseurs perso sont a la racine (rarement sous-domaines)."""
    parts = domain.split(".")
    return parts[0] if len(parts) >= 2 else domain


def is_personal_domain(domain: str) -> bool:
    d = (domain or "").strip().lower()
    if not d:
        return False
    return d in _PERSONAL_EXACT or _domain_base(d) in _PERSONAL_BASES


def is_generic_local(local: str) -> bool:
    return (local or "").strip().lower() in _GENERIC_LOCALS


def classify_email(email: str) -> str:
    """Retourne le domain_type : 'personal' | 'generic' | 'pro'.

    Ordre : personnel d'abord (bloquant RGPD), puis generique, sinon pro.
    Un email invalide est classe 'personal' (rejete par prudence).
    """
    local, domain = _split_email(email)
    if not local or not domain:
        return "personal"
    if is_personal_domain(domain):
        return "personal"
    if is_generic_local(local):
        return "generic"
    return "pro"
