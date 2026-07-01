# =============================================================================
# FGA CRM - Routes MCP Usage (dashboard conso API MCP)
# =============================================================================
"""Endpoints du dashboard de conso API MCP.

- POST /mcp-usage/ingest   — service-auth (write:mcp_usage). Le MCP pousse des
  evenements agreges ; on UPSERT en INCREMENTANT les sommes (2 ingests de la
  meme cle -> sommes cumulees).
- GET  /mcp-usage/summary  — JWT admin. Agregat par tool + total sur la periode.
- GET  /mcp-usage/by-tool  — JWT admin. Detail d'un tool par (jour, modele).

Le cout € est calcule A LA LECTURE via pricing.cost_eur (le tarif depend du
modele -> on agrege par (tool, modele) avant de sommer les couts).

UPSERT : SELECT-puis-update/insert unifie (portable PG/SQLite), calque sur
l'esprit de services/geo/scorer.py. On N'utilise PAS pg_insert ON CONFLICT ici
car la contrainte unique porte sur organization_id qui est NULL en Phase 1 :
en Postgres, NULL est traite comme distinct dans une UNIQUE, donc ON CONFLICT
ne matcherait jamais -> doublons silencieux. Le SELECT explicite (filtre IS NULL)
est correct pour les deux dialectes. Source d'ingest unique (le MCP, flush
sequentiel) -> pas de race condition concurrente en pratique (DC17).
"""

import contextlib
import logging
from datetime import UTC, date, datetime, timedelta

import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_admin, require_service_scope
from app.core.pricing import cost_eur
from app.db.session import get_db
from app.models.mcp_tool_usage import McpToolUsage
from app.models.user import User
from app.schemas.mcp_usage import (
    McpUsageByToolResponse,
    McpUsageByToolRow,
    McpUsageIngestRequest,
    McpUsageIngestResponse,
    McpUsageSummaryResponse,
    McpUsageTotal,
    ToolUsageSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Fenetre max autorisee sur les lectures (DC1 — borne l'input externe).
MAX_WINDOW_DAYS = 366


# ---------------------------------------------------------------------------
# Idempotence de l'ingest (dedup via Redis)
# ---------------------------------------------------------------------------
# Le flush MCP est at-least-once : si l'ingest reussit mais que la reponse se
# perd (timeout), le MCP retente le MEME batch (meme idempotency_key). On dedupe
# ici pour ne pas double-compter. Fail-open : Redis indispo -> on ingere sans
# dedup (degrade vers at-least-once, jamais de perte).
_IDEM_PREFIX = "mcp_ingest:"
_IDEM_TTL_SECONDS = 86400  # 24h — largement > la fenetre de retry du MCP

_redis_client: redis_async.Redis | None = None


def _get_redis() -> redis_async.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_async.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def _idem_acquire(key: str) -> bool:
    """True si le batch est nouveau (a traiter). False si deja ingere (doublon).

    SET NX EX atomique. Fail-open : sur erreur Redis, retourne True (on ingere
    sans dedup — best-effort).
    """
    try:
        acquired = await _get_redis().set(
            f"{_IDEM_PREFIX}{key}", "1", nx=True, ex=_IDEM_TTL_SECONDS,
        )
        return bool(acquired)
    except Exception as exc:
        logger.warning(
            "[MCP usage] dedup indisponible (%s) — ingest sans dedup", type(exc).__name__
        )
        return True


async def _idem_release(key: str) -> None:
    """Libere la cle (ex: echec d'application) pour autoriser un retry. Best-effort."""
    with contextlib.suppress(Exception):
        await _get_redis().delete(f"{_IDEM_PREFIX}{key}")

# Colonnes de sommes incrementees a l'upsert.
_SUM_COLUMNS = (
    "calls",
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
)


# ---------------------------------------------------------------------------
# Helpers dates (bornes DC1)
# ---------------------------------------------------------------------------

def _parse_iso_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        # Litteral 422 (aligne sur geo.py, source des helpers dates reutilises).
        raise HTTPException(
            status_code=422,
            detail=f"{field_name} doit etre une date ISO YYYY-MM-DD",
        )


def _resolve_window(date_from: str | None, date_to: str | None) -> tuple[date, date]:
    """Resoudre [date_from, date_to] : defaut 30 jours, bornes DC1.

    - format ISO valide
    - date_from <= date_to
    - fenetre <= MAX_WINDOW_DAYS
    """
    d_to = _parse_iso_date(date_to, "date_to") if date_to else datetime.now(UTC).date()
    d_from = (
        _parse_iso_date(date_from, "date_from")
        if date_from
        else d_to - timedelta(days=30)
    )
    if d_from > d_to:
        raise HTTPException(
            status_code=422,
            detail="date_from doit preceder ou egaler date_to",
        )
    if (d_to - d_from).days > MAX_WINDOW_DAYS:
        raise HTTPException(
            status_code=422,
            detail=f"fenetre trop large (max {MAX_WINDOW_DAYS} jours)",
        )
    return d_from, d_to


# ---------------------------------------------------------------------------
# Ingest (service-auth)
# ---------------------------------------------------------------------------

async def _upsert_event(
    db: AsyncSession,
    day: date,
    tool_name: str,
    model: str,
    calls: int,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
) -> None:
    """UPSERT incremental d'un evenement sur (organization_id, day, tool, model).

    organization_id reste None (multi-tenant futur). Sur conflit, les sommes
    sont INCREMENTEES (calls = existing.calls + nouveau, idem tokens).

    SELECT-puis-update/insert (portable PG/SQLite). Le filtre organization_id
    utilise IS NULL explicitement — indispensable car NULL = NULL est faux en SQL.
    """
    values = {
        "organization_id": None,
        "day": day,
        "tool_name": tool_name,
        "model": model,
        "calls": calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
    }

    existing = (
        await db.execute(
            select(McpToolUsage).where(
                and_(
                    McpToolUsage.organization_id.is_(None),
                    McpToolUsage.day == day,
                    McpToolUsage.tool_name == tool_name,
                    McpToolUsage.model == model,
                )
            )
        )
    ).scalar_one_or_none()

    if existing is not None:
        for col in _SUM_COLUMNS:
            setattr(existing, col, getattr(existing, col) + values[col])
    else:
        db.add(McpToolUsage(**values))


@router.post(
    "/ingest",
    response_model=McpUsageIngestResponse,
    dependencies=[Depends(require_service_scope("write:mcp_usage"))],
)
async def ingest_usage(
    payload: McpUsageIngestRequest,
    db: AsyncSession = Depends(get_db),
) -> McpUsageIngestResponse:
    """Ingerer un batch d'evenements d'usage (pousse par le MCP).

    Chaque evenement est upserte en incrementant les sommes. Avec une
    `idempotency_key`, un batch deja ingere est IGNORE (exactly-once malgre le
    retry at-least-once du MCP). Sans cle -> ancien comportement incremental.
    """
    key = payload.idempotency_key
    if key and not await _idem_acquire(key):
        logger.info("[MCP usage] ingest duplique ignore (key=%s)", key)
        return McpUsageIngestResponse(ingested=0)

    try:
        for event in payload.events:
            await _upsert_event(
                db,
                day=event.day,
                tool_name=event.tool_name,
                model=event.model,
                calls=event.calls,
                input_tokens=event.input_tokens,
                output_tokens=event.output_tokens,
                cache_read_tokens=event.cache_read_tokens,
                cache_write_tokens=event.cache_write_tokens,
            )
        await db.commit()
    except Exception:
        await db.rollback()
        # L'application a echoue : liberer la cle pour autoriser un retry (pas de
        # perte silencieuse — la cle ne doit pas "consommer" un batch non applique).
        if key:
            await _idem_release(key)
        raise

    logger.info("[MCP usage] ingest : %d evenements", len(payload.events))
    return McpUsageIngestResponse(ingested=len(payload.events))


# ---------------------------------------------------------------------------
# Summary (JWT admin)
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=McpUsageSummaryResponse)
async def usage_summary(
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> McpUsageSummaryResponse:
    """Agregat par tool + total sur la periode.

    Le cout depend du modele : on agrege d'abord par (tool, modele) pour
    appliquer le bon tarif, puis on somme par tool et au global.
    """
    d_from, d_to = _resolve_window(date_from, date_to)

    # SUM par (tool, modele) — necessaire pour un cout juste (tarif par modele).
    rows = (
        await db.execute(
            select(
                McpToolUsage.tool_name,
                McpToolUsage.model,
                func.sum(McpToolUsage.calls),
                func.sum(McpToolUsage.input_tokens),
                func.sum(McpToolUsage.output_tokens),
                func.sum(McpToolUsage.cache_read_tokens),
                func.sum(McpToolUsage.cache_write_tokens),
            )
            .where(and_(McpToolUsage.day >= d_from, McpToolUsage.day <= d_to))
            .group_by(McpToolUsage.tool_name, McpToolUsage.model)
        )
    ).all()

    # Agregation par tool (cout somme sur les modeles du tool).
    by_tool: dict[str, ToolUsageSummary] = {}
    total = McpUsageTotal(
        calls=0, tokens_in=0, tokens_out=0, cache_read=0, cache_write=0, cost_eur=0.0
    )

    for tool_name, model, calls, tok_in, tok_out, cache_r, cache_w in rows:
        calls = int(calls or 0)
        tok_in = int(tok_in or 0)
        tok_out = int(tok_out or 0)
        cache_r = int(cache_r or 0)
        cache_w = int(cache_w or 0)
        line_cost = cost_eur(model, tok_in, tok_out, cache_r, cache_w)

        entry = by_tool.get(tool_name)
        if entry is None:
            by_tool[tool_name] = ToolUsageSummary(
                tool_name=tool_name,
                calls=calls,
                input_tokens=tok_in,
                output_tokens=tok_out,
                cache_read_tokens=cache_r,
                cache_write_tokens=cache_w,
                cost_eur=line_cost,
            )
        else:
            entry.calls += calls
            entry.input_tokens += tok_in
            entry.output_tokens += tok_out
            entry.cache_read_tokens += cache_r
            entry.cache_write_tokens += cache_w
            entry.cost_eur += line_cost

        total.calls += calls
        total.tokens_in += tok_in
        total.tokens_out += tok_out
        total.cache_read += cache_r
        total.cache_write += cache_w
        total.cost_eur += line_cost

    # Arrondis (aligne sur une lecture monetaire lisible).
    total.cost_eur = round(total.cost_eur, 6)
    tools_sorted = sorted(by_tool.values(), key=lambda t: t.cost_eur, reverse=True)
    for tool in tools_sorted:
        tool.cost_eur = round(tool.cost_eur, 6)

    return McpUsageSummaryResponse(
        date_from=d_from,
        date_to=d_to,
        total=total,
        by_tool=tools_sorted,
    )


# ---------------------------------------------------------------------------
# By-tool (JWT admin)
# ---------------------------------------------------------------------------

@router.get("/by-tool", response_model=McpUsageByToolResponse)
async def usage_by_tool(
    tool: str = Query(..., min_length=1, max_length=100),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),
) -> McpUsageByToolResponse:
    """Detail d'un tool : lignes par (jour, modele) avec cout."""
    d_from, d_to = _resolve_window(date_from, date_to)

    rows = (
        await db.execute(
            select(
                McpToolUsage.day,
                McpToolUsage.model,
                func.sum(McpToolUsage.calls),
                func.sum(McpToolUsage.input_tokens),
                func.sum(McpToolUsage.output_tokens),
                func.sum(McpToolUsage.cache_read_tokens),
                func.sum(McpToolUsage.cache_write_tokens),
            )
            .where(
                and_(
                    McpToolUsage.tool_name == tool,
                    McpToolUsage.day >= d_from,
                    McpToolUsage.day <= d_to,
                )
            )
            .group_by(McpToolUsage.day, McpToolUsage.model)
            .order_by(McpToolUsage.day, McpToolUsage.model)
            .limit(MAX_WINDOW_DAYS * 10)
        )
    ).all()

    result_rows = [
        McpUsageByToolRow(
            day=day,
            model=model,
            calls=int(calls or 0),
            input_tokens=int(tok_in or 0),
            output_tokens=int(tok_out or 0),
            cache_read_tokens=int(cache_r or 0),
            cache_write_tokens=int(cache_w or 0),
            cost_eur=round(
                cost_eur(
                    model,
                    int(tok_in or 0),
                    int(tok_out or 0),
                    int(cache_r or 0),
                    int(cache_w or 0),
                ),
                6,
            ),
        )
        for day, model, calls, tok_in, tok_out, cache_r, cache_w in rows
    ]

    return McpUsageByToolResponse(
        tool_name=tool,
        date_from=d_from,
        date_to=d_to,
        rows=result_rows,
    )
