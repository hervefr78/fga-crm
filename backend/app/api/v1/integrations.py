# =============================================================================
# FGA CRM - Integrations API (Startup Radar sync + audit avance)
# =============================================================================

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.rbac import check_entity_access
from app.db.session import get_db
from app.models.activity import Activity
from app.models.company import Company
from app.models.user import User
from app.schemas.integration import (
    CompanyAuditResponse,
    SyncResultResponse,
    SyncStatusResponse,
)
from app.services.startup_radar import StartupRadarClient, StartupRadarError
from app.services.startup_radar_sync import full_sync, get_last_sync_result

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- POST /startup-radar/sync ----------


@router.post("/startup-radar/sync", response_model=SyncResultResponse, status_code=200)
async def sync_startup_radar(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lancer une synchronisation complete Startup Radar → CRM.

    Les entites creees appartiennent a l'utilisateur qui lance le sync.
    """
    try:
        result = await full_sync(db, current_user)
    except StartupRadarError as e:
        logger.error("[Integrations] Erreur sync SR: %s", e)
        raise HTTPException(status_code=503, detail=f"Erreur Startup Radar: {e}") from e

    return SyncResultResponse(
        companies_created=result.companies_created,
        companies_updated=result.companies_updated,
        contacts_created=result.contacts_created,
        contacts_updated=result.contacts_updated,
        investors_created=result.investors_created,
        investors_updated=result.investors_updated,
        audits_created=result.audits_created,
        errors=result.errors,
    )


# ---------- GET /startup-radar/status ----------


@router.get("/startup-radar/status", response_model=SyncStatusResponse)
async def get_sync_status(
    current_user: User = Depends(get_current_user),
):
    """Retourner le statut de la derniere synchronisation."""
    last = get_last_sync_result()

    if last is None:
        return SyncStatusResponse(has_synced=False, last_result=None)

    return SyncStatusResponse(
        has_synced=True,
        last_result=SyncResultResponse(
            companies_created=last.companies_created,
            companies_updated=last.companies_updated,
            contacts_created=last.contacts_created,
            contacts_updated=last.contacts_updated,
            investors_created=last.investors_created,
            investors_updated=last.investors_updated,
            audits_created=last.audits_created,
            errors=last.errors,
        ),
    )


# ---------- POST /startup-radar/audit/{company_id} ----------


@router.post(
    "/startup-radar/audit/{company_id}",
    response_model=CompanyAuditResponse,
    status_code=200,
)
async def trigger_company_audit(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lancer un audit avance Startup Radar pour une entreprise.

    Recupere l'audit detaille + l'analyse messaging depuis SR,
    les stocke en Activity(type=audit), et retourne le resultat.
    Idempotent : ne recree pas un audit qui existe deja.
    """
    # 1. Valider company_id
    try:
        cid = uuid.UUID(company_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="company_id invalide")

    # 2. Charger la company
    stmt = select(Company).where(Company.id == cid)
    company = (await db.execute(stmt)).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise non trouvee")

    # 3. Verifier startup_radar_id
    if not company.startup_radar_id:
        raise HTTPException(
            status_code=422,
            detail="Cette entreprise n'a pas de lien Startup Radar",
        )
    if company.startup_radar_id.startswith("inv:"):
        raise HTTPException(
            status_code=422,
            detail="Les audits ne sont pas disponibles pour les investisseurs",
        )

    # 4. RBAC
    check_entity_access(company, current_user)

    sr_id = company.startup_radar_id
    sr_client = StartupRadarClient()

    # 5. Auth SR
    try:
        await sr_client.authenticate()
    except StartupRadarError as e:
        logger.error("[Integrations] Erreur auth SR pour audit: %s", e)
        raise HTTPException(status_code=503, detail=f"Erreur auth Startup Radar: {e}") from e

    audits_created = 0
    audits_skipped = 0
    errors: list[str] = []

    # 6. Audit detaille
    try:
        audit = await sr_client.get_detailed_audit(sr_id)
        if audit and audit.get("status") == "completed" and audit.get("result"):
            subject = f"Audit detaille: {company.name}"
            existing = (
                await db.execute(
                    select(Activity).where(
                        Activity.company_id == company.id,
                        Activity.type == "audit",
                        Activity.subject == subject,
                    )
                )
            ).scalar_one_or_none()

            if existing:
                audits_skipped += 1
            else:
                audit_result = audit["result"]
                exec_summary = audit_result.get("executive_summary", {})
                metadata = {
                    "audit_type": "detailed",
                    "source": "startup_radar",
                    "total_score": exec_summary.get("total_score"),
                    "score_interpretation": exec_summary.get("score_interpretation"),
                    "key_findings": exec_summary.get("key_findings"),
                    "top_priority": exec_summary.get("top_priority"),
                    "scoring": audit_result.get("scoring", {}),
                    "gaps_count": exec_summary.get("gaps_count"),
                    "recommendations_count": exec_summary.get("recommendations_count"),
                }
                activity = Activity(
                    id=uuid.uuid4(),
                    type="audit",
                    subject=subject,
                    content=exec_summary.get("score_interpretation"),
                    metadata_=metadata,
                    company_id=company.id,
                    user_id=current_user.id,
                )
                db.add(activity)
                audits_created += 1
        elif audit and audit.get("status") != "completed":
            errors.append(f"Audit detaille en cours (status: {audit.get('status', 'unknown')})")
    except StartupRadarError as e:
        errors.append(f"Audit detaille: {e}")

    # 7. Analyse messaging
    try:
        analysis = await sr_client.get_analysis(sr_id)
        if analysis and analysis.get("positioning"):
            subject = f"Audit messaging: {company.name}"
            existing = (
                await db.execute(
                    select(Activity).where(
                        Activity.company_id == company.id,
                        Activity.type == "audit",
                        Activity.subject == subject,
                    )
                )
            ).scalar_one_or_none()

            if existing:
                audits_skipped += 1
            else:
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
                    company_id=company.id,
                    user_id=current_user.id,
                )
                db.add(activity)
                audits_created += 1
    except StartupRadarError as e:
        errors.append(f"Analyse messaging: {e}")

    # 8. Commit
    if audits_created > 0:
        try:
            await db.commit()
        except Exception as e:
            await db.rollback()
            errors.append(f"Commit: {e}")
            audits_created = 0

    logger.info(
        "[Integrations] Audit %s: %d crees, %d existants, %d erreurs",
        company.name, audits_created, audits_skipped, len(errors),
    )

    return CompanyAuditResponse(
        audits_created=audits_created,
        audits_skipped=audits_skipped,
        errors=errors,
    )
