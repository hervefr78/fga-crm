# =============================================================================
# FGA CRM - Enrichissement : traitement du callback webhook Icypeas (bulk)
# =============================================================================
"""Resout un bulk Icypeas a reception du webhook bulkDone : pour chaque item
(externalId -> EnrichmentBulkItem), applique les filtres RGPD puis cree le contact
CRM (reutilise crm_writer/rgpd/suppression/provenance — DC8). Idempotent."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.enrichment import (
    EnrichmentBulk,
    EnrichmentBulkItem,
    EnrichmentEmailVerification,
    EnrichmentJob,
)
from app.services.enrichment import freshness
from app.services.enrichment.adapters.icypeas import _map_certainty, parse_bulk_callback
from app.services.enrichment.crm_writer import update_contact_email, upsert_contact
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


def _to_uuid(val: object) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(val)) if val else None
    except (ValueError, TypeError, AttributeError):
        return None


async def _resolve_item(
    db: AsyncSession, bulk: EnrichmentBulk, item: EnrichmentBulkItem, res: dict,
    *, fresh_client=None,
) -> None:
    """Resout une ligne : RGPD -> contact CRM + verif + provenance. Modifie `item`."""
    org_id = bulk.organization_id
    ctx = item.context_json or {}
    comp = ctx.get("company") or {}
    pers = ctx.get("person") or {}
    existing_contact_id = _to_uuid(ctx.get("contact_id"))
    is_verify = bulk.task == "email-verification"
    email = res.get("email")

    if not email or res.get("status") not in _FOUND_STATUSES:
        # Reverify d'un email injoignable (#7/#8) : mailbox morte -> contact 'invalid'
        # (au lieu de garder son ancien statut). L'email d'origine est dans le contexte.
        ctx_email = ctx.get("email")
        if is_verify and existing_contact_id is not None and ctx_email:
            cid = await update_contact_email(
                db, contact_id=existing_contact_id, email=ctx_email, email_status="invalid",
                organization_id=org_id, backfill_domain=False,
            )
            if cid is not None:
                item.status = "found"
                item.email = ctx_email
                item.certainty = res.get("certainty")
                item.contact_id = cid
                return
        item.status = "not_found"
        return

    domain_type = classify_email(email)
    # Suppression RGPD : TOUJOURS verifiee, meme en reverify (#12 : ne pas re-marquer
    # deliverable un contact opt-out/bounce). Seule la classification pro/perso est
    # sautee pour un email deja en base (reverify).
    if await is_suppressed(db, organization_id=org_id, email=email):
        item.status = "not_found"
        return
    if not is_verify and domain_type != "pro":
        item.status = "not_found"  # rejete RGPD (email nouvellement trouve non pro)
        return

    status, confidence = _map_certainty(res.get("certainty"))
    deliverable = status == "valid"

    first = pers.get("first_name") or res.get("firstname") or ""
    last = pers.get("last_name") or res.get("lastname") or ""

    if existing_contact_id is not None:
        # Feature B : met a jour un contact EXISTANT (pas de create) + backfill domaine.
        contact_id = await update_contact_email(
            db, contact_id=existing_contact_id, email=email, email_status=status,
            organization_id=org_id,
        )
        if contact_id is None:  # contact disparu / hors org
            item.status = "not_found"
            return
    else:
        company = Company(
            siren=comp.get("siren") or "", name=comp.get("name") or "", domain=comp.get("domain"),
        )
        person = PersonCandidate(
            first_name=first, last_name=last, title_raw=pers.get("title_raw") or "",
            source="icypeas", linkedin_url=pers.get("linkedin_url"), role=pers.get("role"),
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
    # Fraicheur (#5) : marque la personne enrichie (meme clef que le pipeline inline)
    # -> un re-run du meme batch ne re-soumet/re-facture pas cette personne.
    await freshness.touch(
        freshness.person_key(org_id, comp.get("siren"), first, last),
        settings.enrichment_refresh_days, client=fresh_client,
    )


async def process_bulk_callback(db: AsyncSession, data: dict) -> dict:
    """Traite le payload `data` d'un webhook bulkDone. Idempotent (re-livraison sans effet)."""
    file_id = data.get("file")
    if not file_id:
        return {"matched": False}

    # Verrou de ligne (#3) : serialise les livraisons concurrentes/dupliquees du
    # meme callback (endpoint public, Icypeas peut re-livrer). Le 2e appel attend le
    # commit du 1er puis voit status='done' -> no-op. Ignore par SQLite (no-op tests).
    bulk = (
        await db.execute(
            select(EnrichmentBulk).where(EnrichmentBulk.file == file_id).with_for_update()
        )
    ).scalars().first()
    if bulk is None:
        logger.warning("[Icypeas webhook] bulk inconnu file=%s", file_id)
        return {"matched": False}
    if bulk.status in ("done", "error"):
        # #9 : etat terminal (error = timeout reconcile). Un callback tardif ne
        # doit pas re-traiter et recreer des contacts sur un job deja failed.
        return {"matched": True, "already_done": True}

    items = (
        await db.execute(select(EnrichmentBulkItem).where(EnrichmentBulkItem.bulk_id == bulk.id))
    ).scalars().all()
    by_ext = {i.external_id: i for i in items}

    # #6 : un seul client Redis pour toute la boucle (au lieu d'un par item via touch).
    async with freshness.client_scope() as fresh_client:
        for res in parse_bulk_callback(data):
            item = by_ext.get(res.get("external_id"))
            if item is None or item.status != "pending":
                continue  # inconnu ou deja resolu (idempotence)
            try:
                # Savepoint par item (#1/DC4) : une erreur (collision, ecriture) sur une
                # ligne n'annule pas tout le bulk (sinon perte des contacts Icypeas payes).
                async with db.begin_nested():
                    await _resolve_item(db, bulk, item, res, fresh_client=fresh_client)
            except Exception:  # noqa: BLE001 — echec isole a l'item, on continue
                logger.exception(
                    "[Icypeas webhook] item %s echoue, marque error", res.get("external_id")
                )
                item.status = "error"

    bulk.done = sum(1 for i in items if i.status != "pending")
    bulk.found = sum(1 for i in items if i.status == "found")
    if bulk.done >= bulk.total:
        bulk.status = "done"
        bulk.finished_at = _now()
        if bulk.job_id:
            # Verrou sur la ligne job (#1/#3) : serialise les callbacks concurrents
            # des differents bulks d'un meme job (reverify = 2 bulks). Sans ce verrou,
            # chacun voit l'autre encore 'awaiting_results' -> job jamais finalise.
            job = (
                await db.execute(
                    select(EnrichmentJob).where(EnrichmentJob.id == bulk.job_id).with_for_update()
                )
            ).scalar_one_or_none()
            if job is not None and job.status == "awaiting_results":
                # Job done quand tous les AUTRES bulks sont done (le courant l'est
                # deja). Le verrou job ci-dessus serialise les callbacks concurrents :
                # le 2e voit le bulk du 1er committe -> finalisation correcte.
                other_statuses = (
                    await db.execute(
                        select(EnrichmentBulk.status).where(
                            EnrichmentBulk.job_id == bulk.job_id,
                            EnrichmentBulk.id != bulk.id,
                        )
                    )
                ).scalars().all()
                if all(s == "done" for s in other_statuses):
                    job.status = "done"
                    job.finished_at = _now()
                    # Les stats de soumission datent d'AVANT les resultats
                    # (emails_found=0) : on les ecrase avec le reel des items.
                    await _refresh_job_stats(db, job)

    await db.commit()
    return {"matched": True, "done": bulk.done, "found": bulk.found, "total": bulk.total}


async def _refresh_job_stats(db: AsyncSession, job: EnrichmentJob) -> None:
    """Agrege les resultats REELS des bulks email-search dans job.stats_json.

    Sans ce refresh, le dashboard affiche les compteurs figes a la soumission
    (emails_found=0, valid=0) alors que le webhook a trouve des emails et cree
    les contacts. Nouveau dict assigne (JSONB : mutation in place non trackee).
    """
    items = (
        await db.execute(
            select(EnrichmentBulkItem)
            .join(EnrichmentBulk, EnrichmentBulkItem.bulk_id == EnrichmentBulk.id)
            .where(
                EnrichmentBulk.job_id == job.id,
                EnrichmentBulk.task == "email-search",
            )
        )
    ).scalars().all()
    if not items:
        return
    found = [i for i in items if i.status == "found"]
    valid = sum(1 for i in found if _map_certainty(i.certainty)[0] == "valid")
    job.stats_json = {
        **(job.stats_json or {}),
        "emails_found": len(found),
        "valid": valid,
    }


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
