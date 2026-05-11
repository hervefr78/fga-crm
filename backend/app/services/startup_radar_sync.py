# =============================================================================
# FGA CRM - Startup Radar Sync Orchestrator
# Synchronisation one-way SR → CRM (startups, contacts, investors, audits)
# =============================================================================

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.company import Company
from app.models.contact import Contact
from app.models.task import Task
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
    # Funding multi-source (Phase B 2026-05)
    funding_activities_created: int = 0
    qualification_tasks_created: int = 0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers funding (Phase B 2026-05)
# ---------------------------------------------------------------------------


def _parse_iso_date(value: str | None) -> date | None:
    """Convertir une chaine ISO YYYY-MM-DD en date, ou None si invalide.

    Tolere None et string vide (retour None sans erreur). Utilise pour les
    champs funding_date qui peuvent etre absents/mal formes dans la reponse SR.
    """
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _format_amount_subject(amount_eur: int, series: str | None) -> str:
    """Sujet stable pour Activity 'funding_detected' (cle d'idempotence).

    Inclut le montant en M€ et la serie pour permettre des rounds successifs
    sur la meme company (Seed → Serie A → Serie B = 3 activities distinctes).
    """
    amount_m = amount_eur / 1_000_000
    series_label = series or "Levée"
    return f"Levée détectée : {amount_m:.1f}M€ ({series_label})"


async def create_funding_activity(
    db: AsyncSession,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    startup_data: dict,
) -> bool:
    """Cree une Activity 'funding_detected' depuis les donnees SR. Idempotente.

    Idempotence : (company_id, type='funding_detected', subject) — le subject
    inclut le montant + la serie donc un nouveau round produit une nouvelle activity.

    Retourne True si activity creee, False si elle existait deja ou si pas de montant.
    """
    amount_eur = startup_data.get("amount", 0)
    if not amount_eur:
        return False

    series = startup_data.get("series") or "Levée"
    sources = startup_data.get("source_names") or ["startup_radar"]
    investors = startup_data.get("investors") or []

    subject = _format_amount_subject(amount_eur, series)

    # Flush pour rendre visible les inserts precedents de la session (l'autoflush
    # peut etre desactivee, ex: session de test). Indispensable pour l'idempotence
    # entre appels successifs au sein de la meme transaction.
    await db.flush()

    # Idempotence : verifier si l'activity existe deja
    stmt = select(Activity).where(
        Activity.company_id == company_id,
        Activity.type == "funding_detected",
        Activity.subject == subject,
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        return False

    amount_m = amount_eur / 1_000_000
    metadata = {
        "amount_eur": amount_eur,
        "series": series,
        "sources": sources,
        "investors": investors[:10],  # cap pour eviter blob enorme
        "funding_date": startup_data.get("funding_date"),
        "siren": startup_data.get("siren"),
    }

    content_lines = [
        f"Montant : {amount_m:.1f}M€",
        f"Série : {series}",
        f"Sources détectées : {', '.join(sources)}",
    ]
    if investors:
        content_lines.append(f"Investisseurs : {', '.join(investors[:5])}")

    activity = Activity(
        id=uuid.uuid4(),
        type="funding_detected",
        subject=subject,
        content="\n".join(content_lines),
        metadata_=metadata,
        company_id=company_id,
        user_id=user_id,
    )
    db.add(activity)
    # Flush pour que les appels suivants au sein de la meme transaction voient
    # cette activity et appliquent correctement l'idempotence (autoflush=False
    # sur session de test). En prod autoflush=True donc no-op effectif.
    await db.flush()
    return True


async def create_qualification_task(
    db: AsyncSession,
    company_id: uuid.UUID,
    assigned_to: uuid.UUID,
    startup_data: dict,
) -> bool:
    """Cree une Task 'qualification' pour qualifier la levee. Idempotente.

    Le seuil de filtrage est applique cote SR (pipeline funding_ingest) : si la
    startup arrive ici, c'est qu'elle est qualifying. CRM cree donc la task
    systematiquement quand amount > 0.

    Idempotence : (company_id, type='qualification', is_completed=False) —
    une seule task ouverte a la fois. Si l'ancienne est completee, une nouvelle
    peut etre creee (ex: nouveau round 6 mois plus tard).

    Retourne True si task creee, False sinon.
    """
    amount_eur = startup_data.get("amount", 0)
    if not amount_eur:
        return False

    # Flush pour rendre visible les inserts precedents (cf. create_funding_activity).
    await db.flush()

    # Idempotence : verifier qu'aucune task qualification ouverte n'existe deja
    stmt = select(Task).where(
        Task.company_id == company_id,
        Task.type == "qualification",
        Task.is_completed.is_(False),
    )
    if (await db.execute(stmt)).scalar_one_or_none():
        return False

    amount_m = amount_eur / 1_000_000
    startup_name = startup_data.get("name", "Startup")
    series = startup_data.get("series") or "Levée"
    title = f"Qualifier la levée : {startup_name} ({amount_m:.1f}M€ — {series})"

    # Echeance 7 jours (timezone-naive — DateTime(timezone=True) accepte naive en PG)
    due_date = datetime.utcnow() + timedelta(days=7)

    task = Task(
        id=uuid.uuid4(),
        title=title[:500],  # DC1 — respecter max_length
        type="qualification",
        priority="medium",
        due_date=due_date,
        company_id=company_id,
        assigned_to=assigned_to,
        is_completed=False,
    )
    db.add(task)
    await db.flush()  # cf. note dans create_funding_activity
    return True


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
            async with db.begin_nested():
                # 1. Chercher par startup_radar_id (idempotence principale)
                stmt = select(Company).where(Company.startup_radar_id == sr_id)
                existing = (await db.execute(stmt)).scalar_one_or_none()

                # 2. Fallback : chercher par nom (case-insensitive) si pas encore lie a SR
                #    Evite les doublons quand la company existe deja cree manuellement
                if not existing and s.get("name"):
                    stmt2 = select(Company).where(
                        func.lower(Company.name) == s["name"].lower(),
                        Company.startup_radar_id.is_(None),
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
                    if s.get("amount"):
                        # Conserver le montant le plus eleve (round le plus important)
                        if not existing.funding_amount or s["amount"] > existing.funding_amount:
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
                    if await create_funding_activity(db, company_id, user.id, s):
                        result.funding_activities_created += 1
                    if await create_qualification_task(db, company_id, user.id, s):
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
            async with db.begin_nested():
                # 1. Chercher par startup_radar_id
                stmt = select(Company).where(Company.startup_radar_id == sr_id)
                existing = (await db.execute(stmt)).scalar_one_or_none()

                # 2. Fallback nom case-insensitive (evite doublons si cree manuellement)
                if not existing and inv.get("name"):
                    stmt2 = select(Company).where(
                        func.lower(Company.name) == inv["name"].lower(),
                        Company.startup_radar_id.is_(None),
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
            async with db.begin_nested():
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
                subject = f"Audit messaging: {startup_name}"
                async with db.begin_nested():
                    # Verifier si deja importe (par subject unique)
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
                async with db.begin_nested():
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

                        # Stocker le rapport markdown complet dans content
                        full_report = audit_result.get("full_report", "")

                        # URLs de telechargement (MD/DOCX) — toujours disponibles si audit existe
                        try:
                            md_url, docx_url = client.get_detailed_audit_file_urls(sr_id)
                            metadata["file_md_url"] = md_url
                            metadata["file_docx_url"] = docx_url
                        except Exception as e:
                            logger.debug("Echec recuperation fichiers audit %s: %s", sr_id, e)

                        # Recuperer le lien de presentation commerciale
                        try:
                            pres = await client.get_presentation(sr_id)
                            if pres:
                                metadata["presentation_slug"] = pres.get("slug")
                                metadata["presentation_url"] = pres.get("public_url")
                                metadata["radar_axes"] = pres.get("radar_axes")
                        except Exception as e:
                            logger.debug("Echec recuperation presentation %s: %s", sr_id, e)

                        activity = Activity(
                            id=uuid.uuid4(),
                            type="audit",
                            subject=subject,
                            content=full_report or exec_summary.get("score_interpretation"),
                            metadata_=metadata,
                            company_id=company_id,
                            user_id=user.id,
                        )
                        db.add(activity)
                        result.audits_created += 1

        except Exception as e:
            result.errors.append(f"DetailedAudit {startup_name}: {e}")

        # --- Audit GEO ---
        try:
            geo = await client.get_geo_audit(sr_id)
            if geo and geo.get("status") == "completed" and geo.get("result"):
                subject = f"Audit GEO: {startup_name}"
                async with db.begin_nested():
                    stmt = select(Activity).where(
                        Activity.company_id == company_id,
                        Activity.type == "audit",
                        Activity.subject == subject,
                    )
                    existing = (await db.execute(stmt)).scalar_one_or_none()

                    if not existing:
                        geo_result = geo["result"]
                        metadata = {
                            "audit_type": "geo",
                            "source": "startup_radar",
                            "total_score": geo_result.get("total_score"),
                            "grade": geo_result.get("grade"),
                            "summary": geo_result.get("summary"),
                            "content_clarity": geo_result.get("content_clarity"),
                            "semantic_html": geo_result.get("semantic_html"),
                            "schema_org": geo_result.get("schema_org"),
                            "crawl_directives": geo_result.get("crawl_directives"),
                            "agent_comprehension": geo_result.get("agent_comprehension"),
                            "priority_actions": geo_result.get("priority_actions"),
                        }
                        # Rapport markdown complet dans content
                        full_report = geo_result.get("full_report", "")

                        activity = Activity(
                            id=uuid.uuid4(),
                            type="audit",
                            subject=subject,
                            content=full_report or geo_result.get("summary"),
                            metadata_=metadata,
                            company_id=company_id,
                            user_id=user.id,
                        )
                        db.add(activity)
                        result.audits_created += 1

        except Exception as e:
            result.errors.append(f"GeoAudit {startup_name}: {e}")

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
    total.funding_activities_created += partial.funding_activities_created
    total.qualification_tasks_created += partial.qualification_tasks_created
    total.errors.extend(partial.errors)


# ---------------------------------------------------------------------------
# Sync incrementale (Phase B 2026-05) — pull recent startups uniquement
# ---------------------------------------------------------------------------


async def sync_recent_startups(
    db: AsyncSession,
    user: User,
    days_back: int = 7,
) -> SyncResult:
    """Sync incrementale : pull uniquement les startups SR creees/modifiees recemment.

    Cible un cron quotidien CRM qui ramene les nouvelles levees detectees, sans
    refaire une full sync (couteux : 200+ requetes a SR).

    Necessite que GET /api/v1/startups cote SR accepte ?since=<ISO datetime>
    (cf. FUNDING_SYNC_INTEGRATION.md section 2.5).

    Args:
        days_back: fenetre de remontee en jours (defaut 7).

    Returns:
        SyncResult agrege (companies + contacts + funding activities + tasks).
    """
    result = SyncResult()
    sr_client = StartupRadarClient()

    # Auth (fallback anonyme si echec — l'API SR peut etre publique en lecture)
    try:
        await sr_client.authenticate()
    except StartupRadarError as e:
        logger.warning("[SRSync recent] Auth echec, mode anonyme: %s", e)

    since = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

    # 1. Fetch startups recentes
    try:
        # API SR : GET /startups?since=...&size=200 (cf. doc maitre 13.2)
        data = await sr_client._get(f"/startups?since={since}&size=200")
        # SR peut retourner soit {"items": [...]} (paginated) soit [...] (legacy)
        if isinstance(data, dict):
            items = data.get("items", [])
        elif isinstance(data, list):
            items = data
        else:
            items = []
    except StartupRadarError as e:
        result.errors.append(f"Fetch recent startups: {e}")
        _set_last_sync_result(result)
        return result
    except Exception as e:
        result.errors.append(f"Fetch recent startups: {e}")
        _set_last_sync_result(result)
        return result

    logger.info("[SRSync recent] %d startups depuis %s", len(items), since)

    # 2. Upsert chaque startup via la meme logique que sync_startups()
    #    On reuse sync_startups en lui passant un client qui retourne `items`.
    #    Comme sync_startups appelle client.get_startups(), on patche localement.
    class _PartialClient:
        """Mock partiel : fournit get_startups() qui retourne `items`,
        delegue le reste au vrai client (pour audits/contacts notamment)."""

        def __init__(self, real_client, startups):
            self._real = real_client
            self._startups = startups

        async def get_startups(self):
            return self._startups

        def __getattr__(self, name):
            return getattr(self._real, name)

    partial_client = _PartialClient(sr_client, items)
    startups_result, sr_to_crm = await sync_startups(db, partial_client, user)  # type: ignore[arg-type]
    _merge_results(result, startups_result)

    # 3. Sync contacts uniquement pour les startups touchees (eviter full pull)
    try:
        contacts = await sr_client.get_contacts()
    except StartupRadarError as e:
        result.errors.append(f"Fetch contacts: {e}")
        contacts = []

    relevant_contacts = [
        c for c in contacts
        if str(c.get("startup_id", "")) in sr_to_crm
    ]
    if relevant_contacts:
        # Reuse sync_contacts via partial client (memes contacts)
        class _ContactsClient:
            def __init__(self, real_client, contacts):
                self._real = real_client
                self._contacts = contacts

            async def get_contacts(self):
                return self._contacts

            def __getattr__(self, name):
                return getattr(self._real, name)

        contacts_client = _ContactsClient(sr_client, relevant_contacts)
        contacts_result = await sync_contacts(db, contacts_client, user, sr_to_crm)  # type: ignore[arg-type]
        _merge_results(result, contacts_result)

    # 4. Commit final
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        result.errors.append(f"Commit recent sync: {e}")

    _set_last_sync_result(result)

    logger.info(
        "[SRSync recent] Termine — Companies: +%d/~%d, Contacts: +%d/~%d, "
        "Funding activities: +%d, Tasks: +%d, Erreurs: %d",
        result.companies_created, result.companies_updated,
        result.contacts_created, result.contacts_updated,
        result.funding_activities_created, result.qualification_tasks_created,
        len(result.errors),
    )

    return result
