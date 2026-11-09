import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from communication.tasks import generate_claim_document_pdf_task
from coredata.models import ConfigProject
from communication.utils.communication_process_service import finish_process_if_done
from .models import CANCELLED_STATUS_TOKEN, Communication, CommunicationProcessStatus

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Communication)
def check_communication_process_completed(sender, instance, created, **kwargs):
    if created or not instance.process_id:
        return

    try:
        sent_token = ConfigProject.objects.get(token='communication_status_sent_token').value
    except ConfigProject.DoesNotExist:
        return

    # També en anul·lar-ne una: si la resta ja estan enviades, el procés s'ha acabat
    if not instance.status or instance.status.token not in (sent_token, CANCELLED_STATUS_TOKEN):
        return

    try:
        finish_process_if_done(instance.process)
    except (CommunicationProcessStatus.DoesNotExist, ConfigProject.DoesNotExist):
        logger.warning("Could not find communication_process_status_finalized_token config.")
