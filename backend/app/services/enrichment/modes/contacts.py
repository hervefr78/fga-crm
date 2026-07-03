# =============================================================================
# FGA CRM - Enrichissement : mode contacts (Feature B)
# =============================================================================
"""Enrichissement de contacts CRM existants : trouve l'email manquant (ou
re-verifie l'existant), en bulk (2 bulks : find + reverify) ou inline."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company as CrmCompany
from app.models.contact import Contact
from app.models.enrichment import EnrichmentEmailVerification, EnrichmentJob
from app.services.enrichment.credit_ledger import CreditLedger
from app.services.enrichment.crm_writer import update_contact_email
from app.services.enrichment.factory import get_bulk_client
from app.services.enrichment.ports import PersonCandidate, TargetSpec
from app.services.enrichment.provenance import record_provenance
from app.services.enrichment.rgpd import classify_email
from app.services.enrichment.suppression import is_suppressed

from .._pipeline import (
    _BULK_CREDIT,
    _BULK_TASK,
    _VERIFY_TASK,
    _finalize_bulk_job,
    _persist_bulk,
    _to_uuid,
)

logger = logging.getLogger(__name__)

_MAX_CONTACTS = 1000  # borne DC1 sur une selection de contacts a enrichir


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
    companies = await _load_companies(db, contacts, org_id)  # #4/#5 : evite le N+1
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
            # Reverify : bulk email-verification (row = [email]). L'email est mis
            # dans le contexte -> si NOT_FOUND, le webhook marque le contact 'invalid'.
            if not ledger.can_spend(_BULK_CREDIT):
                break
            ledger.record("icypeas-verify", _BULK_CREDIT)
            v_ext.append(str(len(v_rows)))
            v_rows.append([contact.email])
            v_ctx.append({**base_ctx, "email": contact.email})
            continue
        # Sans email : bulk email-search (row = [first, last, domainOrCompany])
        company = companies.get(contact.company_id) if contact.company_id else None
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


async def _load_companies(db: AsyncSession, contacts: list[Contact], org_id) -> dict:
    """Precharge en UNE requete les societes liees (evite le N+1 db.get par contact)."""
    ids = {c.company_id for c in contacts if c.company_id}
    if not ids:
        return {}
    rows = (
        await db.execute(select(CrmCompany).where(
            CrmCompany.id.in_(ids), CrmCompany.organization_id == org_id,
        ))
    ).scalars().all()
    return {c.id: c for c in rows}


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
    companies: dict,
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
        company = companies.get(contact.company_id) if contact.company_id else None
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
    companies = await _load_companies(db, contacts, org_id)  # #4/#5 : evite le N+1
    for contact in contacts:
        try:
            await _process_contact(
                db, contact, finders=finders, verifiers=verifiers, ledger=ledger,
                org_id=org_id, stats=stats, reverify=target.reverify, companies=companies,
            )
            await db.commit()
        except Exception:  # noqa: BLE001 — echec isole au contact
            logger.exception("[Enrichment] job contacts : contact %s echoue, skip", contact.id)
            await db.rollback()
            stats["errors"] += 1
