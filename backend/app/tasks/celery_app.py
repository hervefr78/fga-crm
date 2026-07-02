# =============================================================================
# FGA CRM - Celery Application
# =============================================================================

import os

from celery import Celery
from celery.schedules import crontab

# Broker et backend via Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

app = Celery(
    "fga_crm",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Paris",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# ---------------------------------------------------------------------------
# Beat Schedule — Tasks periodiques
# ---------------------------------------------------------------------------
# Format : { 'task_name': { 'task': 'app.tasks.module.task_name',
#                           'schedule': crontab(...) | timedelta(...),
#                           'args': (...) (optionnel) } }
#
# Timezone = Europe/Paris (cf. conf ci-dessus).
#
# ⚠ CRON DESACTIVE (2026-05-11) — voir TODO ci-dessous.
# La task `sync_recent_funding_task` consomme `GET /api/v1/startups?since=...`
# cote Startup Radar, mais ce filtre query param n'est pas encore implemente
# cote SR (ticket a ouvrir). Sans `?since=`, le cron ferait un full pull
# quotidien (cout reseau + latence).
#
# A REACTIVER quand :
#   1. cote SR : ajouter `since: datetime | None` dans GET /api/v1/startups
#      (filtre WHERE scraped_at >= since) — cf. doc maitre section 12
#   2. cote CRM : decommenter le bloc beat_schedule ci-dessous
#   3. redeployer le container fga-crm-beat (pas besoin de migration)
#
# La task reste enregistree dans le worker et peut etre declenchee
# manuellement via l'endpoint POST /integrations/startup-radar/sync-recent-funding
# ou via celery call (pour test ad-hoc).
# ---------------------------------------------------------------------------
# Le funding_sync reste DESACTIVE (cf. TODO ci-dessus, filtre `?since=` cote SR
# manquant). Il pourra etre rajoute ici quand le filtre SR sera disponible :
#     "sync-recent-funding-daily": {
#         "task": "app.tasks.funding_sync.sync_recent_funding_task",
#         "schedule": crontab(hour=9, minute=0),
#         "args": (7,),  # days_back = 7
#     },
app.conf.beat_schedule = {
    # Metriques GEO — calcul quotidien a 07:00 (apres les runs nocturnes)
    "geo-compute-metrics-daily": {
        "task": "app.tasks.geo.geo_compute_metrics_task",
        "schedule": crontab(hour=7, minute=0),
        "args": (),
    },
    # Enrichissement — filet de securite : finalise les bulks sans callback webhook
    # (timeout). Horaire ; le webhook (includeResults) reste le chemin nominal.
    "enrichment-reconcile-bulks-hourly": {
        "task": "app.tasks.enrichment.enrichment_reconcile_bulks_task",
        "schedule": crontab(minute=15),
        "args": (),
    },
}

# Decouverte automatique : autodiscover_tasks scanne pour `tasks.py` dans
# les packages listes (convention Celery). On a un layout different
# (chaque task = un module dans app.tasks/), donc on importe explicitement
# les modules pour declencher l'enregistrement des @app.task.
app.autodiscover_tasks(["app.tasks"])
from app.tasks import (  # noqa: E402, F401, I001  — register tasks
    enrichment,
    funding_sync,
    geo,
    startup_radar_full_sync,
    trends,
)
