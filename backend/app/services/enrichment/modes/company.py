# =============================================================================
# FGA CRM - Enrichissement : mode company/batch/icp
# =============================================================================
"""Traitement d'une societe : sourcing decideurs -> email -> verif -> RGPD ->
contact CRM (pipeline inline), et soumission bulk (W3) via Icypeas + webhook."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.enrichment import EnrichmentEmailVerification, EnrichmentJob
from app.services.enrichment import freshness
from app.services.enrichment.credit_ledger import CreditLedger
from app.services.enrichment.crm_writer import upsert_contact
from app.services.enrichment.factory import get_bulk_client
from app.services.enrichment.ports import Company, TargetSpec
from app.services.enrichment.provenance import record_provenance
from app.services.enrichment.rgpd import classify_email
from app.services.enrichment.suppression import is_suppressed

from .._pipeline import (
    _BULK_CREDIT,
    _BULK_TASK,
    _finalize_bulk_job,
    _freshness_key,
    _persist_bulk,
    _source_people,
)


async def _process_company(
    db: AsyncSession,
    *,
    company: Company,
    company_src,
    people_srcs,
    finders,
    verifiers,
    ledger: CreditLedger,
    org_id,
    stats: dict,
    fresh_client=None,
) -> None:
    """Traite UNE societe : sourcing -> email -> verif -> RGPD -> contact CRM.

    Modifie `stats` en place. Ne commit PAS : l'appelant gere le checkpoint par
    societe (resilience) et la transaction. `fresh_client` : client Redis reutilise
    sur la boucle chaude (fix #13, evite le churn de connexions).
    """
    domain, people = await _source_people(
        db, company=company, company_src=company_src, people_srcs=people_srcs,
        ledger=ledger, org_id=org_id, stats=stats,
    )

    # Etapes 4-6 : email -> verif -> RGPD -> contact
    for person in people:
        # Fraicheur (spec §13) : skip si deja enrichie recemment -> pas de re-depense.
        fresh_key = _freshness_key(org_id, company.siren, person)
        if await freshness.is_fresh(fresh_key, client=fresh_client):
            stats["skipped_fresh"] += 1
            continue

        email = person.email
        # Icypeas accepte `domainOrCompany` : a defaut de domaine resolu (~40% seulement),
        # on passe le nom de societe -> la personne reste enrichissable.
        dom_or_company = domain or company.name
        if not email and dom_or_company:
            for finder in finders:
                if not ledger.can_spend(finder.cost_per_hit):
                    break
                cand = await finder.find(person, dom_or_company)
                if cand:
                    ledger.record(finder.name, finder.cost_per_hit)
                    email = cand.email
                    break
        if not email:
            continue
        stats["emails_found"] += 1

        # Filtres RGPD bloquants (pro nominatif uniquement)
        domain_type = classify_email(email)
        if domain_type != "pro" or await is_suppressed(db, organization_id=org_id, email=email):
            continue

        # Verification
        verification = None
        for v in verifiers:
            if not ledger.can_spend(v.cost_per_check):
                break
            verification = await v.verify(email)
            ledger.record(v.name, v.cost_per_check)
            break
        status = verification.status if verification else "unknown"
        confidence = verification.confidence if verification else None
        deliverable = status == "valid" or (
            status == "catch_all"
            and confidence is not None
            and confidence >= settings.enrichment_catchall_accept
        )

        # Persistance : contact CRM + verif + provenance
        contact_id = await upsert_contact(
            db, company=company, person=person, email=email, email_status=status,
            organization_id=org_id,
        )
        db.add(EnrichmentEmailVerification(
            organization_id=org_id, contact_id=contact_id,
            email=email, domain_type=domain_type, confidence=confidence,
            status=status, deliverable=deliverable,
            source=verification.source if verification else "unknown",
        ))
        await record_provenance(
            db, entity_type="person", field="name", source=person.source,
            contact_id=contact_id, organization_id=org_id,
        )
        await record_provenance(
            db, entity_type="email", field="email",
            source=verification.source if verification else "unknown",
            contact_id=contact_id, organization_id=org_id,
        )
        if deliverable:
            stats["valid"] += 1
        # Fraicheur : marque la personne enrichie pour eviter la re-depense avant TTL
        await freshness.touch(fresh_key, settings.enrichment_refresh_days, client=fresh_client)


def _should_use_bulk(target: TargetSpec) -> bool:
    """Mode bulk (W3) : batch/icp + Icypeas reel + URL webhook configuree.

    Sinon (on-demand, mock, ou pas d'URL) -> pipeline inline synchrone (polling).
    """
    return (
        target.kind in ("batch", "icp")
        and bool(settings.icypeas_api_key)
        and bool(settings.icypeas_webhook_url)
    )


async def _submit_bulk_job(
    db: AsyncSession,
    job: EnrichmentJob,
    companies: list[Company],
    *,
    company_src,
    people_srcs,
    ledger: CreditLedger,
    org_id,
    stats: dict,
    fresh_client=None,
) -> None:
    """Mode bulk : source les personnes (inline) puis soumet UN bulk email-search
    a Icypeas avec callback webhook. Les contacts sont crees au callback (W2), pas ici.
    Le job passe `awaiting_results` (ou `done` si rien a enrichir)."""
    client = get_bulk_client()
    if client is None:  # garde defensive (ne devrait pas arriver vu _should_use_bulk)
        raise RuntimeError("Bulk indisponible : client Icypeas absent")

    rows: list[list[str]] = []
    ext_ids: list[str] = []
    contexts: list[dict] = []

    for company in companies:
        domain, people = await _source_people(
            db, company=company, company_src=company_src, people_srcs=people_srcs,
            ledger=ledger, org_id=org_id, stats=stats,
        )
        for person in people:
            # Icypeas accepte `domainOrCompany` : domaine resolu si dispo, sinon nom.
            dom_or_company = domain or company.name
            if not dom_or_company:
                stats["skipped_no_domain"] += 1
                continue
            fresh_key = _freshness_key(org_id, company.siren, person)
            if await freshness.is_fresh(fresh_key, client=fresh_client):
                stats["skipped_fresh"] += 1
                continue
            if person.email:
                # Aucun PeopleSource actuel ne fournit d'email : signale si ca change (DC2).
                stats["skipped_pre_emailed"] += 1
                continue
            if not ledger.can_spend(_BULK_CREDIT):
                break
            ledger.record("icypeas-bulk", _BULK_CREDIT)
            ext_ids.append(str(len(rows)))  # deterministe + unique dans le bulk
            rows.append([person.first_name, person.last_name, dom_or_company])
            contexts.append({
                "company": {"siren": company.siren, "name": company.name, "domain": domain},
                "person": {
                    "first_name": person.first_name, "last_name": person.last_name,
                    "title_raw": person.title_raw, "role": person.role,
                    "linkedin_url": person.linkedin_url,
                },
            })

    stats["credits_spent"] = ledger.spent_this_run()
    n = await _persist_bulk(db, job, client, _BULK_TASK, rows, ext_ids, contexts, org_id=org_id)
    _finalize_bulk_job(job, stats, n)
    await db.commit()
