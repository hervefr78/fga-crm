# =============================================================================
# FGA CRM - Enrichissement : adapters MOCK deterministes (build-first, sans cle)
# =============================================================================
"""Implementations de secours pour dev/demo/tests : donnees DETERMINISTES (hash),
aucun appel reseau. Permettent de faire tourner tout le pipeline sans Icypeas ni
frdata/Radar (cf. approche mock-first de Trends)."""

from __future__ import annotations

import hashlib

from app.services.enrichment.ports import (
    Company,
    CompanySource,
    EmailCandidate,
    EmailFinder,
    EmailVerifier,
    IcpFilter,
    PeopleSource,
    PersonCandidate,
    VerificationResult,
)

_MOCK_SOURCE = "mock"

# Noms deterministes pour habiller les personnes.
_FIRST_NAMES = ["Julie", "Marc", "Sophie", "Thomas", "Claire", "Antoine", "Ines", "Paul"]
_LAST_NAMES = ["Martin", "Bernard", "Dubois", "Robert", "Petit", "Durand", "Leroy", "Moreau"]

# Intitule brut par role (pour tester normalize_title en aval).
_ROLE_TITLES = {
    "CTO": "Directeur Technique",
    "CPO": "Chief Product Officer",
    "CMO": "Directrice Marketing",
    "FOUNDER": "Co-founder & CEO",
    "OTHER": "Manager",
}


def _h(*parts: str) -> int:
    return int.from_bytes(hashlib.sha256("|".join(parts).encode()).digest()[:4], "big")


class MockCompanySource(CompanySource):
    async def get_companies(self, icp: IcpFilter) -> list[Company]:
        n = icp.limit or 5
        naf = icp.naf_codes[0] if icp.naf_codes else "5829C"
        out: list[Company] = []
        for i in range(n):
            siren = str(100000000 + i)
            out.append(Company(
                siren=siren, name=f"Editeur Mock {i + 1}",
                domain=f"editeur-mock-{i + 1}.fr", naf=naf, active=True,
            ))
        return out

    async def get_by_siren(self, siren: str) -> Company | None:
        idx = _h("company", siren) % 8
        return Company(
            siren=siren, name=f"Societe {siren[-4:]}",
            domain=f"societe-{siren[-4:]}.fr", naf="5829C", active=True,
            size_band=["1-10", "10-50", "50-200"][idx % 3],
        )

    async def resolve_domain(self, company: Company) -> str | None:
        if company.domain:
            return company.domain
        base = company.name.lower().replace(" ", "-")
        return f"{base}.fr"


class MockPeopleSource(PeopleSource):
    name = _MOCK_SOURCE
    cost_per_result = 0.02

    async def find_people(self, company: Company, roles: list[str]) -> list[PersonCandidate]:
        out: list[PersonCandidate] = []
        for role in roles:
            seed = _h("person", company.siren, role)
            first = _FIRST_NAMES[seed % len(_FIRST_NAMES)]
            last = _LAST_NAMES[(seed // 7) % len(_LAST_NAMES)]
            out.append(PersonCandidate(
                first_name=first, last_name=last,
                title_raw=_ROLE_TITLES.get(role, "Manager"),
                source=_MOCK_SOURCE,
                linkedin_url=f"https://linkedin.com/in/{first.lower()}-{last.lower()}",
            ))
        return out


class MockEmailFinder(EmailFinder):
    name = _MOCK_SOURCE
    cost_per_hit = 1.0

    async def find(self, person: PersonCandidate, domain: str) -> EmailCandidate | None:
        seed = _h("email", person.first_name, person.last_name, domain)
        # 1 personne sur 8 sans email trouve (realiste)
        if seed % 8 == 0:
            return None
        email = f"{person.first_name.lower()}.{person.last_name.lower()}@{domain}"
        confidence = round(0.6 + (seed % 40) / 100, 2)  # 0.60..0.99
        return EmailCandidate(
            email=email, confidence=confidence, status="valid", source=_MOCK_SOURCE,
        )


class MockEmailVerifier(EmailVerifier):
    name = _MOCK_SOURCE
    cost_per_check = 0.1

    async def verify(self, email: str) -> VerificationResult:
        seed = _h("verify", email)
        status = ["valid", "valid", "valid", "catch_all", "risky", "invalid"][seed % 6]
        confidence = round(0.5 + (seed % 50) / 100, 2)
        return VerificationResult(
            email=email, status=status, confidence=confidence, source=_MOCK_SOURCE,
        )
