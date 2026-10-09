from celery import shared_task

from integrations.outbound.signing.polling import poll_signing_sessions


@shared_task
def poll_signing_sessions_task():
    """
    Posa al dia les sessions de signatura obertes contra Aqua360 Sign.
    Vegeu `integrations/outbound/signing/polling.py` per què cal, a banda del webhook.
    """
    try:
        return poll_signing_sessions()
    except Exception as exc:
        return {
            "status": "error",
            "message": f"Error sondejant les sessions d'Aqua360 Sign: {exc}",
        }
