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
# Tasks actives :
# - sync_recent_funding : 09:00 quotidien (Europe/Paris)
#   Pull les startups SR creees/modifiees les 7 derniers jours et cree
#   les Activity 'funding_detected' + Task 'qualification' pour chaque levee.
#   Apres le pipeline SR 06:00 (ingest multi-source) + 08:30 (enrichissement).
# ---------------------------------------------------------------------------
app.conf.beat_schedule = {
    "sync-recent-funding-daily": {
        "task": "app.tasks.funding_sync.sync_recent_funding_task",
        "schedule": crontab(hour=9, minute=0),
        "args": (7,),  # days_back = 7
    },
}

# Decouverte automatique : autodiscover_tasks scanne pour `tasks.py` dans
# les packages listes (convention Celery). On a un layout different
# (chaque task = un module dans app.tasks/), donc on importe explicitement
# les modules pour declencher l'enregistrement des @app.task.
app.autodiscover_tasks(["app.tasks"])
from app.tasks import funding_sync  # noqa: E402, F401  — register task
