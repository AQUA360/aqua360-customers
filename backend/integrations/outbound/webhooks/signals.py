"""Senyals dels avisos que no tenen un únic punt de negoci on cridar-los.

- contract_request.cancelled: una sol·licitud d'alta passa a l'estat anul·lat
  (`contract_request_cancel_token`). L'estat es canvia des de la pantalla, l'OV o
  altres serveis amb save(): el senyal els cobreix tots.
"""
import logging

from django.db import DatabaseError, transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from contract.models import ContractRequest

from .dispatcher import webhooks_enabled
from .events import emit_contract_request_cancelled

logger = logging.getLogger(__name__)


def _saves_status(update_fields):
    return update_fields is None or bool({"status", "status_id"} & set(update_fields))


@receiver(pre_save, sender=ContractRequest, dispatch_uid="webhooks_contract_request_pre_save")
def remember_contract_request_status(sender, instance, raw=False, update_fields=None, **kwargs):
    if raw or not webhooks_enabled() or not instance.pk or not _saves_status(update_fields):
        return
    instance._webhook_previous_status_id = (
        ContractRequest.objects.filter(pk=instance.pk).values_list("status_id", flat=True).first()
    )


@receiver(post_save, sender=ContractRequest, dispatch_uid="webhooks_contract_request_post_save")
def contract_request_cancelled(sender, instance, created, raw=False, update_fields=None, **kwargs):
    # Una desada parcial que no escriu l'estat no l'ha canviat a la base de dades
    if raw or created or not webhooks_enabled() or not _saves_status(update_fields):
        return
    previous_status_id = getattr(instance, "_webhook_previous_status_id", None)
    instance._webhook_previous_status_id = instance.status_id
    if instance.status_id is None or instance.status_id == previous_status_id:
        return
    # Mai fer fallar la desada de la sol·licitud: dins un savepoint i només al log
    try:
        with transaction.atomic():
            emit_contract_request_cancelled(instance)
    except DatabaseError:
        logger.exception("No s'ha pogut desar l'avís de sol·licitud anul·lada")
