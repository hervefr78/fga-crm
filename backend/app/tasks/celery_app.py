# =============================================================================
# FGA CRM - Celery Application
# =============================================================================

import os

from celery import Celery

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

# Decouverte automatique des taches dans app.tasks
app.autodiscover_tasks(["app.tasks"])
