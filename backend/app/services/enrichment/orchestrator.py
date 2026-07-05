# =============================================================================
# FGA CRM - Enrichissement : orchestrateur (pipeline 7 etapes)
# =============================================================================
"""Execute un job d'enrichissement (spec §5) : comptes -> personnes (cascade) ->
emails -> verif + filtres RGPD -> contact CRM + provenance. Idempotent (DC5),
echec -> failed borne (DC2). Providers via factory (mock-first).

Dispatch pur : les helpers partages vivent dans `_pipeline`, les handlers de mode
dans `modes/` (company / contacts). Graphe acyclique orchestrator -> {_pipeline, modes}."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.enrichment import EnrichmentJob
from app.services.enrichment import freshness
from app.services.enrichment.credit_ledger import CreditLedger
from app.services.enrichment.factory import (
    get_company_source,
    get_email_finders,
    get_email_verifiers,
    get_people_sources,
)

from ._pipeline import (
    _now,
    _parse_target,
    _resolve_companies,
    _source_people,  # noqa: F401 — re-export pour tests (tests/unit/test_enrichment_quota.py)
)
from .modes.company import (
    _process_company,
    _should_use_bulk,
    _submit_bulk_job,
)
from .modes.contacts import (
    _contacts_use_bulk,
    _run_contacts_inline,
    _submit_bulk_contacts,
)

logger = logging.getLogger(__name__)

_MAX_ERROR_LEN = 2000


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
        "skipped_suppressed": 0, "errors": 0, "credits_spent": 0.0,
        # Decideurs enregistres SANS email (nom + role + LinkedIn) — domaine manquant.
        "contacts_no_email": 0,
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
