# =============================================================================
# FGA CRM - Enrichissement : helpers partages du pipeline
# =============================================================================
"""Helpers partages entre l'orchestrateur et les handlers de mode (company /
contacts) : parsing de cible, resolution des societes, sourcing des personnes
(cascade cout-croissant), fraicheur, et primitives bulk (persist/finalize).

Module feuille du graphe d'imports (ne depend NI de l'orchestrateur NI des modes)
-> garantit un graphe acyclique orchestrator -> {_pipeline, modes} ; modes -> _pipeline."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company as CrmCompany
from app.models.enrichment import (
    EnrichmentBulk,
    EnrichmentBulkItem,
    EnrichmentJob,
)
from app.services.enrichment import freshness
from app.services.enrichment.adapters.icypeas import _domain_from_url
from app.services.enrichment.credit_ledger import CreditLedger
from app.services.enrichment.ports import (
    Company,
    IcpFilter,
    PersonCandidate,
    SourceFilter,
    TargetSpec,
)
from app.services.enrichment.roles import normalize_title
from app.services.enrichment.suppression import is_suppressed

_TARGET_ROLES = ["CTO", "CPO", "CMO"]
_KEEP_ROLES = frozenset({"CTO", "CPO", "CMO", "FOUNDER"})
_GOUV_CONCURRENCY = 5  # requetes gouv concurrentes (respecte la limite douce ~7 req/s)

# Mode bulk (batch/icp) : email-search asynchrone via webhook (W3). Cout estime
# par ligne pour respecter le plafond du run (le debit reel est cote Icypeas).
_BULK_TASK = "email-search"
_VERIFY_TASK = "email-verification"
_BULK_CREDIT = 1.0


def _to_uuid(val: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        return None


def _now() -> datetime:
    return datetime.now(UTC)


def _parse_target(raw: dict) -> TargetSpec:
    icp = raw.get("icp_filter")
    source = raw.get("source_filter")
    return TargetSpec(
        kind=raw.get("kind", "company"),
        siren=raw.get("siren"),
        sirens=raw.get("sirens", []),
        icp_filter=IcpFilter(**icp) if icp else None,
        source_filter=SourceFilter(**source) if source else None,
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
        sirens = [s for s in target.sirens if s and not (s in seen or seen.add(s))]
        # #10 : resolution concurrente bornee (au lieu de 500 GET gouv sequentiels).
        sem = asyncio.Semaphore(_GOUV_CONCURRENCY)

        async def _fetch(siren: str):
            async with sem:
                return await company_src.get_by_siren(siren)

        results = await asyncio.gather(*(_fetch(s) for s in sirens))
        return [c for c in results if c]
    if target.kind == "icp" and target.icp_filter:
        return await company_src.get_companies(target.icp_filter)
    return []


async def _resolve_source_companies(
    db: AsyncSession, org_id, target: TargetSpec, company_src, stats: dict,
) -> list[Company]:
    """Mode 'source' : societes CRM de l'organisation filtrees par provenance.

    Meme semantique que le filtre Provenance de la liste Entreprises :
    'startup_radar' matche le lien SR (les fiches historiques n'ont pas lead_source).
    - siren present en base -> aucune requete gouv (donnees CRM directes) ;
    - siren absent -> resolution par nom (gouv), persistee sur la fiche (comme
      l'endpoint by-id) ; introuvable -> compte dans stats['skipped_no_siren'].
    """
    if target.source_filter is None:
        return []
    sf = target.source_filter

    query = select(CrmCompany).where(CrmCompany.organization_id == org_id)
    if sf.lead_source == "startup_radar":
        query = query.where(or_(
            CrmCompany.lead_source == "startup_radar",
            CrmCompany.startup_radar_id.is_not(None),
        ))
    else:
        query = query.where(CrmCompany.lead_source == sf.lead_source)
    query = query.order_by(CrmCompany.created_at.desc()).limit(sf.limit)
    rows = (await db.execute(query)).scalars().all()

    out: list[Company] = []
    sem = asyncio.Semaphore(_GOUV_CONCURRENCY)

    async def _resolve_missing(crm: CrmCompany) -> Company | None:
        async with sem:
            found = await company_src.search_by_name(crm.name)
        if found is None or not found.siren:
            return None
        # Persiste le siren resolu sur la fiche (evite les re-resolutions).
        crm.siren = found.siren
        return Company(
            siren=found.siren, name=crm.name,
            domain=_domain_from_url(crm.website) or found.domain,
        )

    with_siren = [c for c in rows if c.siren]
    without_siren = [c for c in rows if not c.siren]

    out.extend(
        Company(siren=c.siren, name=c.name, domain=_domain_from_url(c.website))
        for c in with_siren
    )
    resolved = await asyncio.gather(*(_resolve_missing(c) for c in without_siren))
    skipped = sum(1 for r in resolved if r is None)
    if skipped:
        stats["skipped_no_siren"] = stats.get("skipped_no_siren", 0) + skipped
    out.extend(r for r in resolved if r is not None)
    if without_siren:
        await db.commit()  # persiste les sirens resolus (checkpoint avant pipeline)
    return out


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
