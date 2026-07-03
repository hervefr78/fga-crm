# =============================================================================
# FGA CRM - GEO Routes : Alertes (P3) + Gaps et boucle d'optimisation (P4)
# =============================================================================
"""Endpoints de detection : alertes hebdomadaires et gaps de visibilite."""

import logging
import uuid
from collections import defaultdict
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.geo import GeoPrompt, GeoRun
from app.models.user import User
from app.schemas.geo import GeoEngine, GeoRunTriggerResponse

from ._common import (
    _engine_configured,
    _get_brand_or_404,
    _parse_uuid,
    _require_geo_access,
    _require_geo_admin,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# P3 — Alertes
# ---------------------------------------------------------------------------

@router.get("/brands/{brand_id}/alerts", response_model=list[dict])
async def brand_alerts(
    brand_id: str,
    engine: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> list[dict]:
    """Alertes GEO detectees sur la semaine ecoulee pour une marque."""
    from app.services.geo.alerts import detect_weekly_alerts

    bid = _parse_uuid(brand_id, "brand_id")
    await _get_brand_or_404(db, bid, user)

    if engine is not None and engine not in {e.value for e in GeoEngine}:
        raise HTTPException(status_code=422, detail="engine invalide")

    alerts = await detect_weekly_alerts(db, brand_id=bid, engine=engine or None)
    return [
        {
            "alert_type": a.alert_type,
            "engine": a.engine,
            "severity": a.severity,
            "message": a.message,
            "detail": a.detail,
            "detected_at": a.detected_at.isoformat(),
        }
        for a in alerts
    ]


# ---------------------------------------------------------------------------
# P4 — Gap detection et boucle d'optimisation
# ---------------------------------------------------------------------------

@router.get("/brands/{brand_id}/gaps", response_model=list[dict])
async def brand_gaps(
    brand_id: str,
    engine: str = Query(...),
    days: int = Query(default=7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_access),
) -> list[dict]:
    """Prompts ou la marque n'a pas ete mentionnee dans les N derniers jours.

    Pour chaque gap : le prompt, ses runs recents, les sources concurrentes citees.
    C'est l'input de la boucle d'optimisation P4 : detecter -> agir -> re-mesurer.
    """
    from datetime import timedelta

    bid = _parse_uuid(brand_id, "brand_id")
    await _get_brand_or_404(db, bid, user)

    if engine not in {e.value for e in GeoEngine}:
        raise HTTPException(422, detail="engine invalide")

    cutoff = datetime.now(UTC) - timedelta(days=days)

    # Tous les prompts actifs de la marque
    prompts = (await db.execute(
        select(GeoPrompt).where(
            and_(GeoPrompt.brand_id == bid, GeoPrompt.active.is_(True))
        ).limit(200)
    )).scalars().all()

    if not prompts:
        return []

    prompt_ids_list = [p.id for p in prompts]

    # Batch unique — 1 requete au lieu de N (evite le N+1)
    all_runs = (await db.execute(
        select(GeoRun).where(
            and_(
                GeoRun.prompt_id.in_(prompt_ids_list),
                GeoRun.engine == engine,
                GeoRun.run_at >= cutoff,
            )
        ).order_by(GeoRun.run_at.desc()).limit(2000)
    )).scalars().all()

    # Grouper par prompt_id (max 10 runs gardes par prompt)
    runs_by_prompt: dict[uuid.UUID, list] = defaultdict(list)
    for run in all_runs:
        if len(runs_by_prompt[run.prompt_id]) < 10:
            runs_by_prompt[run.prompt_id].append(run)

    gaps = []
    for prompt in prompts:
        recent_runs = runs_by_prompt.get(prompt.id, [])

        if not recent_runs:
            continue  # jamais teste sur ce moteur

        mention_count = sum(1 for r in recent_runs if r.brand_mentioned)
        total = len(recent_runs)

        if mention_count == 0:
            # Pas une seule mention -> gap total
            # Extraire les sources concurrentes des runs
            competitor_sources: dict[str, int] = {}
            competitor_brands: dict[str, int] = {}
            for run in recent_runs:
                for cit in (run.citations or []):
                    domain = cit.get("domain", "")
                    if domain:
                        competitor_sources[domain] = competitor_sources.get(domain, 0) + 1
                for brand_entry in (run.brands_found or []):
                    nom = brand_entry.get("nom", "")
                    if nom:
                        competitor_brands[nom] = competitor_brands.get(nom, 0) + 1

            top_sources = sorted(competitor_sources.items(), key=lambda x: -x[1])[:5]
            top_competitors = sorted(competitor_brands.items(), key=lambda x: -x[1])[:5]

            gaps.append({
                "prompt_id": str(prompt.id),
                "prompt_text": prompt.text,
                "intent": prompt.intent,
                "priority": prompt.priority,
                "runs_checked": total,
                "mentions": 0,
                "visibility_rate": 0.0,
                "top_competitor_sources": [
                    {"domain": d, "count": c} for d, c in top_sources
                ],
                "top_competitors": [
                    {"nom": n, "count": c} for n, c in top_competitors
                ],
                "last_run_at": (
                    recent_runs[0].run_at.isoformat() if recent_runs else None
                ),
                "action_suggestion": _suggest_action(prompt.intent, top_sources),
            })
        elif mention_count / total < 0.5:
            # Mention partielle -> gap partiel (opportunity)
            gaps.append({
                "prompt_id": str(prompt.id),
                "prompt_text": prompt.text,
                "intent": prompt.intent,
                "priority": prompt.priority,
                "runs_checked": total,
                "mentions": mention_count,
                "visibility_rate": round(mention_count / total * 100, 1),
                "top_competitor_sources": [],
                "top_competitors": [],
                "last_run_at": (
                    recent_runs[0].run_at.isoformat() if recent_runs else None
                ),
                "action_suggestion": _suggest_action(prompt.intent, []),
            })

    # Trier : prioritaires d'abord, puis visibilite croissante
    gaps.sort(key=lambda g: (not g["priority"], g["visibility_rate"]))
    return gaps


def _suggest_action(intent: str, top_sources: list[tuple]) -> str:
    """Suggestion d'action content basee sur l'intention et les sources dominantes.

    P4 — logique heuristique (pas d'appel LLM — rapide et deterministe).
    """
    source_names = [d for d, _ in top_sources]

    # Detecter la nature des sources dominantes
    has_reddit = any("reddit" in s for s in source_names)
    has_wiki = any("wikipedia" in s for s in source_names)
    has_comparator = any(
        s in ("g2.com", "capterra.com", "producthunt.com", "trustpilot.com")
        for s in source_names
    )

    if intent == "comparatif":
        if has_comparator:
            return "Creer/optimiser fiche G2, Capterra ou Product Hunt avec donnees chiffrees"
        return "Publier une comparaison structuree (Q&A, tableau) sur le site"

    if intent == "transactionnel":
        if has_reddit:
            return "Animer la presence Reddit/communaute : repondre aux threads pertinents"
        return "Creer une page FAQ dense avec donnees chiffrees et cas clients"

    # informationnel (defaut)
    if has_wiki:
        return "Renforcer les pages Wikipedia / Wikidata liees a la marque"
    return "Publier des contenus definitionnels (guides, glossaires, Q&A) avec schema.org FAQ"


@router.post("/brands/{brand_id}/gaps/remeasure", response_model=GeoRunTriggerResponse)
async def trigger_gap_remeasure(
    brand_id: str,
    engine: str = Query(...),
    days: int = Query(default=7, ge=1, le=90),
    n_runs: int = Query(default=3, ge=1, le=5),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(_require_geo_admin),
) -> GeoRunTriggerResponse:
    """Declencher un re-run sur TOUS les prompts en gap pour re-mesurer l'impact.

    C'est le bouton de cloture de la boucle P4 : detecter -> agir -> re-mesurer.
    """
    from datetime import timedelta

    bid = _parse_uuid(brand_id, "brand_id")
    await _get_brand_or_404(db, bid, user)

    if engine not in {e.value for e in GeoEngine}:
        raise HTTPException(422, "engine invalide")
    if not _engine_configured(engine):
        raise HTTPException(
            422, f"Moteur {engine} non configure (cle API manquante)"
        )

    cutoff = datetime.now(UTC) - timedelta(days=days)

    # Prompts avec 0 mention sur la periode — batch unique (evite N+1)
    prompts = (await db.execute(
        select(GeoPrompt).where(
            and_(GeoPrompt.brand_id == bid, GeoPrompt.active.is_(True))
        ).limit(200)
    )).scalars().all()

    # Prompts qui ont AU MOINS une mention sur la periode (pour exclusion)
    prompt_ids_all = [p.id for p in prompts]
    mentioned_prompt_ids_result = (await db.execute(
        select(GeoRun.prompt_id).where(
            and_(
                GeoRun.prompt_id.in_(prompt_ids_all),
                GeoRun.engine == engine,
                GeoRun.run_at >= cutoff,
                GeoRun.brand_mentioned.is_(True),
            )
        ).distinct()
    )).scalars().all()
    mentioned_set = set(mentioned_prompt_ids_result)

    # Gap = prompts qui ont eu des runs mais aucune mention
    has_runs_result = (await db.execute(
        select(GeoRun.prompt_id).where(
            and_(
                GeoRun.prompt_id.in_(prompt_ids_all),
                GeoRun.engine == engine,
                GeoRun.run_at >= cutoff,
            )
        ).distinct()
    )).scalars().all()
    has_runs_set = set(has_runs_result)

    # Cap a 50 pour eviter des batches excessifs
    gap_prompt_ids = [
        p.id for p in prompts
        if p.id in has_runs_set and p.id not in mentioned_set
    ][:50]

    if not gap_prompt_ids:
        raise HTTPException(404, "Aucun gap detecte — rien a re-mesurer")

    from app.tasks.geo import geo_run_batch_task
    async_result = geo_run_batch_task.delay(  # type: ignore[attr-defined]
        brand_id=str(bid),
        engine=engine,
        prompt_ids=[str(p) for p in gap_prompt_ids],
        n_runs=n_runs,
        country="FR",
        language="fr",
    )

    runs_scheduled = len(gap_prompt_ids) * n_runs
    logger.info(
        "[GEO P4] remeasure brand=%s engine=%s gaps=%d runs=%d task=%s",
        bid, engine, len(gap_prompt_ids), runs_scheduled, async_result.id,
    )

    return GeoRunTriggerResponse(
        task_id=str(async_result.id), runs_scheduled=runs_scheduled
    )
