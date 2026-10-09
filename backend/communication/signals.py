import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from communication.tasks import generate_claim_document_pdf_task
from coredata.models import ConfigProject
from .models import Communication, CommunicationProcess, CommunicationProcessStatus, CommunicationStatus

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Communication)
def check_communication_process_completed(sender, instance, created, **kwargs):
    if created:
        return

    try:
        status_sent = CommunicationStatus.objects.get(
            token=ConfigProject.objects.get(token='communication_status_sent_token').value
        )
    except (CommunicationStatus.DoesNotExist, ConfigProject.DoesNotExist):
        return

    if instance.status != status_sent:
        return

    comm_process = instance.process
    if not comm_process:
        return

    if comm_process.communications.exclude(status=status_sent).exists():
        return

    try:
        status_completed = CommunicationProcessStatus.objects.get(
            token=ConfigProject.objects.get(token='communication_process_status_completed_token').value
        )
    except (CommunicationProcessStatus.DoesNotExist, ConfigProject.DoesNotExist):
        logger.warning("Could not find communication_process_status_completed_token config.")
        return

    comm_process.status = status_completed
    comm_process.save(update_fields=['status', 'updated_at'])