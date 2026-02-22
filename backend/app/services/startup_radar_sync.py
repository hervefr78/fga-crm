# =============================================================================
# FGA CRM - Startup Radar Sync Orchestrator
# Synchronisation one-way SR → CRM (startups, contacts, investors, audits)
# =============================================================================

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.user import User
from app.services.startup_radar import StartupRadarClient, StartupRadarError

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Resultat d'une synchronisation SR → CRM."""

    companies_created: int = 0
    companies_updated: int = 0
    contacts_created: int = 0
    contacts_updated: int = 0
    investors_created: int = 0
    investors_updated: int = 0
    audits_created: int = 0
    errors: list[str] = field(default_factory=list)


# Stockage en memoire du dernier resultat de sync
_last_sync_result: SyncResult | None = None


def get_last_sync_result() -> SyncResult | None:
    """Retourne le dernier resultat de sync."""
    return _last_sync_result


def _set_last_sync_result(result: SyncResult) -> None:
    """Met a jour le dernier resultat de sync."""
    global _last_sync_result
    _last_sync_result = result


# ---------------------------------------------------------------------------
# Sync Startups → Companies
# ---------------------------------------------------------------------------


async def sync_startups(
    db: AsyncSession,
    client: StartupRadarClient,
    user: User,
) -> tuple[SyncResult, dict[str, uuid.UUID]]:
    """Synchroniser les startups SR en Companies CRM.

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
            # Chercher si la company existe deja via startup_radar_id
            stmt = select(Company).where(Company.startup_radar_id == sr_id)
            existing = (await db.execute(stmt)).scalar_one_or_none()

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
                # Merger les custom_fields existants avec les nouveaux
                merged = {**(existing.custom_fields or {}), **custom}
                existing.custom_fields = merged
                sr_to_crm[sr_id] = existing.id
                result.companies_updated += 1
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
                    owner_id=user.id,
                )
                db.add(company)
                sr_to_crm[sr_id] = company_id
                result.companies_created += 1

        except Exception as e:
            result.errors.append(f"Startup {s.get('name', sr_id)}: {e}")

    await db.flush()
    logger.info(
        "[SRSync] Startups: %d creees, %d mises a jour",
        result.companies_created,
        result.companies_updated,
    )
    return result, sr_to_crm


# ---------------------------------------------------------------------------
# Sync Investors → Companies
# ---------------------------------------------------------------------------


async def sync_investors(
    db: AsyncSession,
    client: StartupRadarClient,
    user: User,
) -> SyncResult:
    """Synchroniser les investisseurs SR en Companies CRM (industry=Capital-risque)."""
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
            stmt = select(Company).where(Company.startup_radar_id == sr_id)
            existing = (await db.execute(stmt)).scalar_one_or_none()

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
                    owner_id=user.id,
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


# ---------------------------------------------------------------------------
# Sync Contacts → Contacts
# ---------------------------------------------------------------------------


async def sync_contacts(
    db: AsyncSession,
    client: StartupRadarClient,
    user: User,
    sr_to_crm: dict[str, uuid.UUID],
) -> SyncResult:
    """Synchroniser les contacts SR en Contacts CRM.

    sr_to_crm : mapping startup_radar_id → company_id CRM (pour lier contact → company).
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
            stmt = select(Contact).where(Contact.startup_radar_id == sr_id)
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


# ---------------------------------------------------------------------------
# Sync Audits → Activities
# ---------------------------------------------------------------------------


async def sync_audits(
    db: AsyncSession,
    client: StartupRadarClient,
    user: User,
    sr_to_crm: dict[str, uuid.UUID],
    startups: list[dict],
) -> SyncResult:
    """Synchroniser les analyses/audits SR en Activities CRM (type=audit).

    startups : liste des startups SR (pour le nom + id).
    """
    result = SyncResult()

    for s in startups:
        sr_id = str(s.get("id", ""))
        company_id = sr_to_crm.get(sr_id)
        if not company_id:
            continue

        startup_name = s.get("name", "Startup")

        # --- Analyse messaging ---
        try:
            analysis = await client.get_analysis(sr_id)
            if analysis and analysis.get("positioning"):
                # Verifier si deja importe (par subject unique)
                subject = f"Audit messaging: {startup_name}"
                stmt = select(Activity).where(
                    Activity.company_id == company_id,
                    Activity.type == "audit",
                    Activity.subject == subject,
                )
                existing = (await db.execute(stmt)).scalar_one_or_none()

                if not existing:
                    metadata = {
                        "audit_type": "messaging",
                        "source": "startup_radar",
                        "positioning": analysis.get("positioning"),
                        "value_proposition": analysis.get("value_proposition"),
                        "messaging_score": analysis.get("messaging_score"),
                        "differentiators": analysis.get("differentiators"),
                        "target_audience": analysis.get("target_audience"),
                        "strengths": analysis.get("strengths"),
                        "weaknesses": analysis.get("weaknesses"),
                        "recommendations": analysis.get("recommendations"),
                    }
                    activity = Activity(
                        id=uuid.uuid4(),
                        type="audit",
                        subject=subject,
                        content=analysis.get("value_proposition"),
                        metadata_=metadata,
                        company_id=company_id,
                        user_id=user.id,
                    )
                    db.add(activity)
                    result.audits_created += 1

        except Exception as e:
            result.errors.append(f"Analysis {startup_name}: {e}")

        # --- Audit detaille ---
        try:
            audit = await client.get_detailed_audit(sr_id)
            if audit and audit.get("status") == "completed" and audit.get("result"):
                subject = f"Audit detaille: {startup_name}"
                stmt = select(Activity).where(
                    Activity.company_id == company_id,
                    Activity.type == "audit",
                    Activity.subject == subject,
                )
                existing = (await db.execute(stmt)).scalar_one_or_none()

                if not existing:
                    audit_result = audit["result"]
                    exec_summary = audit_result.get("executive_summary", {})
                    scoring = audit_result.get("scoring", {})

                    metadata = {
                        "audit_type": "detailed",
                        "source": "startup_radar",
                        "total_score": exec_summary.get("total_score"),
                        "score_interpretation": exec_summary.get("score_interpretation"),
                        "key_findings": exec_summary.get("key_findings"),
                        "top_priority": exec_summary.get("top_priority"),
                        "scoring": scoring,
                        "gaps_count": exec_summary.get("gaps_count"),
                        "recommendations_count": exec_summary.get("recommendations_count"),
                    }
                    activity = Activity(
                        id=uuid.uuid4(),
                        type="audit",
                        subject=subject,
                        content=exec_summary.get("score_interpretation"),
                        metadata_=metadata,
                        company_id=company_id,
                        user_id=user.id,
                    )
                    db.add(activity)
                    result.audits_created += 1

        except Exception as e:
            result.errors.append(f"DetailedAudit {startup_name}: {e}")

    await db.flush()
    logger.info("[SRSync] Audits: %d crees", result.audits_created)
    return result


# ---------------------------------------------------------------------------
# Full Sync — Orchestrateur principal
# ---------------------------------------------------------------------------


async def full_sync(db: AsyncSession, user: User) -> SyncResult:
    """Synchronisation complete SR → CRM.

    Ordre : startups → investors → contacts → audits.
    """
    sr_client = StartupRadarClient()
    total = SyncResult()

    # 1. Authentification
    try:
        await sr_client.authenticate()
    except StartupRadarError as e:
        total.errors.append(f"Authentification: {e}")
        _set_last_sync_result(total)
        return total

    # 2. Sync startups → Companies
    startups_result, sr_to_crm = await sync_startups(db, sr_client, user)
    _merge_results(total, startups_result)

    # 3. Sync investors → Companies (industry=Capital-risque)
    investors_result = await sync_investors(db, sr_client, user)
    _merge_results(total, investors_result)

    # 4. Sync contacts → Contacts (avec mapping company)
    contacts_result = await sync_contacts(db, sr_client, user, sr_to_crm)
    _merge_results(total, contacts_result)

    # 5. Sync audits → Activities
    # Recuperer les startups pour les noms
    try:
        startups = await sr_client.get_startups()
    except StartupRadarError as e:
        total.errors.append(f"Re-fetch startups pour audits: {e}")
        startups = []

    audits_result = await sync_audits(db, sr_client, user, sr_to_crm, startups)
    _merge_results(total, audits_result)

    # 6. Commit final
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        total.errors.append(f"Commit final: {e}")

    _set_last_sync_result(total)

    logger.info(
        "[SRSync] Sync terminee — Companies: +%d/~%d, Contacts: +%d/~%d, "
        "Investors: +%d/~%d, Audits: +%d, Erreurs: %d",
        total.companies_created, total.companies_updated,
        total.contacts_created, total.contacts_updated,
        total.investors_created, total.investors_updated,
        total.audits_created,
        len(total.errors),
    )

    return total


def _merge_results(total: SyncResult, partial: SyncResult) -> None:
    """Fusionner un resultat partiel dans le total."""
    total.companies_created += partial.companies_created
    total.companies_updated += partial.companies_updated
    total.contacts_created += partial.contacts_created
    total.contacts_updated += partial.contacts_updated
    total.investors_created += partial.investors_created
    total.investors_updated += partial.investors_updated
    total.audits_created += partial.audits_created
    total.errors.extend(partial.errors)
