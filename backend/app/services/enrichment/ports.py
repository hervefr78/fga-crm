# =============================================================================
# FGA CRM - Enrichissement : ports (interfaces) + value objects
# =============================================================================
"""Contrats hexagonaux : chaque fournisseur externe est derriere une interface.
On ajoute un fournisseur de secours sans reecrire l'orchestrateur (cf. spec §7)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass
class IcpFilter:
    naf_codes: list[str] = field(default_factory=list)
    only_active: bool = True
    min_revenue_eur: int | None = None
    require_domain: bool = True
    limit: int | None = None


@dataclass
class TargetSpec:
    kind: str  # 'company' | 'batch' | 'icp' | 'contacts'
    siren: str | None = None
    sirens: list[str] = field(default_factory=list)
    icp_filter: IcpFilter | None = None
    # Mode 'contacts' (Feature B — enrichir des contacts existants).
    contact_ids: list[str] = field(default_factory=list)
    all_missing_email: bool = False  # tous les contacts de l'org sans email
    reverify: bool = False           # re-verifier aussi les emails deja presents


@dataclass
class Company:
    siren: str
    name: str
    naf: str = ""
    domain: str | None = None
    active: bool = True
    size_band: str | None = None
    revenue_band: str | None = None


@dataclass
class PersonCandidate:
    first_name: str
    last_name: str
    title_raw: str
    source: str
    linkedin_url: str | None = None
    role: str | None = None  # rempli par normalize_title
    email: str | None = None  # email deja connu (CRM/Radar) -> passe direct en verif


@dataclass
class EmailCandidate:
    email: str
    confidence: float
    status: str  # valid | catch_all | risky | invalid
    source: str


@dataclass
class VerificationResult:
    email: str
    status: str
    confidence: float
    source: str


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------

class CompanySource(ABC):
    @abstractmethod
    async def get_companies(self, icp: IcpFilter) -> list[Company]: ...

    @abstractmethod
    async def get_by_siren(self, siren: str) -> Company | None: ...

    @abstractmethod
    async def resolve_domain(self, company: Company) -> str | None: ...


class PeopleSource(ABC):
    name: str = ""
    cost_per_result: float = 0.0  # en credits (0 pour interne)

    @abstractmethod
    async def find_people(self, company: Company, roles: list[str]) -> list[PersonCandidate]: ...


class EmailFinder(ABC):
    name: str = ""
    cost_per_hit: float = 0.0  # facture au resultat trouve

    @abstractmethod
    async def find(self, person: PersonCandidate, domain: str) -> EmailCandidate | None: ...


class EmailVerifier(ABC):
    name: str = ""
    cost_per_check: float = 0.0

    @abstractmethod
    async def verify(self, email: str) -> VerificationResult: ...
