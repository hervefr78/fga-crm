# =============================================================================
# FGA CRM - Integrations API (Startup Radar sync + audit avance + Nomo-IA)
# =============================================================================
#
# Package agregateur : chaque integration independante vit dans son propre
# sous-module (nomo, plein_phare, startup_radar, startup_radar_audit) et expose
# son propre router. On les monte ici SANS prefixe additionnel — le prefixe
# /integrations est ajoute par app/api/v1/router.py. Les chemins d'URL restent
# strictement identiques a l'ancien module monolithique.

from fastapi import APIRouter

from . import nomo, plein_phare, startup_radar, startup_radar_audit

router = APIRouter()
router.include_router(nomo.router)
router.include_router(plein_phare.router)
router.include_router(startup_radar.router)
router.include_router(startup_radar_audit.router)
