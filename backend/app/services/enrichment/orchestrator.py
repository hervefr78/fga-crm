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
from app.models.enrichment import (
    EnrichmentBulk,
    EnrichmentBulkItem,
    EnrichmentEmailVerification,
    EnrichmentJob,
)
from app.services.enrichment import freshness
from app.services.enrichment.credit_ledger import CreditLedger
from app.services.enrichment.crm_writer import upsert_contact
from app.services.enrichment.factory import (
    get_bulk_client,
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

# Mode bulk (batch/icp) : email-search asynchrone via webhook (W3). Cout estime
# par ligne pour respecter le plafond du run (le debit reel est cote Icypeas).
_BULK_TASK = "email-search"
_BULK_CREDIT = 1.0


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
        # Dedup des sirens (doublons CSV frequents) : evite de payer 2x le meme.
        seen: set[str] = set()
        out: list[Company] = []
        for s in target.sirens:
            if not s or s in seen:
                continue
            seen.add(s)
            c = await company_src.get_by_siren(s)
            if c:
                out.append(c)
        return out
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


def _freshness_key(org_id, siren: str | None, person: PersonCandidate) -> str:
    """Clef de fraicheur (delegue a freshness.person_key : format partage inline & bulk)."""
    return freshness.person_key(org_id, siren, person.first_name, person.last_name)


async def _source_people(
    db: AsyncSession,
    *,
    company: Company,
    company_src,
    people_srcs,
    ledger: CreditLedger,
    org_id,
    stats: dict,
) -> tuple[str | None, list[PersonCandidate]]:
    """Resout le domaine + source les personnes (cascade cout-croissant, stop-on-cover).

    Retourne (domain, people). Societe supprimee -> (None, []) (rien a traiter).
    Modifie `stats` en place.
    """
    domain = company.domain or await company_src.resolve_domain(company)
    if domain and await is_suppressed(db, organization_id=org_id, domain=domain):
        stats["suppressed"] += 1
        return None, []
    stats["companies"] += 1

    people: list[PersonCandidate] = []
    for src in people_srcs:
        if not ledger.can_spend(src.cost_per_result):
            break
        found = await src.find_people(company, _TARGET_ROLES)
        # #6 : ne debiter/garder que ce qui tient dans le budget du run. Un provider
        # peut renvoyer jusqu'a N leads alors que can_spend n'en couvrait qu'un.
        budget_exhausted = False
        for lead in found:
            if not ledger.can_spend(src.cost_per_result):
                budget_exhausted = True
                break
            ledger.record(src.name, src.cost_per_result)
            people.append(lead)
        if budget_exhausted or _covers_targets(people):
            break
    people = _normalize_and_dedup(people)
    stats["people_found"] += len(people)
    return domain, people


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

    if not rows:  # rien a enrichir -> job termine directement
        job.stats_json = stats
        job.status = "done"
        job.finished_at = _now()
        await db.commit()
        return

    file_id = await client.submit_bulk(_BULK_TASK, rows, ext_ids, settings.icypeas_webhook_url or "")
    if not file_id:
        raise RuntimeError("Icypeas bulk-search : soumission refusee")

    bulk = EnrichmentBulk(
        file=file_id, task=_BULK_TASK, status="awaiting_results",
        total=len(rows), done=0, found=0, organization_id=org_id, job_id=job.id,
    )
    db.add(bulk)
    await db.flush()
    for ext, ctx in zip(ext_ids, contexts, strict=True):
        db.add(EnrichmentBulkItem(
            bulk_id=bulk.id, external_id=ext, organization_id=org_id,
            status="pending", context_json=ctx,
        ))

    stats["bulk_submitted"] = len(rows)
    job.stats_json = stats
    job.status = "awaiting_results"  # le callback (W2) finalisera le job
    await db.commit()


async def run_enrichment_job(db: AsyncSession, job: EnrichmentJob) -> None:
    """Execute le pipeline. Ne leve pas : echec -> statut failed (DC2)."""
    if job.status in ("done", "failed"):
        logger.info("[Enrichment] job %s deja terminal (%s), skip", job.id, job.status)
        return

    job.status = "running"
    await db.commit()
    # Capture locale : org_id reste accessible apres les commits par societe.
    org_id = job.organization_id

    stats = {
        "companies": 0, "people_found": 0, "emails_found": 0,
        "valid": 0, "suppressed": 0, "skipped_fresh": 0,
        "skipped_no_domain": 0, "skipped_pre_emailed": 0, "bulk_submitted": 0,
        "errors": 0, "credits_spent": 0.0,
    }
    ledger = CreditLedger(max_per_run=settings.enrichment_max_credits_per_run)

    try:
        company_src = get_company_source()
        people_srcs = get_people_sources()
        finders = get_email_finders()
        verifiers = get_email_verifiers()

        target = _parse_target(job.target_json or {})
        companies = await _resolve_companies(company_src, target)

        # Client Redis reutilise sur toute la phase (fix #13 : un seul connect/close
        # par job au lieu d'un par personne). Ouvert dans CETTE event loop.
        async with freshness.client_scope() as fresh_client:
            # Mode bulk (W3) : batch/icp avec Icypeas reel -> soumission async + webhook.
            # Les contacts sont crees au callback (W2). Le pipeline inline est saute.
            if _should_use_bulk(target):
                await _submit_bulk_job(
                    db, job, companies, company_src=company_src, people_srcs=people_srcs,
                    ledger=ledger, org_id=org_id, stats=stats, fresh_client=fresh_client,
                )
                return

            for company in companies:
                # Resilience par societe : une erreur (provider reel KO, etc.) isole la
                # societe et preserve le travail deja committe des precedentes (checkpoint).
                try:
                    await _process_company(
                        db, company=company, company_src=company_src,
                        people_srcs=people_srcs, finders=finders, verifiers=verifiers,
                        ledger=ledger, org_id=org_id, stats=stats, fresh_client=fresh_client,
                    )
                    await db.commit()
                except Exception:  # noqa: BLE001 — echec isole a la societe, on continue
                    logger.exception(
                        "[Enrichment] job %s : societe %s echouee, skip",
                        job.id, getattr(company, "siren", "?"),
                    )
                    await db.rollback()
                    stats["errors"] += 1

        stats["credits_spent"] = ledger.spent_this_run()
        job.stats_json = stats
        job.status = "done"
        job.finished_at = _now()
        await db.commit()

    except Exception as exc:  # noqa: BLE001 — echec global -> statut failed borne (DC2)
        logger.exception("[Enrichment] job %s echoue : %s", job.id, exc)
        await db.rollback()
        stale = await db.get(EnrichmentJob, job.id)
        if stale is not None:
            stale.status = "failed"
            stale.error = str(exc)[:_MAX_ERROR_LEN]
            stale.stats_json = stats
            stale.finished_at = _now()
            await db.commit()
