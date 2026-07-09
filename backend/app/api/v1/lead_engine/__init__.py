# =============================================================================
# FGA CRM - API Lead Engine (agregation des sous-routers)
# =============================================================================
"""Module Lead Engine (docs/LEAD_ENGINE_VISION.md §3) — decoupe DC21 :

- signals.py         : GET /signals, PATCH /signals/{id}, POST /scan
- outreach_routes.py : POST /signals/{id}/draft, GET /queue, GET /funnel

RBAC : manager+ partout (comme GEO/Trends/Enrichissement).
"""

from fastapi import APIRouter

from app.api.v1.lead_engine.outreach_routes import router as outreach_router
from app.api.v1.lead_engine.signals import router as signals_router

router = APIRouter()
router.include_router(signals_router)
router.include_router(outreach_router)
