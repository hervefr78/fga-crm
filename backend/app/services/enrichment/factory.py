# =============================================================================
# FGA CRM - Enrichissement : factory des providers (mock-first)
# =============================================================================
"""Selection des adapters. P2 : tout en MOCK (buildable/testable sans cle).
P6 : brancher les adapters reels (Icypeas si `icypeas_api_key`, CRM interne,
Startup Radar, Plein Phare) en respectant l'ordre cout-croissant."""

from __future__ import annotations

from app.services.enrichment.adapters.mock import (
    MockCompanySource,
    MockEmailFinder,
    MockEmailVerifier,
    MockPeopleSource,
)
from app.services.enrichment.ports import (
    CompanySource,
    EmailFinder,
    EmailVerifier,
    PeopleSource,
)


def get_company_source() -> CompanySource:
    # P6 : PleinPhareCompanySource (frdata) si dispo.
    return MockCompanySource()


def get_people_sources() -> list[PeopleSource]:
    # Ordre cout-croissant. P6 : CrmPeopleSource(0) -> StartupRadar(0) -> Icypeas(0.02).
    return [MockPeopleSource()]


def get_email_finders() -> list[EmailFinder]:
    # P6 : IcypeasEmailFinder (+ fallback Dropcontact…).
    return [MockEmailFinder()]


def get_email_verifiers() -> list[EmailVerifier]:
    # P6 : IcypeasVerifier -> MillionVerifier (2e passe).
    return [MockEmailVerifier()]
