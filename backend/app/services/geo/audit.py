# =============================================================================
# FGA CRM - GEO Audit-visibility (mesure a la demande pour Startup Radar)
# =============================================================================
"""Orchestration d'une mesure de visibilite GEO a la demande.

SR envoie {company_name, domain, aliases, prompts}. On cree une marque EPHEMERE
(is_owned=false -> invisible du dashboard), on lance 1 run Perplexity par prompt,
puis on AGREGE le resultat (visible, taux, concurrents, resume).

Reutilise le pipeline GEO existant (execute_geo_batch : collect -> extract ->
match). Le seul code neuf : marque/prompts ephemeres + agregation + tracking job.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.geo import GeoAuditJob, GeoBrand, GeoPrompt, GeoRun
from app.services.geo.pipeline import execute_geo_batch

logger = logging.getLogger(__name__)

_AUDIT_ENGINE = "perplexity"
_TOP_COMPETITORS = 8
_MAX_ERROR_LEN = 2000


def _now() -> datetime:
    return datetime.now(UTC)


def _slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:40] or "marque"


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def compute_request_hash(
    *, domain: str, engine: str, prompts: list[str], country: str, language: str
) -> str:
    """Empreinte deterministe pour la deduplication (l'ordre des prompts compte peu :
    on trie pour dedupliquer les memes 3 prompts saisis dans un autre ordre)."""
    canonical = json.dumps(
        {
            "domain": domain.lower().strip(),
            "engine": engine,
            "prompts": sorted(p.strip() for p in prompts),
            "country": country,
            "language": language,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Agregation du resultat depuis les GeoRun
# ---------------------------------------------------------------------------

def _aggregate(
    runs: list[GeoRun], *, audited_names: set[str], prompt_text_by_id: dict, n_expected: int
) -> dict:
    runs_completed = len(runs)
    mentioned = [r for r in runs if r.brand_mentioned]
    mentions = len(mentioned)
    visible = mentions > 0

    positions = [r.brand_position for r in mentioned if r.brand_position is not None]
    best_position = min(positions) if positions else None
    recommended = any(bool(r.brand_recommended) for r in runs)

    # Sentiment : celui de la mention la mieux placee.
    sentiment = None
    if mentioned:
        best = min(mentioned, key=lambda r: (r.brand_position or 999))
        sentiment = best.brand_sentiment

    # Concurrents : marques citees HORS la marque auditee, comptees.
    comp_counts: dict[str, int] = {}
    for r in runs:
        for entry in (r.brands_found or []):
            nom = (entry.get("nom") or "").strip()
            if not nom:
                continue
            n = _norm(nom)
            if not n or n in audited_names:
                continue
            comp_counts[nom] = comp_counts.get(nom, 0) + 1
    competitors = sorted(
        ({"name": k, "mentions": v} for k, v in comp_counts.items()),
        key=lambda c: c["mentions"],
        reverse=True,
    )[:_TOP_COMPETITORS]

    # Detail par prompt (1 run par prompt : n_runs=1).
    per_prompt = []
    for r in runs:
        per_prompt.append({
            "prompt": prompt_text_by_id.get(r.prompt_id, ""),
            "mentioned": bool(r.brand_mentioned),
            "position": r.brand_position,
        })

    visibility_rate = round(mentions / runs_completed * 100, 1) if runs_completed else 0.0
    return {
        "visible": visible,
        "runs_total": n_expected,
        "runs_completed": runs_completed,
        "mentions": mentions,
        "visibility_rate": visibility_rate,
        "best_position": best_position,
        "recommended": recommended,
        "sentiment": sentiment,
        "competitors_found": competitors,
        "per_prompt": per_prompt,
    }


def _build_summary(company: str, result: dict) -> str:
    m, total = result["mentions"], result["runs_completed"]
    comps = ", ".join(c["name"] for c in result["competitors_found"][:3]) or "aucun concurrent identifie"
    if not result["visible"]:
        return (
            f"{m}/{total} — {company} n'apparait dans aucune reponse Perplexity ; "
            f"acteurs cites a la place : {comps}."
        )
    pos = result["best_position"]
    pos_txt = f" (meilleure position : {pos})" if pos else ""
    return (
        f"{m}/{total} — {company} apparait dans {result['visibility_rate']}% des reponses"
        f"{pos_txt} ; autres acteurs cites : {comps}."
    )


# ---------------------------------------------------------------------------
# Execution du job
# ---------------------------------------------------------------------------

async def run_audit_job(db: AsyncSession, job: GeoAuditJob) -> None:
    """Execute un job d'audit-visibilite : marque ephemere -> run -> agregation.

    Ne leve pas : en cas d'echec, le job passe a `failed` avec l'erreur bornee.
    Idempotent (DC5) : un job en etat terminal est ignore (retry Celery).
    """
    if job.status in ("completed", "failed"):
        logger.info("[GEO audit] job %s deja terminal (%s), skip", job.id, job.status)
        return

    params = job.params_json or {}
    prompts_text: list[str] = params.get("prompts", [])
    aliases: list[str] = params.get("aliases", [])
    country: str = params.get("country", "FR")
    language: str = params.get("language", "fr")

    job.status = "running"
    await db.commit()

    try:
        # 1. Marque ephemere (is_owned=false -> invisible du dashboard). Slug unique
        #    par job (evite toute collision, y compris sur refresh).
        brand = GeoBrand(
            slug=f"audit-{_slugify(job.domain)}-{str(job.id)[:8]}",
            name=job.company_name,
            aliases=aliases,
            is_owned=False,
            active=True,
            organization_id=job.organization_id,
        )
        db.add(brand)
        await db.flush()

        # 2. Prompts ephemeres (heritent de l'org du job/marque)
        prompt_ids: list[uuid.UUID] = []
        for text in prompts_text:
            p = GeoPrompt(brand_id=brand.id, text=text, intent="informationnel",
                          country=country, language=language,
                          organization_id=job.organization_id)
            db.add(p)
            await db.flush()
            prompt_ids.append(p.id)
        job.brand_id = brand.id
        await db.commit()

        # 3. Run Perplexity (n_runs=1) — reutilise le pipeline GEO
        await execute_geo_batch(
            db, brand_id=brand.id, engine=_AUDIT_ENGINE, prompt_ids=prompt_ids,
            n_runs=1, country=country, language=language,
        )

        # 4. Agregation depuis les runs de cette marque
        runs = (
            await db.execute(select(GeoRun).where(GeoRun.brand_id == brand.id))
        ).scalars().all()
        if not runs:
            raise RuntimeError("aucun run abouti (collecte/extraction en echec)")

        prompt_text_by_id = dict(zip(prompt_ids, prompts_text, strict=False))
        audited_names = {_norm(job.company_name)} | {_norm(a) for a in aliases if a}
        result = _aggregate(
            runs, audited_names=audited_names,
            prompt_text_by_id=prompt_text_by_id, n_expected=len(prompt_ids),
        )
        result["summary"] = _build_summary(job.company_name, result)

        job.result_json = result
        job.status = "completed"
        job.finished_at = _now()
        await db.commit()

    except Exception as exc:  # noqa: BLE001 — converti en statut failed (DC2)
        logger.exception("[GEO audit] job %s echoue : %s", job.id, exc)
        await db.rollback()
        stale = await db.get(GeoAuditJob, job.id)
        if stale is not None:
            stale.status = "failed"
            stale.error = str(exc)[:_MAX_ERROR_LEN]
            stale.finished_at = _now()
            await db.commit()
