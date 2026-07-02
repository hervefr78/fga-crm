# =============================================================================
# FGA CRM - Enrichissement : orchestrateur (pipeline 7 etapes)
# =============================================================================
"""Execute un job d'enrichissement (spec §5) : comptes -> personnes (cascade) ->
emails -> verif + filtres RGPD -> contact CRM + provenance. Idempotent (DC5),
echec -> failed borne (DC2). Providers via factory (mock-first)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.enrichment import EnrichmentEmailVerification, EnrichmentJob
from app.services.enrichment import freshness
from app.services.enrichment.credit_ledger import CreditLedger
from app.services.enrichment.crm_writer import upsert_contact
from app.services.enrichment.factory import (
    get_company_source,
    get_email_finders,
    get_email_verifiers,
    get_people_sources,
)
from app.services.enrichment.ports import (
    Company,
    IcpFilter,
    PersonCandidate,
    TargetSpec,
)
from app.services.enrichment.provenance import record_provenance
from app.services.enrichment.rgpd import classify_email
from app.services.enrichment.roles import normalize_title
from app.services.enrichment.suppression import is_suppressed

logger = logging.getLogger(__name__)

_TARGET_ROLES = ["CTO", "CPO", "CMO"]
_KEEP_ROLES = frozenset({"CTO", "CPO", "CMO", "FOUNDER"})
_MAX_ERROR_LEN = 2000


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_target(raw: dict) -> TargetSpec:
    icp = raw.get("icp_filter")
    return TargetSpec(
        kind=raw.get("kind", "company"),
        siren=raw.get("siren"),
        sirens=raw.get("sirens", []),
        icp_filter=IcpFilter(**icp) if icp else None,
    )


async def _resolve_companies(company_src, target: TargetSpec) -> list[Company]:
    if target.kind == "company" and target.siren:
        c = await company_src.get_by_siren(target.siren)
        return [c] if c else []
    if target.kind == "batch":
        out = [await company_src.get_by_siren(s) for s in target.sirens]
        return [c for c in out if c]
    if target.kind == "icp" and target.icp_filter:
        return await company_src.get_companies(target.icp_filter)
    return []


def _normalize_and_dedup(people: list[PersonCandidate]) -> list[PersonCandidate]:
    """Assigne le role (normalize_title), garde les cibles+FOUNDER, dedup nom/linkedin."""
    seen: set[str] = set()
    out: list[PersonCandidate] = []
    for p in people:
        p.role = normalize_title(p.title_raw)
        if p.role not in _KEEP_ROLES:
            continue
        key = f"{p.first_name.lower()}|{p.last_name.lower()}"
        if key in seen or (p.linkedin_url and p.linkedin_url in seen):
            continue
        seen.add(key)
        if p.linkedin_url:
            seen.add(p.linkedin_url)
        out.append(p)
    return out


def _covers_targets(people: list[PersonCandidate]) -> bool:
    roles = {normalize_title(p.title_raw) for p in people}
    return all(r in roles for r in _TARGET_ROLES)


async def run_enrichment_job(db: AsyncSession, job: EnrichmentJob) -> None:
    """Execute le pipeline. Ne leve pas : echec -> statut failed (DC2)."""
    if job.status in ("done", "failed"):
        logger.info("[Enrichment] job %s deja terminal (%s), skip", job.id, job.status)
        return

    job.status = "running"
    await db.commit()

    stats = {
        "companies": 0, "people_found": 0, "emails_found": 0,
        "valid": 0, "suppressed": 0, "credits_spent": 0.0,
    }
    ledger = CreditLedger(max_per_run=settings.enrichment_max_credits_per_run)

    try:
        company_src = get_company_source()
        people_srcs = get_people_sources()
        finders = get_email_finders()
        verifiers = get_email_verifiers()

        target = _parse_target(job.target_json or {})
        companies = await _resolve_companies(company_src, target)

        for company in companies:
            domain = company.domain or await company_src.resolve_domain(company)
            if domain and await is_suppressed(db, domain=domain):
                stats["suppressed"] += 1
                continue
            stats["companies"] += 1

            # Etape 3 : sourcing personnes (cascade cout-croissant, stop-on-cover)
            people: list[PersonCandidate] = []
            for src in people_srcs:
                if not ledger.can_spend(src.cost_per_result):
                    break
                found = await src.find_people(company, _TARGET_ROLES)
                for _ in found:
                    ledger.record(src.name, src.cost_per_result)
                people.extend(found)
                if _covers_targets(people):
                    break
            people = _normalize_and_dedup(people)
            stats["people_found"] += len(people)

            # Etapes 4-6 : email -> verif -> RGPD -> contact
            for person in people:
                email = person.email
                if not email and domain:
                    for finder in finders:
                        if not ledger.can_spend(finder.cost_per_hit):
                            break
                        cand = await finder.find(person, domain)
                        if cand:
                            ledger.record(finder.name, finder.cost_per_hit)
                            email = cand.email
                            break
                if not email:
                    continue
                stats["emails_found"] += 1

                # Filtres RGPD bloquants (pro nominatif uniquement)
                domain_type = classify_email(email)
                if domain_type != "pro" or await is_suppressed(db, email=email):
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
                )
                db.add(EnrichmentEmailVerification(
                    organization_id=job.organization_id, contact_id=contact_id,
                    email=email, domain_type=domain_type, confidence=confidence,
                    status=status, deliverable=deliverable,
                    source=verification.source if verification else "unknown",
                ))
                await record_provenance(
                    db, entity_type="person", field="name", source=person.source,
                    contact_id=contact_id, organization_id=job.organization_id,
                )
                await record_provenance(
                    db, entity_type="email", field="email",
                    source=verification.source if verification else "unknown",
                    contact_id=contact_id, organization_id=job.organization_id,
                )
                if deliverable:
                    stats["valid"] += 1
                # Fraicheur : eviter de re-enrichir cette personne avant TTL
                await freshness.touch(
                    f"person:{company.siren}:{person.first_name}.{person.last_name}".lower(),
                    settings.enrichment_refresh_days,
                )

        stats["credits_spent"] = ledger.spent_this_run()
        job.stats_json = stats
        job.status = "done"
        job.finished_at = _now()
        await db.commit()

    except Exception as exc:  # noqa: BLE001 — converti en statut failed (DC2)
        logger.exception("[Enrichment] job %s echoue : %s", job.id, exc)
        await db.rollback()
        stale = await db.get(EnrichmentJob, job.id)
        if stale is not None:
            stale.status = "failed"
            stale.error = str(exc)[:_MAX_ERROR_LEN]
            stale.finished_at = _now()
            await db.commit()
