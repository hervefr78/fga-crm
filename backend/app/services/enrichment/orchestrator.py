# =============================================================================
# FGA CRM - Enrichissement : orchestrateur (pipeline 7 etapes)
# =============================================================================
"""Execute un job d'enrichissement (spec §5) : comptes -> personnes (cascade) ->
emails -> verif + filtres RGPD -> contact CRM + provenance. Idempotent (DC5),
echec -> failed borne (DC2). Providers via factory (mock-first)."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company as CrmCompany
from app.models.contact import Contact
from app.models.enrichment import (
    EnrichmentBulk,
    EnrichmentBulkItem,
    EnrichmentEmailVerification,
    EnrichmentJob,
)
from app.services.enrichment import freshness
from app.services.enrichment.credit_ledger import CreditLedger
from app.services.enrichment.crm_writer import update_contact_email, upsert_contact
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
_MAX_CONTACTS = 1000  # borne DC1 sur une selection de contacts a enrichir


def _to_uuid(val: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        return None

# Mode bulk (batch/icp) : email-search asynchrone via webhook (W3). Cout estime
# par ligne pour respecter le plafond du run (le debit reel est cote Icypeas).
_BULK_TASK = "email-search"
_VERIFY_TASK = "email-verification"
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
        contact_ids=raw.get("contact_ids", []),
        all_missing_email=bool(raw.get("all_missing_email", False)),
        reverify=bool(raw.get("reverify", False)),
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
    n = await _persist_bulk(db, job, client, _BULK_TASK, rows, ext_ids, contexts, org_id=org_id)
    _finalize_bulk_job(job, stats, n)
    await db.commit()


def _finalize_bulk_job(job: EnrichmentJob, stats: dict, submitted: int) -> None:
    """Statut final apres soumission des bulks : awaiting_results si >0, sinon done."""
    stats["bulk_submitted"] = submitted
    job.stats_json = stats
    if submitted > 0:
        job.status = "awaiting_results"  # le(s) callback(s) (W2) finalisent le job
    else:
        job.status = "done"
        job.finished_at = _now()


async def _persist_bulk(
    db: AsyncSession, job: EnrichmentJob, client, task: str,
    rows: list[list[str]], ext_ids: list[str], contexts: list[dict], *, org_id,
) -> int:
    """Soumet UN bulk (task) a Icypeas + persiste EnrichmentBulk/Items. Retourne le
    nb de lignes soumises (0 si rien). Ne commit pas (l'appelant gere le job)."""
    if not rows:
        return 0
    file_id = await client.submit_bulk(task, rows, ext_ids, settings.icypeas_webhook_url or "")
    if not file_id:
        raise RuntimeError(f"Icypeas bulk ({task}) : soumission refusee")
    bulk = EnrichmentBulk(
        file=file_id, task=task, status="awaiting_results",
        total=len(rows), done=0, found=0, organization_id=org_id, job_id=job.id,
    )
    db.add(bulk)
    await db.flush()
    for ext, ctx in zip(ext_ids, contexts, strict=True):
        db.add(EnrichmentBulkItem(
            bulk_id=bulk.id, external_id=ext, organization_id=org_id,
            status="pending", context_json=ctx,
        ))
    return len(rows)


def _contacts_use_bulk(target: TargetSpec) -> bool:
    """Mode contacts en bulk (find manquants + reverify existants via 2 bulks) :
    Icypeas reel + URL webhook."""
    return (
        target.kind == "contacts"
        and bool(settings.icypeas_api_key)
        and bool(settings.icypeas_webhook_url)
    )


async def _submit_bulk_contacts(
    db: AsyncSession, job: EnrichmentJob, target: TargetSpec, *,
    ledger: CreditLedger, org_id, stats: dict,
) -> None:
    """Mode contacts (bulk) : soumet UN bulk email-search (contacts sans email) ET,
    si reverify, UN bulk email-verification (contacts avec email). Le contexte porte
    `contact_id` -> le webhook MET A JOUR le contact (W2). Job done quand TOUS finis."""
    client = get_bulk_client()
    if client is None:
        raise RuntimeError("Bulk indisponible : client Icypeas absent")

    contacts = await _resolve_contacts(db, target, org_id)
    s_rows: list[list[str]] = []
    s_ext: list[str] = []
    s_ctx: list[dict] = []
    v_rows: list[list[str]] = []
    v_ext: list[str] = []
    v_ctx: list[dict] = []

    for contact in contacts:
        base_ctx = {
            "contact_id": str(contact.id),  # marque le mode UPDATE cote webhook
            "person": {"first_name": contact.first_name, "last_name": contact.last_name},
        }
        if contact.email:
            if not target.reverify:
                stats["skipped_has_email"] += 1
                continue
            # Reverify : bulk email-verification (row = [email])
            if not ledger.can_spend(_BULK_CREDIT):
                break
            ledger.record("icypeas-verify", _BULK_CREDIT)
            v_ext.append(str(len(v_rows)))
            v_rows.append([contact.email])
            v_ctx.append(base_ctx)
            continue
        # Sans email : bulk email-search (row = [first, last, domainOrCompany])
        company = await db.get(CrmCompany, contact.company_id) if contact.company_id else None
        dom_or_company = (company.domain or company.name) if company else None
        if not dom_or_company:
            stats["skipped_no_company"] += 1
            continue
        if not ledger.can_spend(_BULK_CREDIT):
            break
        ledger.record("icypeas-bulk", _BULK_CREDIT)
        s_ext.append(str(len(s_rows)))
        s_rows.append([contact.first_name, contact.last_name, dom_or_company])
        s_ctx.append({
            **base_ctx,
            "company": {"siren": "", "name": company.name if company else "", "domain": company.domain if company else None},
        })

    stats["credits_spent"] = ledger.spent_this_run()
    n = await _persist_bulk(db, job, client, _BULK_TASK, s_rows, s_ext, s_ctx, org_id=org_id)
    n += await _persist_bulk(db, job, client, _VERIFY_TASK, v_rows, v_ext, v_ctx, org_id=org_id)
    _finalize_bulk_job(job, stats, n)
    await db.commit()


async def _resolve_contacts(db: AsyncSession, target: TargetSpec, org_id) -> list[Contact]:
    """Resout la selection de contacts (org-scopee, bornee). Feature B :
    - contact_ids : ces contacts precis.
    - all_missing_email sans reverify : contacts sans email (a trouver).
    - all_missing_email avec reverify : TOUS les contacts (manquants -> find,
      remplis -> re-verify) — sinon le reverify n'aurait aucune cible."""
    stmt = select(Contact).where(Contact.organization_id == org_id)
    if target.contact_ids:
        ids = [u for u in (_to_uuid(c) for c in target.contact_ids) if u is not None]
        if not ids:
            return []
        stmt = stmt.where(Contact.id.in_(ids))
    elif target.all_missing_email:
        if not target.reverify:
            stmt = stmt.where(Contact.email.is_(None))
    else:
        return []
    stmt = stmt.limit(_MAX_CONTACTS)
    return list((await db.execute(stmt)).scalars().all())


async def _process_contact(
    db: AsyncSession,
    contact: Contact,
    *,
    finders,
    verifiers,
    ledger: CreditLedger,
    org_id,
    stats: dict,
    reverify: bool,
) -> None:
    """Enrichit UN contact existant (Feature B) : trouve l'email manquant (ou
    re-verifie l'existant si reverify), met a jour le contact + provenance."""
    has_email = bool(contact.email)
    if has_email and not reverify:
        stats["skipped_has_email"] += 1
        return

    email = contact.email
    person = PersonCandidate(
        first_name=contact.first_name, last_name=contact.last_name,
        title_raw=contact.title or "", source="crm", linkedin_url=contact.linkedin_url,
    )

    if not has_email:
        # Trouver l'email : domaine de la societe liee, sinon nom (domainOrCompany).
        company = await db.get(CrmCompany, contact.company_id) if contact.company_id else None
        dom_or_company = (company.domain or company.name) if company else None
        if not dom_or_company:
            stats["skipped_no_company"] += 1
            return
        for finder in finders:
            if not ledger.can_spend(finder.cost_per_hit):
                break
            cand = await finder.find(person, dom_or_company)
            if cand:
                ledger.record(finder.name, finder.cost_per_hit)
                email = cand.email
                break
        if not email:
            return
        stats["emails_found"] += 1
        # Filtres RGPD bloquants (uniquement sur un email nouvellement trouve).
        domain_type = classify_email(email)
        if domain_type != "pro" or await is_suppressed(db, organization_id=org_id, email=email):
            return

    # Verification (email trouve OU existant a re-verifier)
    verification = None
    for v in verifiers:
        if not ledger.can_spend(v.cost_per_check):
            break
        verification = await v.verify(email)
        ledger.record(v.name, v.cost_per_check)
        break
    status = verification.status if verification else "unknown"
    deliverable = status == "valid"

    cid = await update_contact_email(
        db, contact_id=contact.id, email=email, email_status=status, organization_id=org_id,
    )
    if cid is None:  # contact disparu / hors org
        return
    db.add(EnrichmentEmailVerification(
        organization_id=org_id, contact_id=cid, email=email, domain_type=classify_email(email),
        confidence=verification.confidence if verification else None,
        status=status, deliverable=deliverable,
        source=verification.source if verification else "icypeas",
    ))
    await record_provenance(
        db, entity_type="email", field="email", source="icypeas",
        contact_id=cid, organization_id=org_id,
    )
    if deliverable:
        stats["valid"] += 1
    stats["updated"] += 1


async def _run_contacts_inline(
    db: AsyncSession, target: TargetSpec, *,
    finders, verifiers, ledger: CreditLedger, org_id, stats: dict,
) -> None:
    """Mode contacts (inline) : enrichit chaque contact, checkpoint par contact."""
    contacts = await _resolve_contacts(db, target, org_id)
    for contact in contacts:
        try:
            await _process_contact(
                db, contact, finders=finders, verifiers=verifiers, ledger=ledger,
                org_id=org_id, stats=stats, reverify=target.reverify,
            )
            await db.commit()
        except Exception:  # noqa: BLE001 — echec isole au contact
            logger.exception("[Enrichment] job contacts : contact %s echoue, skip", contact.id)
            await db.rollback()
            stats["errors"] += 1


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
        "updated": 0, "skipped_has_email": 0, "skipped_no_company": 0,
        "errors": 0, "credits_spent": 0.0,
    }
    ledger = CreditLedger(max_per_run=settings.enrichment_max_credits_per_run)

    try:
        company_src = get_company_source()
        people_srcs = get_people_sources()
        finders = get_email_finders()
        verifiers = get_email_verifiers()

        target = _parse_target(job.target_json or {})

        # Mode contacts (Feature B) : enrichir des contacts existants.
        if target.kind == "contacts":
            # Bulk async (find emails manquants) si Icypeas+webhook, sinon inline.
            if _contacts_use_bulk(target):
                await _submit_bulk_contacts(
                    db, job, target, ledger=ledger, org_id=org_id, stats=stats,
                )
                return  # awaiting_results : le webhook (W2) met a jour les contacts
            await _run_contacts_inline(
                db, target, finders=finders, verifiers=verifiers,
                ledger=ledger, org_id=org_id, stats=stats,
            )
            stats["credits_spent"] = ledger.spent_this_run()
            job.stats_json = stats
            job.status = "done"
            job.finished_at = _now()
            await db.commit()
            return

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
