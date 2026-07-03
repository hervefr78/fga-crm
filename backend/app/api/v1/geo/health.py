# =============================================================================
# FGA CRM - GEO Routes : Health
# =============================================================================
"""Endpoint de statut des moteurs GEO collectables."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from app.models.user import User
from app.schemas.geo import GeoHealthResponse

from ._common import _engine_configured, _require_geo_admin

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=list[GeoHealthResponse])
async def geo_health(
    _user: User = Depends(_require_geo_admin),
) -> list[GeoHealthResponse]:
    """Statut des moteurs GEO collectables (P1/P2).

    Pour chaque moteur supporte par le collecteur : si la cle API est absente ->
    'unconfigured' ; sinon on tente un appel de test minimal -> 'ok' / 'error'.
    """
    from app.services.geo.collector import get_collector

    checked_at = datetime.now(UTC)
    results: list[GeoHealthResponse] = []

    # On ne teste que les moteurs collectables (P1/P2)
    for engine in ("perplexity", "openai", "gemini"):
        if not _engine_configured(engine):
            results.append(
                GeoHealthResponse(
                    engine=engine, status="unconfigured", checked_at=checked_at
                )
            )
            continue
        try:
            collector = get_collector(engine)
            # Appel de test minimal (peu couteux)
            await collector.collect("ping", country="FR", language="fr")
            results.append(
                GeoHealthResponse(engine=engine, status="ok", checked_at=checked_at)
            )
        except Exception as exc:  # noqa: BLE001 — on rapporte l'erreur, pas de 500
            logger.warning("[GEO health] %s en erreur : %s", engine, exc)
            results.append(
                GeoHealthResponse(
                    engine=engine,
                    status="error",
                    checked_at=checked_at,
                    error=str(exc)[:300],
                )
            )

    return results
