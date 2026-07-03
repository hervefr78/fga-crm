# =============================================================================
# FGA CRM - Startup Radar Sync : Investors + Contacts
# sync_investors (→ Companies) + sync_contacts (→ Contacts)
# =============================================================================

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.contact import Contact
from app.models.user import User
from app.services.startup_radar import StartupRadarClient, StartupRadarError

from ._common import SyncResult

logger = logging.getLogger(__name__)


async def sync_investors(
    db: AsyncSession,
    client: StartupRadarClient,
    user: User,
    organization_id: uuid.UUID,
) -> SyncResult:
    """Synchroniser les investisseurs SR en Companies CRM (industry=Capital-risque).

    Toutes les entites creees sont taggees `organization_id` et les recherches
    d'idempotence sont scopees a cette org (isolation multi-tenant).
    """
    result = SyncResult()

    try:
        investors = await client.get_investors()
    except StartupRadarError as e:
        result.errors.append(f"Fetch investors: {e}")
        return result

    for inv in investors:
        inv_id = str(inv.get("id", ""))
        if not inv_id:
            continue

        # Prefixe inv: pour distinguer des startups
        sr_id = f"inv:{inv_id}"

        try:
            async with db.begin_nested():
                # 1. Chercher par startup_radar_id (scopee org)
                stmt = select(Company).where(
                    Company.startup_radar_id == sr_id,
                    Company.organization_id == organization_id,
                )
                existing = (await db.execute(stmt)).scalar_one_or_none()

                # 2. Fallback nom case-insensitive (evite doublons si cree manuellement)
                if not existing and inv.get("name"):
                    stmt2 = select(Company).where(
                        func.lower(Company.name) == inv["name"].lower(),
                        Company.startup_radar_id.is_(None),
                        Company.organization_id == organization_id,
                    )
                    existing = (await db.execute(stmt2)).scalar_one_or_none()
                    if existing:
                        existing.startup_radar_id = sr_id

                custom = {}
                if inv.get("startups_count"):
                    custom["portfolio_size"] = inv["startups_count"]
                if inv.get("total_funding_amount"):
                    custom["total_invested"] = inv["total_funding_amount"]

                if existing:
                    existing.name = inv.get("name") or existing.name
                    existing.website = inv.get("website") or existing.website
                    existing.industry = "Capital-risque"
                    merged = {**(existing.custom_fields or {}), **custom}
                    existing.custom_fields = merged
                    result.investors_updated += 1
                else:
                    company = Company(
                        id=uuid.uuid4(),
                        name=inv.get("name", "Investisseur inconnu"),
                        website=inv.get("website"),
                        industry="Capital-risque",
                        custom_fields=custom if custom else None,
                        startup_radar_id=sr_id,
                        lead_source="startup_radar",
                        owner_id=user.id,
                        organization_id=organization_id,
                    )
                    db.add(company)
                    result.investors_created += 1

        except Exception as e:
            result.errors.append(f"Investor {inv.get('name', inv_id)}: {e}")

    await db.flush()
    logger.info(
        "[SRSync] Investors: %d crees, %d mis a jour",
        result.investors_created,
        result.investors_updated,
    )
    return result


async def sync_contacts(
    db: AsyncSession,
    client: StartupRadarClient,
    user: User,
    sr_to_crm: dict[str, uuid.UUID],
    organization_id: uuid.UUID,
) -> SyncResult:
    """Synchroniser les contacts SR en Contacts CRM.

    sr_to_crm : mapping startup_radar_id → company_id CRM (pour lier contact → company).

    Toutes les entites creees sont taggees `organization_id` et la recherche
    d'idempotence est scopee a cette org (isolation multi-tenant).
    """
    result = SyncResult()

    try:
        contacts = await client.get_contacts()
    except StartupRadarError as e:
        result.errors.append(f"Fetch contacts: {e}")
        return result

    for c in contacts:
        sr_id = str(c.get("id", ""))
        if not sr_id:
            continue

        try:
            async with db.begin_nested():
                stmt = select(Contact).where(
                    Contact.startup_radar_id == sr_id,
                    Contact.organization_id == organization_id,
                )
                existing = (await db.execute(stmt)).scalar_one_or_none()

                # Trouver la company CRM via startup_id du contact SR
                company_id = None
                startup_id = c.get("startup_id")
                if startup_id:
                    company_id = sr_to_crm.get(str(startup_id))

                if existing:
                    existing.first_name = c.get("first_name") or existing.first_name
                    existing.last_name = c.get("last_name") or existing.last_name
                    existing.email = c.get("email") or existing.email
                    existing.email_status = c.get("email_status") or existing.email_status
                    existing.title = c.get("title") or existing.title
                    existing.linkedin_url = c.get("linkedin_url") or existing.linkedin_url
                    existing.is_decision_maker = c.get("is_decision_maker", existing.is_decision_maker)
                    if company_id:
                        existing.company_id = company_id
                    # --- Enrichment fields (Phase B 2026-05) ---
                    # enrichment_source : ecrasable (toujours mettre la derniere source)
                    if c.get("enrichment_source"):
                        existing.enrichment_source = c["enrichment_source"][:50]
                    # email_pattern_used : conserve la premiere valeur (heuristique stable)
                    if c.get("email_pattern_used") and not existing.email_pattern_used:
                        existing.email_pattern_used = c["email_pattern_used"][:50]
                    # linkedin_url_status : ecrasable (verified > candidate > invalid)
                    if c.get("linkedin_url_status"):
                        existing.linkedin_url_status = c["linkedin_url_status"][:20]
                    result.contacts_updated += 1
                else:
                    contact = Contact(
                        id=uuid.uuid4(),
                        first_name=c.get("first_name", ""),
                        last_name=c.get("last_name", ""),
                        email=c.get("email"),
                        email_status=c.get("email_status"),
                        title=c.get("title"),
                        linkedin_url=c.get("linkedin_url"),
                        is_decision_maker=c.get("is_decision_maker", False),
                        source="startup_radar",
                        company_id=company_id,
                        startup_radar_id=sr_id,
                        owner_id=user.id,
                        organization_id=organization_id,
                        enrichment_source=(c.get("enrichment_source") or "")[:50] or None,
                        email_pattern_used=(c.get("email_pattern_used") or "")[:50] or None,
                        linkedin_url_status=(c.get("linkedin_url_status") or "")[:20] or None,
                    )
                    db.add(contact)
                    result.contacts_created += 1

        except Exception as e:
            result.errors.append(f"Contact {c.get('first_name', '')} {c.get('last_name', sr_id)}: {e}")

    await db.flush()
    logger.info(
        "[SRSync] Contacts: %d crees, %d mis a jour",
        result.contacts_created,
        result.contacts_updated,
    )
    return result
