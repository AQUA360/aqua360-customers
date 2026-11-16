import logging

from celery import shared_task

from .exceptions import OVApiError
from .sync import is_ov_sync_enabled, sync_virtual_office_contracts

logger = logging.getLogger(__name__)


@shared_task
def sync_virtual_office_contracts_task():
    if not is_ov_sync_enabled():
        return {"status": "skipped", "message": "Sincronització amb l'oficina virtual desactivada"}

    try:
        stats = sync_virtual_office_contracts()
    except OVApiError:
        logger.exception("Error sincronitzant els contractes amb l'oficina virtual")
        return {"status": "error", "message": "No s'ha pogut obtenir la llista de contractes de l'oficina virtual"}
    except Exception:
        logger.exception("Error sincronitzant els contractes amb l'oficina virtual")
        return {"status": "error", "message": "Error sincronitzant els contractes amb l'oficina virtual"}

    stats["not_found"] = len(stats.pop("not_found_tokens"))
    # Contractes que no s'han pogut desar: queden pendents per a la sincronització següent.
    return {"status": "partial" if stats["errors"] else "success", **stats}
