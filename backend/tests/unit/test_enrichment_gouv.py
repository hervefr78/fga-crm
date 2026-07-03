"""Tests CompanySource FR (API gouv recherche-entreprises) via httpx.MockTransport :
get_by_siren, get_companies (ICP + min_revenue), resolve_domain (heuristique)."""

from __future__ import annotations

import httpx
import pytest

from app.services.enrichment.adapters.gouv import (
    GouvCompanySource,
    _domain_candidates,
    _normalize_for_domain,
)
from app.services.enrichment.ports import IcpFilter

_GOUV_HOST = "recherche-entreprises.api.gouv.fr"


def _company_result(siren: str, name: str, ca: int | None = None) -> dict:
    r = {
        "siren": siren, "nom_raison_sociale": name, "activite_principale": "62.01Z",
        "etat_administratif": "A", "tranche_effectif_salarie": "12",
    }
    if ca is not None:
        r["finances"] = {"2024": {"ca": ca, "resultat_net": 1000}}
    return r


def _source(handler) -> GouvCompanySource:
    return GouvCompanySource(transport=httpx.MockTransport(handler))


# ---------- get_by_siren ----------

@pytest.mark.asyncio
async def test_get_by_siren_maps_company():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == _GOUV_HOST
        assert request.url.params["q"] == "552081317"
        return httpx.Response(200, json={"results": [_company_result("552081317", "ACME")], "total_pages": 1})

    company = await _source(handler).get_by_siren("552081317")
    assert company is not None
    assert company.siren == "552081317"
    assert company.name == "ACME"
    assert company.naf == "62.01Z"
    assert company.active is True
    assert company.size_band == "20-49"
    assert company.domain is None


@pytest.mark.asyncio
async def test_get_by_siren_invalid_siren_no_http():
    called = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200, json={"results": []})

    assert await _source(handler).get_by_siren("abc") is None
    assert await _source(handler).get_by_siren("123") is None  # pas 9 chiffres
    assert called["n"] == 0  # aucun appel reseau sur input invalide


@pytest.mark.asyncio
async def test_get_by_siren_no_results():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": []})

    assert await _source(handler).get_by_siren("552081317") is None


# ---------- get_companies (ICP) ----------

@pytest.mark.asyncio
async def test_get_companies_respects_limit_and_naf():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["activite_principale"] == "62.01Z"
        assert request.url.params["etat_administratif"] == "A"
        results = [_company_result(str(500000000 + i), f"Boite {i}") for i in range(25)]
        return httpx.Response(200, json={"results": results, "total_pages": 100, "page": 1})

    icp = IcpFilter(naf_codes=["62.01Z"], only_active=True, limit=10)
    companies = await _source(handler).get_companies(icp)
    assert len(companies) == 10  # cappe a limit
    assert all(c.naf == "62.01Z" for c in companies)


@pytest.mark.asyncio
async def test_get_companies_filters_min_revenue():
    def handler(request: httpx.Request) -> httpx.Response:
        results = [
            _company_result("500000001", "Riche", ca=5_000_000),
            _company_result("500000002", "Pauvre", ca=100_000),
            _company_result("500000003", "SansCA", ca=None),
        ]
        return httpx.Response(200, json={"results": results, "total_pages": 1})

    icp = IcpFilter(naf_codes=["62.01Z"], min_revenue_eur=1_000_000, limit=10)
    companies = await _source(handler).get_companies(icp)
    assert [c.name for c in companies] == ["Riche"]  # seuls >= 1M€ (sans CA exclu)


# ---------- resolve_domain (heuristique) ----------

@pytest.mark.asyncio
async def test_resolve_domain_returns_first_responding():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "acme.fr":
            return httpx.Response(200)
        raise httpx.ConnectError("no such host")

    from app.services.enrichment.ports import Company
    domain = await _source(handler).resolve_domain(Company(siren="1", name="ACME SAS"))
    assert domain == "acme.fr"


@pytest.mark.asyncio
async def test_resolve_domain_none_when_no_candidate_responds():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no such host")

    from app.services.enrichment.ports import Company
    assert await _source(handler).resolve_domain(Company(siren="1", name="Introuvable XYZ")) is None


@pytest.mark.asyncio
async def test_resolve_domain_keeps_existing():
    from app.services.enrichment.ports import Company
    src = GouvCompanySource(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert await src.resolve_domain(Company(siren="1", name="X", domain="deja.fr")) == "deja.fr"


# ---------- helpers heuristique ----------

def test_normalize_and_candidates():
    assert _normalize_for_domain("SOPRACOM SAS") == "sopracom"
    assert _normalize_for_domain("Fast Growth Advisor SARL") == "fast growth advisor"
    cands = _domain_candidates("Fast Growth Advisor SARL")
    assert "fastgrowthadvisor.fr" in cands
    assert "fast-growth-advisor.com" in cands
    assert "fast.fr" in cands  # premier mot
