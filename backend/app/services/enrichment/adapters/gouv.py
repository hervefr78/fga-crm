# =============================================================================
# FGA CRM - Enrichissement : CompanySource FR (API gouv recherche-entreprises)
# =============================================================================
"""Source societe FR via `recherche-entreprises.api.gouv.fr` (gratuite, sans cle).

- get_by_siren : siren -> Company (raison sociale, NAF, effectif, etat).
- get_companies : recherche ICP (NAF + geo + effectif) paginee (mode ICP v1).
- resolve_domain : heuristique nom->domaine best-effort (~40%). Icypeas acceptant
  `domainOrCompany`, le domaine est un BOOSTER optionnel (fallback = nom societe).

L'API gouv ne retourne PAS de site web -> le domaine est resolu separement."""

from __future__ import annotations

import asyncio
import logging
import re
import unicodedata

import httpx

from app.services.enrichment.ports import Company, CompanySource, IcpFilter

logger = logging.getLogger(__name__)

_BASE_URL = "https://recherche-entreprises.api.gouv.fr"
_HTTP_TIMEOUT_S = 15.0
_DOMAIN_TIMEOUT_S = 3.0          # court : la resolution est best-effort
_MAX_PER_PAGE = 25              # plafond de l'API gouv
_MAX_RETRIES = 3
_INITIAL_BACKOFF_S = 2.0
_PAGE_THROTTLE_S = 0.15         # ~7 req/s (limite douce de l'API)
_DEFAULT_ICP_LIMIT = 100
_DOMAIN_EXTENSIONS = (".fr", ".com")

# Formes juridiques a retirer avant de deriver un domaine.
_LEGAL_SUFFIXES = re.compile(
    r"\b(SAS|SARL|SA|EURL|SCI|SNC|SASU|SELARL|SCA|SE|SCOP|GIE|EI)\b", re.IGNORECASE
)

# Tranches d'effectif INSEE -> bande lisible (size_band).
_EFFECTIF_BANDS = {
    "00": "0", "01": "1-2", "02": "3-5", "03": "6-9", "11": "10-19", "12": "20-49",
    "21": "50-99", "22": "100-199", "31": "200-249", "32": "250-499", "41": "500-999",
    "42": "1000-1999", "51": "2000-4999", "52": "5000-9999", "53": "10000+",
}


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def _normalize_for_domain(raison_sociale: str) -> str:
    name = _LEGAL_SUFFIXES.sub("", raison_sociale or "").strip()
    name = _strip_accents(name).lower()
    name = re.sub(r"[^a-z0-9 ]", " ", name)  # garde alphanum + espaces
    return re.sub(r"\s+", " ", name).strip()


def _domain_candidates(raison_sociale: str) -> list[str]:
    """Candidats domaine par priorite (slug colle -> tirets -> premier mot)."""
    normalized = _normalize_for_domain(raison_sociale)
    if not normalized or len(normalized) < 2:
        return []
    out: list[str] = []
    slug = normalized.replace(" ", "")
    for ext in _DOMAIN_EXTENSIONS:
        out.append(f"{slug}{ext}")
    if " " in normalized:
        hyphen = normalized.replace(" ", "-")
        for ext in _DOMAIN_EXTENSIONS:
            out.append(f"{hyphen}{ext}")
    first = normalized.split()[0]
    if len(first) >= 3 and first != slug:
        for ext in _DOMAIN_EXTENSIONS:
            out.append(f"{first}{ext}")
    return out


def _band(code: str | None) -> str | None:
    return _EFFECTIF_BANDS.get((code or "").strip()) if code else None


def _map_result(r: dict) -> Company | None:
    siren = r.get("siren")
    name = r.get("nom_raison_sociale") or r.get("nom_complet")
    if not siren or not name:
        return None
    return Company(
        siren=str(siren),
        name=str(name),
        naf=r.get("activite_principale") or "",
        domain=None,  # resolu separement (l'API gouv n'a pas de site web)
        active=r.get("etat_administratif") == "A",
        size_band=_band(r.get("tranche_effectif_salarie")),
    )


def _latest_ca(finances: dict | None) -> int | None:
    """Chiffre d'affaires le plus recent (finances = {annee: {ca, resultat_net}})."""
    if not finances:
        return None
    try:
        latest = max(finances.keys())
        ca = (finances.get(latest) or {}).get("ca")
        return int(ca) if ca is not None else None
    except (ValueError, TypeError):
        return None


class GouvCompanySource(CompanySource):
    """Adapter reel FR (API gouv). Fail-safe : None/[] sur erreur reseau (DC2 loggue)."""

    def __init__(
        self,
        *,
        base_url: str = _BASE_URL,
        timeout_s: float = _HTTP_TIMEOUT_S,
        domain_timeout_s: float = _DOMAIN_TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s
        self._domain_timeout = domain_timeout_s
        self._transport = transport  # httpx.MockTransport en test

    def _client(self, timeout: float) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=timeout, transport=self._transport, follow_redirects=True)

    async def _search(self, params: dict) -> dict | None:
        """GET /search avec retry/backoff (429/5xx). None sur echec definitif."""
        backoff = _INITIAL_BACKOFF_S
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with self._client(self._timeout) as client:
                    resp = await client.get(f"{self._base}/search", params=params)
                if resp.status_code in (429, 500, 502, 503, 504) and attempt < _MAX_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)
                    continue
                logger.warning("[gouv] recherche KO (params=%s) : %s", params, exc)
                return None
        return None

    async def get_by_siren(self, siren: str) -> Company | None:
        if not siren or not siren.isdigit() or len(siren) != 9:
            return None
        data = await self._search({"q": siren, "page": 1, "per_page": 1})
        results = (data or {}).get("results") or []
        if not results:
            return None
        company = _map_result(results[0])
        # Garde-fou : le resultat doit correspondre au siren demande.
        return company if company and company.siren == siren else None

    async def get_companies(self, icp: IcpFilter) -> list[Company]:
        limit = icp.limit or _DEFAULT_ICP_LIMIT
        per_page = min(_MAX_PER_PAGE, limit)
        base_params: dict = {"per_page": per_page}
        if icp.naf_codes:
            base_params["activite_principale"] = ",".join(icp.naf_codes)
        if icp.only_active:
            base_params["etat_administratif"] = "A"

        out: list[Company] = []
        page = 1
        while len(out) < limit:
            data = await self._search({**base_params, "page": page})
            results = (data or {}).get("results") or []
            if not results:
                break
            for r in results:
                company = _map_result(r)
                if company is None:
                    continue
                if icp.min_revenue_eur is not None:
                    ca = _latest_ca(r.get("finances"))
                    if ca is None or ca < icp.min_revenue_eur:
                        continue
                out.append(company)
                if len(out) >= limit:
                    break
            total_pages = (data or {}).get("total_pages") or 1
            if page >= total_pages:
                break
            page += 1
            await asyncio.sleep(_PAGE_THROTTLE_S)  # respecte la limite douce (~7 req/s)
        return out

    async def _domain_responds(self, client: httpx.AsyncClient, domain: str) -> bool:
        # #11 : https et http testes en CONCURRENCE (un https qui pend ne bloque
        # plus le fallback http jusqu'au timeout).
        async def _try(scheme: str) -> bool:
            try:
                resp = await client.get(f"{scheme}://{domain}")
                return resp.status_code < 400
            except httpx.HTTPError:
                return False

        results = await asyncio.gather(_try("https"), _try("http"))
        return any(results)

    async def resolve_domain(self, company: Company) -> str | None:
        """Heuristique nom->domaine (best-effort). Retourne le 1er candidat (par
        priorite) qui repond, ou None. Les candidats sont testes en concurrence
        pour borner la latence a ~un timeout."""
        if company.domain:
            return company.domain
        candidates = _domain_candidates(company.name)
        if not candidates:
            return None
        async with self._client(self._domain_timeout) as client:
            checks = await asyncio.gather(
                *(self._domain_responds(client, c) for c in candidates),
                return_exceptions=True,
            )
        for candidate, ok in zip(candidates, checks, strict=True):
            if ok is True:
                return candidate
        return None
