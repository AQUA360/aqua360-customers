from django.utils.translation import gettext as _

from coredata.models import ConfigProject


def get_sent_status_token():
    config = ConfigProject.objects.filter(token='payment_remittance_status_sent_token').first()
    return config.value if config else None


def is_remittance_sent(remittance, sent_status_token=None):
    """
    Una remesa enviada queda bloquejada: no es poden excloure pagaments,
    regenerar el fitxer, tornar-la a enviar, modificar-la ni esborrar-la.
    Es considera enviada si té data d'enviament o l'estat configurat com a enviat.
    """
    if remittance.sent_at:
        return True
    if sent_status_token is None:
        sent_status_token = get_sent_status_token()
    return bool(
        sent_status_token
        and remittance.status_id
        and remittance.status.token == sent_status_token
    )


def sent_remittance_error_message():
    return _("This remittance has already been sent and can no longer be modified.")
