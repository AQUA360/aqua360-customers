"""Senyals dels avisos que no tenen un únic punt de negoci on cridar-los.

- contract_request.cancelled: una sol·licitud d'alta passa a l'estat anul·lat
  (`contract_request_cancel_token`). L'estat es canvia des de la pantalla, l'OV o
  altres serveis amb save(): el senyal els cobreix tots.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from contract.models import ContractRequest

from .dispatcher import webhooks_enabled
from .events import emit_contract_request_cancelled


@receiver(pre_save, sender=ContractRequest, dispatch_uid="webhooks_contract_request_pre_save")
def remember_contract_request_status(sender, instance, raw=False, **kwargs):
    if raw or not webhooks_enabled() or not instance.pk:
        return
    instance._webhook_previous_status_id = (
        ContractRequest.objects.filter(pk=instance.pk).values_list("status_id", flat=True).first()
    )


@receiver(post_save, sender=ContractRequest, dispatch_uid="webhooks_contract_request_post_save")
def contract_request_cancelled(sender, instance, created, raw=False, **kwargs):
    if raw or created or not webhooks_enabled():
        return
    previous_status_id = getattr(instance, "_webhook_previous_status_id", None)
    instance._webhook_previous_status_id = instance.status_id
    if instance.status_id is None or instance.status_id == previous_status_id:
        return
    emit_contract_request_cancelled(instance)
