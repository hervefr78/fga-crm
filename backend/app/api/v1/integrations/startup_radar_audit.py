# =============================================================================
# FGA CRM - Integrations API : Startup Radar (audit avance + generation)
# =============================================================================

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_manager
from app.core.rbac import check_entity_access, check_tenant_access
from app.db.session import get_db
from app.models.activity import Activity
from app.models.company import Company
from app.models.user import User
from app.schemas.integration import (
    AuditGenerateResponse,
    AuditGenerateStatusResponse,
    CompanyAuditResponse,
)
from app.services.startup_radar import (
    StartupRadarClient,
    StartupRadarConflict,
    StartupRadarError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------- POST /startup-radar/audit/{company_id} ----------


@router.post(
    "/startup-radar/audit/{company_id}",
    response_model=CompanyAuditResponse,
    status_code=200,
)
async def trigger_company_audit(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_manager),
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

    # 3. RBAC AVANT toute validation metier (isolation tenant -> ownership) : ne pas
    #    divulguer l'etat/existence d'une company cross-org via les 422 metier.
    check_tenant_access(company, current_user)
    check_entity_access(company, current_user)

    # 4. Verifier startup_radar_id
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
            async with db.begin_nested():
                existing = (
                    await db.execute(
                        select(Activity).where(
                            Activity.company_id == company.id,
                            Activity.type == "audit",
                            Activity.subject == subject,
                            Activity.organization_id == company.organization_id,
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
                        # Herite de l'org de la company parente (source de verite)
                        organization_id=company.organization_id,
                    )
                    db.add(activity)
                    audits_created += 1
        elif audit and audit.get("status") != "completed":
            errors.append(f"Audit detaille en cours (status: {audit.get('status', 'unknown')})")
    except StartupRadarError as e:
        errors.append(f"Audit detaille: {e}")
    except Exception as e:
        errors.append(f"Audit detaille DB: {e}")

    # 7. Analyse messaging
    try:
        analysis = await sr_client.get_analysis(sr_id)
        if analysis and analysis.get("positioning"):
            subject = f"Audit messaging: {company.name}"
            async with db.begin_nested():
                existing = (
                    await db.execute(
                        select(Activity).where(
                            Activity.company_id == company.id,
                            Activity.type == "audit",
                            Activity.subject == subject,
                            Activity.organization_id == company.organization_id,
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
                        # Herite de l'org de la company parente (source de verite)
                        organization_id=company.organization_id,
                    )
                    db.add(activity)
                    audits_created += 1
    except StartupRadarError as e:
        errors.append(f"Analyse messaging: {e}")
    except Exception as e:
        errors.append(f"Analyse messaging DB: {e}")

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


# ---------- Generation d'audit a la demande (trigger SR + polling) ----------


async def _resolve_sr_company(db: AsyncSession, company_id: str, user: User) -> Company:
    """Charge une company auditable SR + valide (sr_id, pas investisseur, RBAC).

    Partage par les endpoints generate / generate-status (DC8). Leve HTTPException
    en cas d'invalidite.
    """
    try:
        cid = uuid.UUID(company_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="company_id invalide") from None

    company = (
        await db.execute(select(Company).where(Company.id == cid))
    ).scalar_one_or_none()
    if not company:
        raise HTTPException(status_code=404, detail="Entreprise non trouvee")
    # RBAC AVANT validation metier (ne pas divulguer l'etat d'une company cross-org).
    check_tenant_access(company, user)
    check_entity_access(company, user)
    if not company.startup_radar_id:
        raise HTTPException(
            status_code=422, detail="Cette entreprise n'a pas de lien Startup Radar",
        )
    if company.startup_radar_id.startswith("inv:"):
        raise HTTPException(
            status_code=422,
            detail="Les audits ne sont pas disponibles pour les investisseurs",
        )
    return company


@router.post(
    "/startup-radar/audit/{company_id}/generate",
    response_model=AuditGenerateResponse,
    status_code=202,
)
async def generate_company_audit(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_manager),
):
    """Declencher la GENERATION d'un audit SR (detaille + GEO + presentation).

    Reserve manager+. SR calcule l'audit en arriere-plan (pipeline LLM, plusieurs
    minutes). Le frontend poll GET .../generate-status jusqu'a completed, puis
    importe le resultat via POST .../audit/{company_id}.
    """
    company = await _resolve_sr_company(db, company_id, current_user)

    sr_client = StartupRadarClient()
    try:
        await sr_client.authenticate()
    except StartupRadarError as e:
        logger.error("[Integrations] Auth SR (generate audit): %s", e)
        raise HTTPException(
            status_code=503, detail=f"Erreur auth Startup Radar: {e}",
        ) from e

    try:
        result = await sr_client.launch_diagnostic_audit(company.startup_radar_id)
    except StartupRadarConflict:
        raise HTTPException(
            status_code=409,
            detail="Un audit est deja en cours pour cette entreprise.",
        ) from None
    except StartupRadarError as e:
        logger.error("[Integrations] Generate audit SR: %s", e)
        raise HTTPException(
            status_code=503, detail=f"Erreur Startup Radar: {e}",
        ) from e

    return AuditGenerateResponse(
        status="running",
        message=result.get("message", "Audit lance"),
    )


@router.get(
    "/startup-radar/audit/{company_id}/generate-status",
    response_model=AuditGenerateStatusResponse,
)
async def get_company_audit_generate_status(
    company_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_manager),
):
    """Statut de generation d'un audit SR (proxy du statut SR).

    `idle` si aucun audit en cours, sinon running / completed / failed.
    """
    company = await _resolve_sr_company(db, company_id, current_user)

    sr_client = StartupRadarClient()
    try:
        await sr_client.authenticate()
        st = await sr_client.get_diagnostic_status(company.startup_radar_id)
    except StartupRadarError as e:
        logger.error("[Integrations] Statut generation audit SR: %s", e)
        raise HTTPException(
            status_code=503, detail=f"Erreur Startup Radar: {e}",
        ) from e

    if st is None:
        return AuditGenerateStatusResponse(status="idle")

    return AuditGenerateStatusResponse(
        status=st.get("status", "idle"),
        step=st.get("step", ""),
        error=st.get("error"),
    )
