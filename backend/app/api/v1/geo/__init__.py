# =============================================================================
# FGA CRM - GEO Routes (Generative Engine Optimization)
# =============================================================================
"""Package du module GEO.

RBAC :
- Lecture (brands, prompts, runs, dashboard, competitors) : admin + manager
- Ecriture (create/update/delete, trigger, health) : admin uniquement

Le module GEO est cloisonne : les sales n'y ont pas acces du tout.

Ce package agrege les sous-routers thematiques (brands, prompts, runs,
dashboard, gaps, health) sans prefixe additionnel : les chemins declares
dans chaque module sont les chemins finaux (montes sous /geo par router.py).
"""

from fastapi import APIRouter

from . import brands, dashboard, gaps, health, prompts, runs

router = APIRouter()

# Ordre preservant la declaration d'origine (brands en premier : overview
# avant {brand_id} est garanti dans brands.py).
router.include_router(brands.router)
router.include_router(prompts.router)
router.include_router(runs.router)
router.include_router(dashboard.router)
router.include_router(health.router)
router.include_router(gaps.router)
