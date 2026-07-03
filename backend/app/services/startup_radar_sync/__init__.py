# =============================================================================
# FGA CRM - Startup Radar Sync Orchestrator (package)
# Synchronisation one-way SR → CRM (startups, contacts, investors, audits)
#
# Ce package re-exporte tous les noms publics historiquement importes depuis
# `app.services.startup_radar_sync` afin que les importeurs externes
# (tasks Celery, endpoints, tests) continuent de resoudre a l'identique :
#   from app.services.startup_radar_sync import sync_recent_startups, full_sync, ...
# =============================================================================

from ._common import (
    SyncResult,
    _format_amount_subject,
    _merge_results,
    _parse_iso_date,
)
from .activities import create_funding_activity, create_qualification_task
from .audits import sync_audits
from .people import sync_contacts, sync_investors
from .runner import full_sync, sync_recent_startups
from .startups import sync_startups

__all__ = [
    "SyncResult",
    "_parse_iso_date",
    "_format_amount_subject",
    "_merge_results",
    "create_funding_activity",
    "create_qualification_task",
    "sync_startups",
    "sync_investors",
    "sync_contacts",
    "sync_audits",
    "full_sync",
    "sync_recent_startups",
]
