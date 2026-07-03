# =============================================================================
# FGA CRM - Startup Radar Sync : Startups → Companies
# sync_startups (upsert companies + funding activities/tasks)
# =============================================================================

import logging
import uuid

from sqlalchemy import func, select
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

    Retourne (result_partiel, sr_id_to_company_id_map).
    """
    result = SyncResult()
    sr_to_crm: dict[str, uuid.UUID] = {}

    try:
        startups = await client.get_startups()
    except StartupRadarError as e:
        result.errors.append(f"Fetch startups: {e}")
        return result, sr_to_crm

    for s in startups:
        sr_id = str(s.get("id", ""))
        if not sr_id:
            continue

        try:
            async with db.begin_nested():
                # 1. Chercher par startup_radar_id (idempotence principale, scopee org)
                stmt = select(Company).where(
                    Company.startup_radar_id == sr_id,
                    Company.organization_id == organization_id,
                )
                existing = (await db.execute(stmt)).scalar_one_or_none()

                # 2. Fallback SIREN : si SR fournit un siren, chercher une company
                #    deja creee (manuellement) avec ce siren. Evite les doublons
                #    quand le commercial a deja saisi la societe avec son SIREN.
                if not existing and s.get("siren"):
                    siren_clean = (s["siren"] or "").strip()[:9]
                    if siren_clean:
                        stmt_siren = select(Company).where(
                            Company.siren == siren_clean,
                            Company.startup_radar_id.is_(None),
                            Company.organization_id == organization_id,
                        )
                        existing = (await db.execute(stmt_siren)).scalar_one_or_none()
                        if existing:
                            # Lier la company existante a SR
                            existing.startup_radar_id = sr_id

                # 3. Fallback nom : chercher par nom (case-insensitive) si pas encore lie a SR
                #    Evite les doublons quand la company existe deja cree manuellement
                #    sans SIREN renseigne.
                if not existing and s.get("name"):
                    stmt2 = select(Company).where(
                        func.lower(Company.name) == s["name"].lower(),
                        Company.startup_radar_id.is_(None),
                        Company.organization_id == organization_id,
                    )
                    existing = (await db.execute(stmt2)).scalar_one_or_none()
                    if existing:
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

        except Exception as e:
            result.errors.append(f"Startup {s.get('name', sr_id)}: {e}")

    await db.flush()
    logger.info(
        "[SRSync] Startups: %d creees, %d mises a jour",
        result.companies_created,
        result.companies_updated,
    )
    return result, sr_to_crm
