# =============================================================================
# FGA CRM - Startup Radar Sync : orchestrateurs
# full_sync (complete) + sync_recent_startups (incrementale Phase B)
# =============================================================================

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.startup_radar import StartupRadarClient, StartupRadarError

from ._common import SyncResult, _merge_results
from .audits import sync_audits
from .people import sync_contacts, sync_investors
from .startups import sync_startups

logger = logging.getLogger(__name__)


# Le statut de la full sync est stocke dans Redis (cf. services/sync_status.py),
# pas dans un global memoire : la prod a plusieurs workers uvicorn + un process
# Celery, un global ne serait visible que dans le process qui l'ecrit.
# full_sync() / sync_recent_startups() restent du calcul pur : elles retournent
# un SyncResult, l'orchestration (task Celery + endpoint) enregistre le statut.


# ---------------------------------------------------------------------------
# Full Sync — Orchestrateur principal
# ---------------------------------------------------------------------------


async def full_sync(
    db: AsyncSession,
    user: User,
    organization_id: uuid.UUID,
) -> SyncResult:
    """Synchronisation complete SR → CRM.

    Ordre : startups → investors → contacts → audits.

    organization_id : org a laquelle rattacher toutes les entites creees (tag +
    scope idempotence). Fournie par l'appelant (task Celery) qui la resout depuis
    le user declencheur.
    """
    sr_client = StartupRadarClient()
    total = SyncResult()

    # 1. Authentification — erreur fatale : on remonte pour que la task marque
    # le job 'failed' (et non 'completed' avec 0 element, qui serait trompeur).
    try:
        await sr_client.authenticate()
    except StartupRadarError:
        logger.error("[SRSync] Authentification SR echouee — sync annulee")
        raise

    # 2. Sync startups → Companies
    startups_result, sr_to_crm = await sync_startups(db, sr_client, user, organization_id)
    _merge_results(total, startups_result)

    # 3. Sync investors → Companies (industry=Capital-risque)
    investors_result = await sync_investors(db, sr_client, user, organization_id)
    _merge_results(total, investors_result)

    # 4. Sync contacts → Contacts (avec mapping company)
    contacts_result = await sync_contacts(db, sr_client, user, sr_to_crm, organization_id)
    _merge_results(total, contacts_result)

    # 5. Sync audits → Activities
    # Recuperer les startups pour les noms
    try:
        startups = await sr_client.get_startups()
    except StartupRadarError as e:
        total.errors.append(f"Re-fetch startups pour audits: {e}")
        startups = []

    audits_result = await sync_audits(db, sr_client, user, sr_to_crm, startups, organization_id)
    _merge_results(total, audits_result)

    # 6. Commit final
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        total.errors.append(f"Commit final: {e}")

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
    # Isolation multi-tenant : toutes les entites creees sont rattachees a l'org
    # du user declencheur (humain). Scope aussi les recherches d'idempotence.
    organization_id = user.organization_id

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
        return result
    except Exception as e:
        result.errors.append(f"Fetch recent startups: {e}")
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
    startups_result, sr_to_crm = await sync_startups(db, partial_client, user, organization_id)  # type: ignore[arg-type]
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
        contacts_result = await sync_contacts(db, contacts_client, user, sr_to_crm, organization_id)  # type: ignore[arg-type]
        _merge_results(result, contacts_result)

    # 4. Commit final
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        result.errors.append(f"Commit recent sync: {e}")

    logger.info(
        "[SRSync recent] Termine — Companies: +%d/~%d, Contacts: +%d/~%d, "
        "Funding activities: +%d, Tasks: +%d, Erreurs: %d",
        result.companies_created, result.companies_updated,
        result.contacts_created, result.contacts_updated,
        result.funding_activities_created, result.qualification_tasks_created,
        len(result.errors),
    )

    return result
