# =============================================================================
# FGA CRM - Enrichissement : traitement du callback webhook Icypeas (bulk)
# =============================================================================
"""Resout un bulk Icypeas a reception du webhook bulkDone : pour chaque item
(externalId -> EnrichmentBulkItem), applique les filtres RGPD puis cree le contact
CRM (reutilise crm_writer/rgpd/suppression/provenance — DC8). Idempotent."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrichment import (
    EnrichmentBulk,
    EnrichmentBulkItem,
    EnrichmentEmailVerification,
    EnrichmentJob,
)
from app.services.enrichment.adapters.icypeas import _map_certainty, parse_bulk_callback
from app.services.enrichment.crm_writer import upsert_contact
from app.services.enrichment.ports import Company, PersonCandidate
from app.services.enrichment.provenance import record_provenance
from app.services.enrichment.rgpd import classify_email
from app.services.enrichment.suppression import is_suppressed

logger = logging.getLogger(__name__)

_FOUND_STATUSES = frozenset({"DEBITED", "FOUND"})
_STUCK_STATUSES = ("submitted", "awaiting_results")
_RECONCILE_BATCH = 100


def _now() -> datetime:
    return datetime.now(UTC)


async def _resolve_item(
    db: AsyncSession, bulk: EnrichmentBulk, item: EnrichmentBulkItem, res: dict
) -> None:
    """Resout une ligne : RGPD -> contact CRM + verif + provenance. Modifie `item`."""
    org_id = bulk.organization_id
    email = res.get("email")
    if not email or res.get("status") not in _FOUND_STATUSES:
        item.status = "not_found"
        return

    domain_type = classify_email(email)
    if domain_type != "pro" or await is_suppressed(db, organization_id=org_id, email=email):
        item.status = "not_found"  # rejete RGPD/suppression
        return

    status, confidence = _map_certainty(res.get("certainty"))
    deliverable = status == "valid"

    ctx = item.context_json or {}
    comp = ctx.get("company") or {}
    pers = ctx.get("person") or {}
    company = Company(
        siren=comp.get("siren") or "", name=comp.get("name") or "", domain=comp.get("domain"),
    )
    person = PersonCandidate(
        first_name=pers.get("first_name") or res.get("firstname") or "",
        last_name=pers.get("last_name") or res.get("lastname") or "",
        title_raw=pers.get("title_raw") or "",
        source="icypeas",
        linkedin_url=pers.get("linkedin_url"),
        role=pers.get("role"),
    )

    contact_id = await upsert_contact(
        db, company=company, person=person, email=email, email_status=status,
        organization_id=org_id,
    )
    db.add(EnrichmentEmailVerification(
        organization_id=org_id, contact_id=contact_id, email=email, domain_type=domain_type,
        confidence=confidence, status=status, deliverable=deliverable, source="icypeas",
    ))
    await record_provenance(
        db, entity_type="email", field="email", source="icypeas",
        contact_id=contact_id, organization_id=org_id,
    )
    item.status = "found"
    item.email = email
    item.certainty = res.get("certainty")
    item.contact_id = contact_id


async def process_bulk_callback(db: AsyncSession, data: dict) -> dict:
    """Traite le payload `data` d'un webhook bulkDone. Idempotent (re-livraison sans effet)."""
    file_id = data.get("file")
    if not file_id:
        return {"matched": False}

    bulk = (
        await db.execute(select(EnrichmentBulk).where(EnrichmentBulk.file == file_id))
    ).scalars().first()
    if bulk is None:
        logger.warning("[Icypeas webhook] bulk inconnu file=%s", file_id)
        return {"matched": False}
    if bulk.status == "done":
        return {"matched": True, "already_done": True}

    items = (
        await db.execute(select(EnrichmentBulkItem).where(EnrichmentBulkItem.bulk_id == bulk.id))
    ).scalars().all()
    by_ext = {i.external_id: i for i in items}

    for res in parse_bulk_callback(data):
        item = by_ext.get(res.get("external_id"))
        if item is None or item.status != "pending":
            continue  # inconnu ou deja resolu (idempotence)
        await _resolve_item(db, bulk, item, res)

    bulk.done = sum(1 for i in items if i.status != "pending")
    bulk.found = sum(1 for i in items if i.status == "found")
    if bulk.done >= bulk.total:
        bulk.status = "done"
        bulk.finished_at = _now()
        if bulk.job_id:
            job = await db.get(EnrichmentJob, bulk.job_id)
            if job is not None and job.status == "awaiting_results":
                job.status = "done"
                job.finished_at = _now()

    await db.commit()
    return {"matched": True, "done": bulk.done, "found": bulk.found, "total": bulk.total}


async def reconcile_stuck_bulks(db: AsyncSession, *, timeout_hours: int) -> int:
    """Filet de securite : un bulk sans callback (webhook rate/perdu) reste bloque en
    `awaiting_results`. Au-dela du timeout, on le marque `error` et on echoue le job
    associe (DC2 : pas de blocage silencieux). Retourne le nombre de bulks finalises.

    Note : un re-poll auto des resultats necessiterait l'endpoint de lecture bulk
    Icypeas (non capture) — on finalise proprement plutot que d'inventer un contrat
    non verifie. Le webhook (includeResults) reste le chemin nominal."""
    cutoff = _now() - timedelta(hours=timeout_hours)
    stuck = (
        await db.execute(
            select(EnrichmentBulk)
            .where(
                EnrichmentBulk.status.in_(_STUCK_STATUSES),
                EnrichmentBulk.created_at < cutoff,
            )
            .limit(_RECONCILE_BATCH)
        )
    ).scalars().all()

    for bulk in stuck:
        logger.warning(
            "[Enrichment reconcile] bulk %s (file=%s) sans callback > %sh -> error",
            bulk.id, bulk.file, timeout_hours,
        )
        bulk.status = "error"
        bulk.error = "callback Icypeas non recu (timeout)"
        bulk.finished_at = _now()
        if bulk.job_id:
            job = await db.get(EnrichmentJob, bulk.job_id)
            if job is not None and job.status == "awaiting_results":
                job.status = "failed"
                job.error = "callback Icypeas non recu (timeout reconciliation)"
                job.finished_at = _now()

    await db.commit()
    return len(stuck)
