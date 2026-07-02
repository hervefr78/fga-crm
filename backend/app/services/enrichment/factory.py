# =============================================================================
# FGA CRM - Enrichissement : factory des providers (mock-first)
# =============================================================================
"""Selection des adapters. P2 : tout en MOCK (buildable/testable sans cle).
P6 : brancher les adapters reels (Icypeas si `icypeas_api_key`, CRM interne,
Startup Radar, Plein Phare) en respectant l'ordre cout-croissant."""

from __future__ import annotations

from app.config import settings
from app.services.enrichment.adapters.icypeas import (
    IcypeasClient,
    IcypeasEmailFinder,
    IcypeasEmailVerifier,
)
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


def _icypeas_client() -> IcypeasClient:
    return IcypeasClient(settings.icypeas_api_key)


def get_company_source() -> CompanySource:
    # P6 : PleinPhareCompanySource (frdata) si dispo. Reste mock (Icypeas ne fait
    # pas la resolution siren->societe FR).
    return MockCompanySource()


def get_people_sources() -> list[PeopleSource]:
    # Ordre cout-croissant. P6 : CrmPeopleSource(0) -> StartupRadar(0) -> Icypeas
    # find-people (leads DB, schema a capturer avant integration).
    return [MockPeopleSource()]


def get_email_finders() -> list[EmailFinder]:
    # Icypeas si cle configuree, fallback mock (build-first sans cle).
    if settings.icypeas_api_key:
        return [IcypeasEmailFinder(_icypeas_client())]
    return [MockEmailFinder()]


def get_email_verifiers() -> list[EmailVerifier]:
    if settings.icypeas_api_key:
        return [IcypeasEmailVerifier(_icypeas_client())]
    return [MockEmailVerifier()]
