"""Tests des adapters Icypeas (email finder + verifier) via httpx.MockTransport.

Reproduit les reponses REELLES capturees (docs/compass/icypeas-api-reference.md) :
soumission -> {success, item:{_id, status}} ; read -> {items:[{results:{emails:[
{email, certainty}]}, status}]}.
"""

from __future__ import annotations

import httpx

from app.services.enrichment.adapters.icypeas import (
    IcypeasClient,
    IcypeasEmailFinder,
    IcypeasEmailVerifier,
    _map_certainty,
)
from app.services.enrichment.ports import PersonCandidate

_PERSON = PersonCandidate(first_name="Herve", last_name="Dhelin", title_raw="CTO", source="mock")


def _resp(body: dict) -> httpx.Response:
    return httpx.Response(200, json=body)


def _submit_ok(_id: str = "abc") -> dict:
    return {"success": True, "item": {"_id": _id, "status": "NONE"}}


def _read(status: str, emails: list[dict]) -> dict:
    return {"success": True, "items": [{"results": {"emails": emails}, "status": status, "_id": "abc"}], "total": 1}


def _client(handler) -> IcypeasClient:
    return IcypeasClient(
        "test-key", transport=httpx.MockTransport(handler),
        poll_interval_s=0.01, max_wait_s=0.05,
    )


def test_map_certainty():
    assert _map_certainty("ultra_sure") == ("valid", 0.99)
    assert _map_certainty("probable") == ("valid", 0.90)
    assert _map_certainty("undeliverable") == ("invalid", 0.0)
    assert _map_certainty("not_found") == ("invalid", 0.0)
    assert _map_certainty("inconnu") == ("risky", 0.5)  # defaut prudent


async def test_finder_found_maps_email_and_certainty():
    def handler(request):
        if request.url.path.endswith("/email-search"):
            return _resp(_submit_ok())
        return _resp(_read("DEBITED", [{"email": "herve@fast-growth.fr", "certainty": "ultra_sure"}]))

    cand = await IcypeasEmailFinder(_client(handler)).find(_PERSON, "fast-growth.fr")
    assert cand is not None
    assert cand.email == "herve@fast-growth.fr"
    assert cand.status == "valid"
    assert cand.confidence == 0.99
    assert cand.source == "icypeas"


async def test_finder_not_found_returns_none():
    def handler(request):
        if request.url.path.endswith("/email-search"):
            return _resp(_submit_ok())
        return _resp(_read("NOT_FOUND", []))

    assert await IcypeasEmailFinder(_client(handler)).find(_PERSON, "x.fr") is None


async def test_finder_polls_until_terminal():
    calls = {"read": 0}

    def handler(request):
        if request.url.path.endswith("/email-search"):
            return _resp(_submit_ok())
        calls["read"] += 1
        if calls["read"] == 1:
            return _resp(_read("IN_PROGRESS", []))
        return _resp(_read("DEBITED", [{"email": "a@b.fr", "certainty": "probable"}]))

    cand = await IcypeasEmailFinder(_client(handler)).find(_PERSON, "b.fr")
    assert calls["read"] >= 2  # a bien polle
    assert cand is not None and cand.email == "a@b.fr" and cand.status == "valid"


async def test_finder_timeout_returns_none():
    def handler(request):
        if request.url.path.endswith("/email-search"):
            return _resp(_submit_ok())
        return _resp(_read("IN_PROGRESS", []))  # jamais terminal

    assert await IcypeasEmailFinder(_client(handler)).find(_PERSON, "x.fr") is None


async def test_finder_submit_refused_returns_none():
    def handler(request):
        return _resp({"success": False, "validationErrors": [{"field": "domainOrCompany"}]})

    assert await IcypeasEmailFinder(_client(handler)).find(_PERSON, "x.fr") is None


async def test_verifier_valid():
    def handler(request):
        if request.url.path.endswith("/email-verification"):
            return _resp(_submit_ok("v"))
        return _resp(_read("DEBITED", [{"email": "michel@fast-growth.fr", "certainty": "ultra_sure"}]))

    res = await IcypeasEmailVerifier(_client(handler)).verify("michel@fast-growth.fr")
    assert res.status == "valid"
    assert res.confidence == 0.99
    assert res.source == "icypeas"


async def test_verifier_undeliverable_is_invalid():
    def handler(request):
        if request.url.path.endswith("/email-verification"):
            return _resp(_submit_ok("v"))
        return _resp(_read("DEBITED", [{"email": "x@y.fr", "certainty": "undeliverable"}]))

    res = await IcypeasEmailVerifier(_client(handler)).verify("x@y.fr")
    assert res.status == "invalid"


async def test_verifier_no_result_is_invalid():
    def handler(request):
        if request.url.path.endswith("/email-verification"):
            return _resp(_submit_ok("v"))
        return _resp(_read("NOT_FOUND", []))

    res = await IcypeasEmailVerifier(_client(handler)).verify("x@y.fr")
    assert res.status == "invalid"
    assert res.confidence == 0.0


async def test_http_error_degrades_to_none():
    def handler(request):
        return httpx.Response(500, json={"error": "boom"})

    assert await IcypeasEmailFinder(_client(handler)).find(_PERSON, "x.fr") is None
    res = await IcypeasEmailVerifier(_client(handler)).verify("x@y.fr")
    assert res.status == "invalid"  # fail-safe : deny by default
