# =============================================================================
# FGA CRM - Enrichissement : adapters Icypeas (moteur reel email finder/verifier)
# =============================================================================
"""Adapters Icypeas (spec §7). API async : on soumet une recherche (-> _id) puis
on POLL le resultat jusqu'a un statut terminal. Contrat capture en live :
docs/compass/icypeas-api-reference.md.

Auth : header `Authorization: <cle>` (brute, pas de Bearer). Base app.icypeas.com/api.
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.services.enrichment.ports import (
    Company,
    EmailCandidate,
    EmailFinder,
    EmailVerifier,
    PeopleSource,
    PersonCandidate,
    VerificationResult,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://app.icypeas.com/api"
_HTTP_TIMEOUT_S = 15.0
_POLL_INTERVAL_S = 2.0
_MAX_WAIT_S = 30.0

# Statuts d'item : on continue a poller tant qu'on n'est pas terminal.
_TERMINAL_STATUSES = frozenset({
    "DEBITED", "FOUND", "NOT_FOUND", "DEBITED_NOT_FOUND",
    "BAD_INPUT", "INSUFFICIENT_FUNDS", "ABORTED",
})

# certainty Icypeas -> (status interne, confidence). Defaut prudent = risky.
_CERTAINTY_MAP: dict[str, tuple[str, float]] = {
    "ultra_sure": ("valid", 0.99),
    "very_sure": ("valid", 0.97),
    "probable": ("valid", 0.90),
    "undeliverable": ("invalid", 0.0),
    "not_found": ("invalid", 0.0),
}


def _map_certainty(certainty: str | None) -> tuple[str, float]:
    return _CERTAINTY_MAP.get(certainty or "", ("risky", 0.5))


class IcypeasClient:
    """Client bas niveau : soumission + polling du resultat. Fail-safe (None sur erreur)."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = _BASE_URL,
        timeout_s: float = _HTTP_TIMEOUT_S,
        poll_interval_s: float = _POLL_INTERVAL_S,
        max_wait_s: float = _MAX_WAIT_S,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._poll_interval = poll_interval_s
        self._max_wait = max_wait_s
        self._transport = transport  # injecte en test (httpx.MockTransport)

    def _headers(self) -> dict[str, str]:
        # Icypeas attend la cle brute dans Authorization (pas de prefixe Bearer).
        return {"Authorization": self._api_key, "Content-Type": "application/json"}

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    async def _submit(self, path: str, payload: dict) -> str | None:
        """Soumet une recherche, retourne l'_id de la tache (ou None sur echec)."""
        try:
            async with self._client() as client:
                resp = await client.post(f"{self._base}/{path}", headers=self._headers(), json=payload)
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:  # ValueError = JSON invalide
            logger.warning("[Icypeas] soumission %s KO : %s", path, exc)
            return None
        if not data.get("success"):
            logger.warning("[Icypeas] soumission %s refusee : %s", path, data.get("validationErrors"))
            return None
        return (data.get("item") or {}).get("_id")

    async def _await_result(self, search_id: str) -> dict | None:
        """Poll le resultat jusqu'a statut terminal ou timeout. Retourne items[0]."""
        waited = 0.0
        try:
            async with self._client() as client:
                while True:
                    resp = await client.post(
                        f"{self._base}/bulk-single-searchs/read",
                        headers=self._headers(),
                        json={"id": search_id},
                    )
                    resp.raise_for_status()
                    items = (resp.json().get("items")) or []
                    item = items[0] if items else None
                    if item and item.get("status") in _TERMINAL_STATUSES:
                        return item
                    if waited >= self._max_wait:
                        logger.warning("[Icypeas] timeout polling %s (status=%s)",
                                       search_id, item.get("status") if item else None)
                        return item
                    await asyncio.sleep(self._poll_interval)
                    waited += self._poll_interval
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[Icypeas] lecture resultat %s KO : %s", search_id, exc)
            return None

    async def find_email(self, firstname: str, lastname: str, domain: str) -> dict | None:
        sid = await self._submit(
            "email-search",
            {"firstname": firstname, "lastname": lastname, "domainOrCompany": domain},
        )
        return await self._await_result(sid) if sid else None

    async def verify_email(self, email: str) -> dict | None:
        sid = await self._submit("email-verification", {"email": email})
        return await self._await_result(sid) if sid else None

    async def find_people(
        self,
        *,
        domain: str | None = None,
        company_name: str | None = None,
        job_titles: list[str] | None = None,
        size: int = 25,
    ) -> list[dict]:
        """Leads DB (SYNCHRONE) : retourne les profils matchant societe + titres."""
        query: dict = {}
        if domain:
            query["currentCompanyWebsite"] = {"include": [domain]}
        elif company_name:
            query["currentCompanyName"] = {"include": [company_name]}
        if job_titles:
            query["currentJobTitle"] = {"include": list(job_titles)}
        if not query:
            return []
        try:
            async with self._client() as client:
                resp = await client.post(
                    f"{self._base}/find-people",
                    headers=self._headers(),
                    json={"query": query, "pagination": {"size": size}},
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("[Icypeas] find-people KO : %s", exc)
            return []
        if not data.get("success"):
            logger.warning("[Icypeas] find-people refuse : %s", data.get("validationErrors"))
            return []
        return data.get("leads") or []


def _first_email(item: dict | None) -> dict | None:
    """Extrait la premiere entree emails[] du resultat Icypeas (ou None)."""
    if not item:
        return None
    emails = ((item.get("results") or {}).get("emails")) or []
    return emails[0] if emails else None


class IcypeasPeopleSource(PeopleSource):
    name = "icypeas"
    cost_per_result = 1.0  # 1 credit leads DB par profil retourne

    _SIZE = 25

    def __init__(self, client: IcypeasClient) -> None:
        self._client = client

    async def find_people(self, company: Company, roles: list[str]) -> list[PersonCandidate]:
        # Domaine prioritaire (plus precis), sinon nom de societe.
        leads = await self._client.find_people(
            domain=company.domain,
            company_name=None if company.domain else company.name,
            job_titles=roles,
            size=self._SIZE,
        )
        out: list[PersonCandidate] = []
        for lead in leads:
            fn = (lead.get("firstname") or "").strip()
            ln = (lead.get("lastname") or "").strip()
            if not fn or not ln:
                continue
            out.append(PersonCandidate(
                first_name=fn,
                last_name=ln,
                title_raw=lead.get("lastJobTitle") or "",
                source="icypeas",
                linkedin_url=lead.get("profileUrl") or None,
            ))
        return out


class IcypeasEmailFinder(EmailFinder):
    name = "icypeas"
    cost_per_hit = 1.0  # 1 credit debite par email trouve

    def __init__(self, client: IcypeasClient) -> None:
        self._client = client

    async def find(self, person: PersonCandidate, domain: str) -> EmailCandidate | None:
        item = await self._client.find_email(person.first_name, person.last_name, domain)
        entry = _first_email(item)
        if entry is None or not entry.get("email"):
            return None
        status, confidence = _map_certainty(entry.get("certainty"))
        return EmailCandidate(
            email=entry["email"], confidence=confidence, status=status, source="icypeas",
        )


class IcypeasEmailVerifier(EmailVerifier):
    name = "icypeas"
    cost_per_check = 1.0

    def __init__(self, client: IcypeasClient) -> None:
        self._client = client

    async def verify(self, email: str) -> VerificationResult:
        item = await self._client.verify_email(email)
        entry = _first_email(item)
        if entry is None:
            # Pas de resultat exploitable -> non deliverable (deny by default).
            return VerificationResult(email=email, status="invalid", confidence=0.0, source="icypeas")
        status, confidence = _map_certainty(entry.get("certainty"))
        return VerificationResult(email=email, status=status, confidence=confidence, source="icypeas")
