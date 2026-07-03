# =============================================================================
# FGA CRM - Startup Radar Sync : Startups → Companies
# sync_startups (upsert companies + funding activities/tasks)
# =============================================================================

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.user import User
from app.services.startup_radar import StartupRadarClient, StartupRadarError

from ._common import SyncResult, _parse_iso_date
from .activities import create_funding_activity, create_qualification_task

logger = logging.getLogger(__name__)


async def sync_startups(
    db: AsyncSession,
    client: StartupRadarClient,
    user: User,
    organization_id: uuid.UUID,
) -> tuple[SyncResult, dict[str, uuid.UUID]]:
    """Synchroniser les startups SR en Companies CRM.

    Toutes les entites creees sont taggees `organization_id` et les recherches
    d'idempotence sont scopees a cette org (isolation multi-tenant).

    Perf (fix N+1) : au lieu de faire jusqu'a 3 SELECT d'idempotence par startup
    (par startup_radar_id, par siren, par lower(name)), on pre-charge en UNE
    requete toutes les companies de l'org et on construit 3 index en memoire.
    Les index sont MAINTENUS a chaque creation/liaison dans la boucle pour
    preserver la dedup intra-batch (deux startups pointant la meme company dans
    le meme sync ne doivent pas creer / re-lier un doublon).

    Retourne (result_partiel, sr_id_to_company_id_map).
    """
    result = SyncResult()
    sr_to_crm: dict[str, uuid.UUID] = {}

    try:
        startups = await client.get_startups()
    except StartupRadarError as e:
        result.errors.append(f"Fetch startups: {e}")
        return result, sr_to_crm

    # --- Pre-fetch : toutes les companies de l'org en UNE requete (borne org) ---
    # On charge les entites completes car la branche update mute directement les
    # objets (name, funding_*, custom_fields, etc.).
    existing_companies = (
        await db.execute(
            select(Company).where(Company.organization_id == organization_id)
        )
    ).scalars().all()

    # 3 index d'idempotence (memes criteres que les anciens SELECT) :
    # - by_sr_id : startup_radar_id -> Company (companies deja liees a SR)
    # - by_siren : siren -> Company parmi celles SANS startup_radar_id
    # - by_name  : lower(name) -> Company parmi celles SANS startup_radar_id
    # Les fallback siren/nom ne matchaient que des companies startup_radar_id IS
    # NULL : on reproduit ce filtre a la construction des index.
    by_sr_id: dict[str, Company] = {
        c.startup_radar_id: c for c in existing_companies if c.startup_radar_id
    }
    by_siren: dict[str, Company] = {
        c.siren: c
        for c in existing_companies
        if c.siren and c.startup_radar_id is None
    }
    by_name: dict[str, Company] = {
        c.name.lower(): c
        for c in existing_companies
        if c.startup_radar_id is None
    }

    for s in startups:
        sr_id = str(s.get("id", ""))
        if not sr_id:
            continue

        # Trace de ce qui a ete fait dans cet item (pour maj des index APRES
        # commit du savepoint — jamais avant, pour ne pas polluer les lookups
        # suivants si le savepoint rollback).
        new_company: Company | None = None
        linked_company: Company | None = None
        linked_orig_siren: str | None = None
        linked_orig_name: str | None = None

        try:
            async with db.begin_nested():
                # 1. Idempotence principale : startup_radar_id (scopee org)
                existing = by_sr_id.get(sr_id)

                # 2. Fallback SIREN : company deja creee (manuellement) avec ce
                #    siren, pas encore liee a SR. Evite les doublons.
                if existing is None and s.get("siren"):
                    siren_clean = (s["siren"] or "").strip()[:9]
                    if siren_clean:
                        candidate = by_siren.get(siren_clean)
                        if candidate is not None:
                            existing = candidate
                            linked_company = candidate
                            linked_orig_siren = candidate.siren
                            linked_orig_name = candidate.name.lower()
                            # Lier la company existante a SR
                            existing.startup_radar_id = sr_id

                # 3. Fallback nom (case-insensitive) si pas encore lie a SR.
                #    Evite les doublons quand la company existe deja (creee
                #    manuellement sans SIREN renseigne).
                if existing is None and s.get("name"):
                    candidate = by_name.get(s["name"].lower())
                    if candidate is not None:
                        existing = candidate
                        linked_company = candidate
                        linked_orig_siren = candidate.siren
                        linked_orig_name = candidate.name.lower()
                        # Lier la company existante a SR (pas de creation)
                        existing.startup_radar_id = sr_id

                # Preparer les custom_fields
                custom = {}
                if s.get("strategy"):
                    custom["strategy"] = s["strategy"]
                if s.get("amount"):
                    custom["funding_amount"] = s["amount"]
                if s.get("series"):
                    custom["funding_series"] = s["series"]
                if s.get("status"):
                    custom["sr_status"] = s["status"]

                if existing:
                    # Update
                    existing.name = s.get("name") or existing.name
                    existing.website = s.get("website") or existing.website
                    existing.industry = s.get("sector") or existing.industry
                    existing.description = s.get("description") or existing.description
                    merged = {**(existing.custom_fields or {}), **custom}
                    existing.custom_fields = merged

                    # --- Funding fields (additif, ne pas ecraser le commercial) ---
                    if s.get("siren") and not existing.siren:
                        existing.siren = s["siren"][:9]
                    funding_date_parsed = _parse_iso_date(s.get("funding_date"))
                    if funding_date_parsed and not existing.funding_date:
                        existing.funding_date = funding_date_parsed
                    # Conserver le montant le plus eleve (round le plus important)
                    if s.get("amount") and (not existing.funding_amount or s["amount"] > existing.funding_amount):
                        existing.funding_amount = s["amount"]
                    if s.get("series") and not existing.funding_series:
                        existing.funding_series = s["series"][:50]
                    if s.get("source_names"):
                        existing_sources = set(existing.funding_sources or [])
                        merged_sources = sorted(existing_sources | set(s["source_names"]))
                        existing.funding_sources = merged_sources

                    sr_to_crm[sr_id] = existing.id
                    result.companies_updated += 1
                    company_id = existing.id
                else:
                    # Insert
                    company_id = uuid.uuid4()
                    company = Company(
                        id=company_id,
                        name=s.get("name", "Sans nom"),
                        website=s.get("website"),
                        industry=s.get("sector"),
                        description=s.get("description"),
                        custom_fields=custom if custom else None,
                        startup_radar_id=sr_id,
                        lead_source="startup_radar",
                        owner_id=user.id,
                        organization_id=organization_id,
                        siren=(s.get("siren") or "")[:9] or None,
                        funding_date=_parse_iso_date(s.get("funding_date")),
                        funding_amount=s.get("amount"),
                        funding_series=(s.get("series") or "")[:50] or None,
                        funding_sources=s.get("source_names"),
                    )
                    db.add(company)
                    sr_to_crm[sr_id] = company_id
                    result.companies_created += 1
                    new_company = company

                # --- Activity 'funding_detected' + Task 'qualification' ---
                # Appele pour insert ET update (les helpers gerent l'idempotence).
                # SR filtre cote source : si la startup arrive ici avec amount,
                # c'est qu'elle est qualifying (cf. doc maitre 13.1).
                if s.get("amount"):
                    # Flush pour que company_id existe avant les FK des Activity/Task
                    await db.flush()
                    if await create_funding_activity(db, company_id, user.id, s, organization_id):
                        result.funding_activities_created += 1
                    if await create_qualification_task(db, company_id, user.id, s, organization_id):
                        result.qualification_tasks_created += 1

            # --- Savepoint commite OK : maintenir les index en memoire ---
            # CRITIQUE (dedup intra-batch) : sans cette maj, deux startups de meme
            # sr_id creeraient un doublon (constraint violation), et deux startups
            # pointant une meme company pre-existante par nom/siren la re-lieraient
            # (sr_id ecrase) → regression. On ne met a jour qu'APRES commit.
            if new_company is not None:
                by_sr_id[sr_id] = new_company
            elif linked_company is not None:
                # La company vient d'etre liee a SR : elle sort des index nom/siren
                # (qui n'indexent que les companies sans startup_radar_id) et entre
                # dans by_sr_id.
                by_sr_id[sr_id] = linked_company
                if linked_orig_siren and by_siren.get(linked_orig_siren) is linked_company:
                    del by_siren[linked_orig_siren]
                if linked_orig_name is not None and by_name.get(linked_orig_name) is linked_company:
                    del by_name[linked_orig_name]

        except Exception as e:
            result.errors.append(f"Startup {s.get('name', sr_id)}: {e}")

    await db.flush()
    logger.info(
        "[SRSync] Startups: %d creees, %d mises a jour",
        result.companies_created,
        result.companies_updated,
    )
    return result, sr_to_crm
