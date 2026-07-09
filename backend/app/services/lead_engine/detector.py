# =============================================================================
# FGA CRM - Lead Engine : detecteur de signaux (scan periodique)
# =============================================================================
"""Scan des signaux Lead Engine (docs/LEAD_ENGINE_VISION.md §2, §4.2).

Regle metier (a ne jamais inverser) :
- ``mmf_gap`` (audit SR < seuil /75) = SEUL declencheur d'outreach (play P1) ;
- ``funding_detected`` (levee < fenetre) = qualificateur de solvabilite, ne
  declenche qu'un AUDIT du message (play P2).

Le detecteur CREE les signaux (dedupliques, org-scopes) — il ne lance aucune
action : en V1 l'action est humaine, depuis la Signal Inbox.

Garde-fous :
- dedup temporelle par ``dedup_key`` (fenetre ``lead_engine_dedup_days``),
  quel que soit le statut du signal precedent (un signal ignore est memorise) ;
- une societe avec un deal OUVERT (stage hors won/lost) n'est pas re-signalee
  (§2.4 : un lead deja en pipeline n'est pas re-cible).
"""

import logging
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.activity import Activity
from app.models.company import Company
from app.models.deal import Deal
from app.models.lead_engine import LeadSignal
from app.models.organization import Organization

logger = logging.getLogger(__name__)

# Stages de deal consideres fermes (une societe won/lost peut etre re-signalee)
CLOSED_DEAL_STAGES = ("won", "lost")


def _dedup_key(kind: str, company_id: uuid.UUID) -> str:
    return f"{kind}:{company_id}"


async def _recent_dedup_keys(db: AsyncSession, org_id: uuid.UUID) -> set[str]:
    """Cles de dedup deja emises dans la fenetre glissante (tous statuts)."""
    cutoff = datetime.now(UTC) - timedelta(days=settings.lead_engine_dedup_days)
    rows = await db.execute(
        select(LeadSignal.dedup_key).where(
            LeadSignal.organization_id == org_id,
            LeadSignal.created_at >= cutoff,
        )
    )
    return {r[0] for r in rows.all()}


async def _companies_with_open_deal(db: AsyncSession, org_id: uuid.UUID) -> set[uuid.UUID]:
    """Societes de l'org ayant au moins un deal ouvert (deja en pipeline)."""
    rows = await db.execute(
        select(Deal.company_id).distinct().where(
            Deal.organization_id == org_id,
            Deal.company_id.is_not(None),
            Deal.stage.not_in(CLOSED_DEAL_STAGES),
        )
    )
    return {r[0] for r in rows.all()}


def _company_payload(company: Company) -> dict:
    """Contexte commun du signal (le qualificateur solvabilite est toujours joint)."""
    return {
        "company_name": company.name,
        "startup_radar_id": company.startup_radar_id,
        "funding_date": company.funding_date.isoformat() if company.funding_date else None,
        "funding_amount": company.funding_amount,
        "funding_series": company.funding_series,
    }


async def _detect_funding(
    db: AsyncSession,
    org_id: uuid.UUID,
    known_keys: set[str],
    in_pipeline: set[uuid.UUID],
) -> int:
    """P2 — levee recente sur une societe auditable -> signal funding_detected.

    Ne cible que les societes liees a Startup Radar (hors investisseurs) :
    l'action du signal est l'audit du message, impossible sans lien SR.
    """
    window_start = date.today() - timedelta(days=settings.lead_engine_funding_window_days)
    rows = await db.execute(
        select(Company).where(
            Company.organization_id == org_id,
            Company.funding_date >= window_start,
            Company.startup_radar_id.is_not(None),
            ~Company.startup_radar_id.startswith("inv:"),
        )
    )
    created = 0
    for company in rows.scalars().all():
        key = _dedup_key("funding", company.id)
        if key in known_keys or company.id in in_pipeline:
            continue
        db.add(
            LeadSignal(
                organization_id=org_id,
                signal_type="funding_detected",
                company_id=company.id,
                payload_json=_company_payload(company),
                status="new",
                dedup_key=key,
            )
        )
        known_keys.add(key)
        created += 1
    return created


async def _detect_mmf_gap(
    db: AsyncSession,
    org_id: uuid.UUID,
    known_keys: set[str],
    in_pipeline: set[uuid.UUID],
) -> int:
    """P1 — audit du message < seuil -> signal mmf_gap (declencheur d'outreach)."""
    # Import tardif : reutilise la derivation des scores d'audit des routes
    # companies (DC8) sans creer d'import circulaire api <-> services.
    from app.api.v1.companies import _fetch_audit_flags

    # Societes de l'org ayant au moins une activite d'audit (le score /75 est
    # derive des activities type "audit" — pas une colonne Company).
    audited_ids = list(
        (
            await db.execute(
                select(Activity.company_id).distinct().where(
                    Activity.organization_id == org_id,
                    Activity.type == "audit",
                    Activity.company_id.is_not(None),
                )
            )
        ).scalars().all()
    )
    if not audited_ids:
        return 0

    _, score_map = await _fetch_audit_flags(db, audited_ids)
    gap_ids = [
        cid for cid, score in score_map.items()
        if score < settings.lead_engine_mmf_threshold
    ]
    if not gap_ids:
        return 0

    rows = await db.execute(select(Company).where(Company.id.in_(gap_ids)))
    created = 0
    for company in rows.scalars().all():
        key = _dedup_key("mmf", company.id)
        if key in known_keys or company.id in in_pipeline:
            continue
        payload = _company_payload(company)
        payload["audit_score"] = score_map.get(company.id)
        db.add(
            LeadSignal(
                organization_id=org_id,
                signal_type="mmf_gap",
                company_id=company.id,
                payload_json=payload,
                status="new",
                dedup_key=key,
            )
        )
        known_keys.add(key)
        created += 1
    return created


async def scan_org(db: AsyncSession, org_id: uuid.UUID) -> dict[str, int]:
    """Scanner une organisation et creer les signaux manquants (commit inclus)."""
    known_keys = await _recent_dedup_keys(db, org_id)
    in_pipeline = await _companies_with_open_deal(db, org_id)

    funding = await _detect_funding(db, org_id, known_keys, in_pipeline)
    mmf = await _detect_mmf_gap(db, org_id, known_keys, in_pipeline)
    await db.commit()

    if funding or mmf:
        logger.info(
            "[LeadEngine] Scan org %s : %d funding_detected, %d mmf_gap",
            org_id, funding, mmf,
        )
    return {"funding_detected": funding, "mmf_gap": mmf}


async def scan_all_orgs(db: AsyncSession) -> dict[str, int]:
    """Scanner toutes les organisations actives (beat horaire)."""
    org_ids = (
        await db.execute(select(Organization.id).where(Organization.is_active.is_(True)))
    ).scalars().all()

    totals = {"funding_detected": 0, "mmf_gap": 0, "orgs": len(org_ids)}
    for org_id in org_ids:
        try:
            result = await scan_org(db, org_id)
        except Exception:  # noqa: BLE001 — un org en echec ne bloque pas les autres
            logger.exception("[LeadEngine] Scan org %s en echec", org_id)
            await db.rollback()
            continue
        totals["funding_detected"] += result["funding_detected"]
        totals["mmf_gap"] += result["mmf_gap"]
    return totals
