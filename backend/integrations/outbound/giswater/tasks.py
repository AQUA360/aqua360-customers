from celery import shared_task
from django.conf import settings

from .services import fetch_connecs
from .sync import is_giswater_sync_enabled, sync_connections_from_giswater, sync_supply_cuts_from_giswater


@shared_task
def fetch_giswater_connecs_task():
    try:
        data = fetch_connecs()
        return {
            "status": "success",
            "message": "Connecs de Giswater obtingudes correctament",
            "data": data,
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Error obtenint connecs de Giswater: {exc}",
        }


@shared_task
def sync_giswater_connections_task():
    if not is_giswater_sync_enabled():
        return {
            "status": "skipped",
            "message": "Sincronització Giswater desactivada (GISWATER_SYNC_CONNECS_ENABLED=False)",
        }

    try:
        stats = sync_connections_from_giswater()
        return {
            "status": "success",
            "message": "Sincronització Giswater completada",
            **stats,
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Error sincronitzant connexions amb Giswater: {exc}",
        }

@shared_task
def sync_giswater_suply_cuts_task():
    # if not is_giswater_sync_enabled():
    #     return {
    #         "status": "skipped",
    #         "message": "Sincronització Giswater desactivada (GISWATER_SYNC_CONNECS_ENABLED=False)",
    #     }

    try:
        stats = sync_supply_cuts_from_giswater()
        return {
            "status": "success",
            "message": "Sincronització Giswater completada",
            **stats,
        }
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Error sincronitzant talls de subministrament amb Giswater: {exc}",
        }