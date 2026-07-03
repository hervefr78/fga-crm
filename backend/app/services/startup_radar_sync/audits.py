# =============================================================================
# FGA CRM - Startup Radar Sync : Audits → Activities
# sync_audits (messaging + detaille + GEO → Activities type=audit)
# =============================================================================

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.user import User
from app.services.startup_radar import StartupRadarClient

from ._common import SyncResult

logger = logging.getLogger(__name__)


async def sync_audits(
    db: AsyncSession,
    client: StartupRadarClient,
    user: User,
    sr_to_crm: dict[str, uuid.UUID],
    startups: list[dict],
    organization_id: uuid.UUID,
) -> SyncResult:
    """Synchroniser les analyses/audits SR en Activities CRM (type=audit).

    startups : liste des startups SR (pour le nom + id).

    Toutes les Activities creees sont taggees `organization_id` et les recherches
    d'idempotence sont scopees a cette org (isolation multi-tenant).
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
                    # Verifier si deja importe (par subject unique, scopee org)
                    stmt = select(Activity).where(
                        Activity.company_id == company_id,
                        Activity.type == "audit",
                        Activity.subject == subject,
                        Activity.organization_id == organization_id,
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
                            organization_id=organization_id,
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
                        Activity.organization_id == organization_id,
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
                            organization_id=organization_id,
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
                        Activity.organization_id == organization_id,
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
                            organization_id=organization_id,
                        )
                        db.add(activity)
                        result.audits_created += 1

        except Exception as e:
            result.errors.append(f"GeoAudit {startup_name}: {e}")

    await db.flush()
    logger.info("[SRSync] Audits: %d crees", result.audits_created)
    return result
