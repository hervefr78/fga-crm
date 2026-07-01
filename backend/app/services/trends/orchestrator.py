# =============================================================================
# FGA CRM - Trends Orchestrateur
# =============================================================================
"""Execution d'un job Trends : collecte fournisseur -> normalisation -> scoring
-> persistance (snapshot + keywords + report).

Un seul chemin de code pour quick et deep (deep ajoute les related_topics).
Quick tourne inline (mock instantane) ; deep passe par Celery (voir tasks/trends.py).

Statut du job = colonne `status` de trend_jobs (pas de statut Redis global) :
supporte N jobs concurrents, chacun avec sa ligne. Redis ne sert qu'au cache de
payload normalise (skip fournisseur si requete identique recente).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.trends import TrendJob, TrendKeyword, TrendReport, TrendSnapshot
from app.services.trends import cache
from app.services.trends.provider import (
    QueryItem,
    RelatedQueries,
    get_trends_provider,
)

logger = logging.getLogger(__name__)

# Bornes d'affichage / persistance (DC1)
_TOP_QUERIES_KEEP = 12
_RISING_QUERIES_KEEP = 12
_TOPICS_KEEP = 8
_REGIONS_KEEP = 10
_MAX_KEYWORDS_PERSIST = 60
_TIMESERIES_RECENT_WINDOW = 4  # points recents pour l'indice d'interet

# Erreur stockee bornee (DC1)
_MAX_ERROR_LEN = 2000

# Ponderations de l'opportunity_score (somme = 1.0) — explicables, pas de modele opaque
_W_INTEREST = 0.40
_W_GROWTH = 0.30
_W_BREAKOUT = 0.20
_W_GEO = 0.10

# Seuil de variation pour qualifier la direction du marche
_DIRECTION_DELTA = 5.0


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Normalisation & scoring
# ---------------------------------------------------------------------------

def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _query_dict(q: QueryItem) -> dict:
    return {"query": q.query, "value": q.value, "growth": q.growth, "breakout": q.breakout}


def _market_pulse(timeseries: list[dict]) -> dict:
    """Indice d'interet recent + direction (up|down|flat)."""
    values = [p["value"] for p in timeseries]
    if not values:
        return {"interest_index": 0.0, "direction": "flat", "freshness": "fresh"}
    window = min(_TIMESERIES_RECENT_WINDOW, len(values))
    recent = _mean(values[-window:])
    previous = _mean(values[-2 * window : -window]) if len(values) >= 2 * window else recent
    delta = recent - previous
    if delta > _DIRECTION_DELTA:
        direction = "up"
    elif delta < -_DIRECTION_DELTA:
        direction = "down"
    else:
        direction = "flat"
    return {"interest_index": round(recent, 1), "direction": direction, "freshness": "fresh"}


def _opportunity_score(signals: dict) -> float:
    """Score composite 0-100, explicable (cf. doc 02). Pas de modele opaque."""
    interest = float(signals["market_pulse"]["interest_index"])  # 0-100

    rising = signals["rising_queries"]
    growths = [q["growth"] for q in rising if q.get("growth") is not None]
    # 1000%+ de croissance moyenne -> composante max (100)
    growth_component = min(100.0, _mean(growths) / 10.0) if growths else 0.0

    breakout_count = sum(1 for q in rising if q.get("breakout"))
    breakout_component = (breakout_count / len(rising) * 100.0) if rising else 0.0

    regions = signals["regions"]
    geo_component = float(regions[0]["value"]) if regions else 0.0

    score = (
        _W_INTEREST * interest
        + _W_GROWTH * growth_component
        + _W_BREAKOUT * breakout_component
        + _W_GEO * geo_component
    )
    return round(min(100.0, max(0.0, score)), 1)


def _build_summary(category_label: str, signals: dict, score: float) -> str:
    """Synthese markdown concise (enrichissement LLM = P4, apres normalisation)."""
    mp = signals["market_pulse"]
    rising = signals["rising_queries"]
    breakout = sum(1 for q in rising if q.get("breakout"))
    top_region = signals["regions"][0]["region"] if signals["regions"] else "—"

    lines = [
        f"# Tendances — {category_label}",
        "",
        f"**Score d'opportunite : {score}/100**",
        "",
        f"- Interet marche : {mp['interest_index']} ({mp['direction']})",
        f"- Requetes en hausse : {len(rising)} (dont {breakout} breakout)",
        f"- Region la plus active : {top_region}",
    ]
    if rising:
        lines += ["", "## Requetes en hausse"]
        for q in rising[:6]:
            g = f" (+{q['growth']:.0f}%)" if q.get("growth") is not None else ""
            tag = " [breakout]" if q.get("breakout") else ""
            lines.append(f"- {q['query']}{g}{tag}")
    top = signals["top_queries"]
    if top:
        lines += ["", "## Requetes dominantes"]
        for q in top[:6]:
            lines.append(f"- {q['query']}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Collecte fournisseur
# ---------------------------------------------------------------------------

async def _collect_signals(
    *, mode: str, category: str, country: str, language: str, timeframe: str,
    seed_terms: list[str],
) -> tuple[dict, str]:
    """Appelle le fournisseur, retourne (signals_normalises, provider_name)."""
    provider = get_trends_provider()
    kwargs = {
        "category": category, "country": country, "language": language,
        "timeframe": timeframe, "seed_terms": seed_terms or None,
    }

    timeseries = await provider.fetch_category_timeseries(**kwargs)
    rq: RelatedQueries = await provider.fetch_related_queries(**kwargs)
    regions = await provider.fetch_region_breakdown(**kwargs)
    topics = await provider.fetch_related_topics(**kwargs) if mode == "deep" else []

    ts = [{"date": p.date, "value": p.value} for p in timeseries]
    rising = sorted(
        (_query_dict(q) for q in rq.rising),
        key=lambda q: (q["growth"] or 0),
        reverse=True,
    )[:_RISING_QUERIES_KEEP]
    top = [_query_dict(q) for q in rq.top][:_TOP_QUERIES_KEEP]
    regions_d = [{"region": r.region, "value": r.value} for r in regions][:_REGIONS_KEEP]
    topics_d = [{"topic": t.topic, "value": t.value} for t in topics][:_TOPICS_KEEP]

    signals = {
        "market_pulse": _market_pulse(ts),
        "timeseries": ts,
        "rising_queries": rising,
        "top_queries": top,
        "related_topics": topics_d,
        "regions": regions_d,
    }
    return signals, provider.name


# ---------------------------------------------------------------------------
# Persistance
# ---------------------------------------------------------------------------

def _keyword_rows(snapshot_id, signals: dict) -> list[TrendKeyword]:
    """Deroule les keywords d'un snapshot (top/rising/topics) — borne (DC1)."""
    rows: list[TrendKeyword] = []
    for q in signals["top_queries"]:
        rows.append(TrendKeyword(
            snapshot_id=snapshot_id, keyword=q["query"], source_kind="top",
            interest_score=q["value"], growth_score=q.get("growth"),
            breakout=bool(q.get("breakout")),
        ))
    for q in signals["rising_queries"]:
        rows.append(TrendKeyword(
            snapshot_id=snapshot_id, keyword=q["query"], source_kind="rising",
            interest_score=q["value"], growth_score=q.get("growth"),
            breakout=bool(q.get("breakout")),
        ))
    for t in signals["related_topics"]:
        rows.append(TrendKeyword(
            snapshot_id=snapshot_id, keyword=t["topic"], source_kind="related",
            interest_score=t["value"],
        ))
    return rows[:_MAX_KEYWORDS_PERSIST]


async def _persist(
    db: AsyncSession, job: TrendJob, signals: dict, meta: dict, summary: str, score: float,
) -> None:
    """Enregistre snapshot + keywords + report dans la transaction courante."""
    # category_id : depuis les params (string JSONB -> UUID), None si categorie libre
    raw_cat_id = (job.params_json or {}).get("category_id")
    cat_id = uuid.UUID(raw_cat_id) if raw_cat_id else None
    snapshot = TrendSnapshot(
        job_id=job.id,
        category_id=cat_id,
        country=meta["country"],
        language=meta["language"],
        timeframe=meta["timeframe"],
        payload_json=signals,
    )
    db.add(snapshot)
    await db.flush()  # obtenir snapshot.id

    for kw in _keyword_rows(snapshot.id, signals):
        db.add(kw)

    report = TrendReport(
        job_id=job.id,
        summary_md=summary,
        insights_json={"signals": signals, "meta": meta},
        opportunity_score=score,
    )
    db.add(report)


# ---------------------------------------------------------------------------
# Point d'entree : execution d'un job
# ---------------------------------------------------------------------------

async def run_job(db: AsyncSession, job: TrendJob) -> None:
    """Execute un job : running -> collecte/normalisation/scoring/persist -> completed.

    Ne leve pas : en cas d'echec, le job passe a `failed` avec l'erreur bornee.
    """
    # Idempotence (DC5) : un job deja termine ne doit PAS etre re-execute. Un retry
    # Celery (redelivery apres crash worker, max_retries) rappellerait run_job sur un
    # job "completed" -> 2e insertion dans trend_reports (job_id unique) -> IntegrityError
    # -> un job REUSSI basculerait a tort en "failed". On skip donc les etats terminaux.
    if job.status in ("completed", "failed"):
        logger.info(
            "[Trends orchestrator] job %s deja en etat terminal (%s), skip (idempotence)",
            job.id, job.status,
        )
        return

    params = job.params_json or {}
    job.status = "running"
    job.started_at = _now()
    job.steps_total = 4
    job.steps_done = 0
    await db.commit()

    try:
        request_hash = params.get("request_hash", "")
        refresh = bool(params.get("refresh"))
        cached = None if refresh else await cache.get_cached_report(request_hash)

        if cached is not None:
            signals = cached["signals"]
            provider_name = cached["meta"]["provider_effective"]
            meta = dict(cached["meta"])
            meta["cached"] = True
            summary = cached["summary_md"]
            score = cached["opportunity_score"]
        else:
            signals, provider_name = await _collect_signals(
                mode=job.mode,
                category=params.get("category_slug", ""),
                country=params.get("country", settings.trends_default_country),
                language=params.get("language", settings.trends_default_language),
                timeframe=params.get("timeframe", "today 12-m"),
                seed_terms=params.get("seed_terms", []),
            )
            score = _opportunity_score(signals)
            summary = _build_summary(params.get("category_label", "categorie"), signals, score)
            meta = {
                "provider_effective": provider_name,
                "generated_at": _now().isoformat(),
                "cached": False,
                "category_slug": params.get("category_slug", ""),
                "country": params.get("country", settings.trends_default_country),
                "language": params.get("language", settings.trends_default_language),
                "timeframe": params.get("timeframe", "today 12-m"),
            }

        await _persist(db, job, signals, meta, summary, score)

        job.status = "completed"
        job.provider_effective = provider_name
        job.finished_at = _now()
        job.steps_done = job.steps_total
        await db.commit()

        # Cache best-effort (apres commit — n'impacte pas la transaction)
        if cached is None and request_hash:
            await cache.set_cached_report(
                request_hash,
                {"signals": signals, "meta": meta, "summary_md": summary,
                 "opportunity_score": score},
                settings.trends_cache_ttl_quick_seconds,
            )

    except Exception as exc:  # noqa: BLE001 — on convertit en statut failed (DC2)
        logger.exception("[Trends orchestrator] job %s echoue : %s", job.id, exc)
        await db.rollback()
        stale = await db.get(TrendJob, job.id)
        if stale is not None:
            stale.status = "failed"
            stale.error = str(exc)[:_MAX_ERROR_LEN]
            stale.finished_at = _now()
            await db.commit()
