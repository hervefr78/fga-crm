"""Tests des adapters Icypeas (email finder + verifier) via httpx.MockTransport.

Reproduit les reponses REELLES capturees (docs/compass/icypeas-api-reference.md) :
soumission -> {success, item:{_id, status}} ; read -> {items:[{results:{emails:[
{email, certainty}]}, status}]}.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx

from app.services.enrichment.adapters.icypeas import (
    IcypeasClient,
    IcypeasEmailFinder,
    IcypeasEmailVerifier,
    IcypeasPeopleSource,
    _map_certainty,
    parse_bulk_callback,
    verify_webhook_signature,
)
from app.services.enrichment.ports import Company, PersonCandidate

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


async def test_find_people_retries_on_timeout():
    """Timeout Icypeas sur find-people -> 1 retry -> succes au 2e essai (durcissement)."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("timeout", request=request)
        return _resp({"success": True, "leads": [
            {"firstname": "Jean", "lastname": "Dupont", "lastJobTitle": "CTO"},
        ]})

    leads = await _client(handler).find_people(company_name="SHERWOOD", job_titles=["CTO"])
    assert calls["n"] == 2  # a bien retry apres le timeout
    assert len(leads) == 1 and leads[0]["firstname"] == "Jean"


async def test_find_people_gives_up_after_two_timeouts():
    """2 timeouts consecutifs -> [] (pas de faux resultat, pas de crash)."""

    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    assert await _client(handler).find_people(company_name="X", job_titles=["CTO"]) == []


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


# ---------------------------------------------------------------------------
# find-people (leads DB) — reponse REELLE capturee (2 CTO chez Upsun)
# ---------------------------------------------------------------------------

_LEADS_RESPONSE = {
    "total": 2, "success": True,
    "leads": [
        {"firstname": "Guillaume", "lastname": "Moigneu", "lastJobTitle": "Field CTO",
         "profileUrl": "https://www.linkedin.com/in/guillaumemoigneu",
         "lastCompanyName": "Upsun", "lastCompanyWebsite": "http://www.upsun.com"},
        {"firstname": "Florian", "lastname": "Margaine", "lastJobTitle": "Field CTO",
         "profileUrl": "https://www.linkedin.com/in/florian-margaine-43971136",
         "lastCompanyName": "Upsun", "lastCompanyWebsite": "http://www.upsun.com"},
    ],
}

_COMPANY = Company(siren="123", name="Upsun", domain="www.upsun.com")


async def test_people_source_maps_leads_to_candidates():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        return _resp(_LEADS_RESPONSE)

    people = await IcypeasPeopleSource(_client(handler)).find_people(_COMPANY, ["CTO", "CPO", "CMO"])
    assert captured["path"].endswith("/find-people")
    assert len(people) == 2
    p = people[0]
    assert p.first_name == "Guillaume" and p.last_name == "Moigneu"
    assert p.title_raw == "Field CTO"
    assert p.linkedin_url == "https://www.linkedin.com/in/guillaumemoigneu"
    assert p.source == "icypeas"


async def test_people_source_empty_and_missing_names():
    def handler(request):
        return _resp({"success": True, "total": 1, "leads": [{"firstname": "", "lastname": "X"}]})

    # firstname vide -> lead ignore
    assert await IcypeasPeopleSource(_client(handler)).find_people(_COMPANY, ["CTO"]) == []


async def test_people_source_error_returns_empty():
    def handler(request):
        return httpx.Response(500, json={})

    assert await IcypeasPeopleSource(_client(handler)).find_people(_COMPANY, ["CTO"]) == []


# ---------------------------------------------------------------------------
# Bulk + webhook (async)
# ---------------------------------------------------------------------------

async def test_submit_bulk_returns_file_id_and_payload():
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return _resp({"success": True, "status": "in_progress", "file": "BULK123"})

    fid = await _client(handler).submit_bulk(
        "email-search", [["A", "B", "x.fr"]], ["e1"], "https://crm.example/cb",
    )
    assert fid == "BULK123"
    assert captured["path"].endswith("/bulk-search")
    body = captured["body"]
    assert body["task"] == "email-search"
    assert body["data"] == [["A", "B", "x.fr"]]
    assert body["custom"]["externalIds"] == ["e1"]
    assert body["custom"]["webhookUrlBulkDone"] == "https://crm.example/cb"
    assert body["custom"]["includeResultsInWebhook"] is True


def test_verify_webhook_signature():
    secret = "s3cr3t"
    path = "/api/v1/integrations/icypeas/webhook"
    ts = "2026-07-02T13:57:19.134Z"
    sig = hmac.new(secret.encode(), f"{path}{ts}".lower().encode(), hashlib.sha1).hexdigest()
    assert verify_webhook_signature(secret, path, ts, sig) is True
    assert verify_webhook_signature(secret, path, ts, "deadbeef") is False  # mauvaise sig
    assert verify_webhook_signature("", path, ts, sig) is False            # pas de secret
    assert verify_webhook_signature(secret, path, ts, "") is False         # pas de sig


# Payload webhook REEL capture (2 items, bulkDone + includeResults).
_REAL_CALLBACK_DATA = {
    "file": "1VUeI58BY3xwrP2mg7qU", "total": 2, "type": "email-search", "done": 2, "found": 2,
    "results": [
        {"results": {"firstname": "Herve", "lastname": "Dhelin",
                     "emails": [{"email": "herve@fast-growth.fr", "certainty": "ultra_sure"}]},
         "status": "DEBITED", "userData": {"externalId": "ext-1"}},
        {"results": {"firstname": "Michel", "lastname": "Test",
                     "emails": [{"email": "michel@fast-growth.fr", "certainty": "ultra_sure"}]},
         "status": "DEBITED", "userData": {"externalId": "ext-2"}},
    ],
}


def test_parse_bulk_callback_real_payload():
    items = parse_bulk_callback(_REAL_CALLBACK_DATA)
    assert len(items) == 2
    assert items[0]["external_id"] == "ext-1"
    assert items[0]["email"] == "herve@fast-growth.fr"
    assert items[0]["certainty"] == "ultra_sure"
    assert items[0]["status"] == "DEBITED"
    assert items[0]["firstname"] == "Herve"
    assert items[1]["external_id"] == "ext-2"


def test_parse_bulk_callback_not_found_item():
    data = {"results": [{"results": {"firstname": "X", "lastname": "Y", "emails": []},
                         "status": "NOT_FOUND", "userData": {"externalId": "e9"}}]}
    items = parse_bulk_callback(data)
    assert items[0]["external_id"] == "e9"
    assert items[0]["email"] is None
    assert items[0]["status"] == "NOT_FOUND"
