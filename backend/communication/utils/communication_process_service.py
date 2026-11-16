from django.db.models import Exists, OuterRef

from communication.models import CANCELLED_STATUS_TOKEN, CommunicationProcess, CommunicationProcessStatus, CommunicationUseType
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token

def _has_active_process():
    """Exists: la lectura és en algun procés de comunicació no anul·lat."""
    cancelled_token = ConfigProject.objects.get(token='communication_process_status_cancelled_token').value
    return Exists(
        CommunicationProcess.objects.filter(readings=OuterRef('pk')).exclude(status__token=cancelled_token)
    )


def filter_readings_by_active_process(readings, active=True):
    """Filtra `readings` per si són (active=True) o no (active=False) en algun procés de comunicació no anul·lat. Una sola consulta."""
    condition = _has_active_process()
    return readings.filter(condition if active else ~condition)


def add_reading_to_communication_process(reading, user):
    print("add_reading_to_communication_process", reading)
    
    communication_process_status_draft_token = ConfigProject.objects.get(token='communication_process_status_draft_token').value
    use_type_reading_token = ConfigProject.objects.get(token='communication_use_type_reading').value
    
    
    existing_pending_process = CommunicationProcess.objects.filter(
        status__token=communication_process_status_draft_token,
        use_type__token=use_type_reading_token,
        readings__isnull=False,
        readings__supply_point__connection__exploitation=reading.supply_point.connection.exploitation
    )
    
    if existing_pending_process.exists():
        existing_process = existing_pending_process.first()
        if reading not in existing_process.readings.all():
            existing_process.readings.add(reading)
            existing_process.save()
    else:
        new_process = CommunicationProcess.objects.create(
            status=CommunicationProcessStatus.objects.get(token=communication_process_status_draft_token),
            use_type=CommunicationUseType.objects.get(token=use_type_reading_token),
            token=generate_token(CommunicationProcess),
            user=user,
        )
        new_process.readings.add(reading)
        new_process.save()
    
    return reading


def communications_finished(process):
    """Cap comunicació del procés queda per enviar: totes estan enviades o anul·lades,
    i n'hi ha almenys una d'enviada (si s'han anul·lat totes, el procés no s'ha finalitzat).
    """
    sent_token = ConfigProject.objects.get(token='communication_status_sent_token').value
    tokens = set(process.communications.values_list('status__token', flat=True))
    return sent_token in tokens and tokens <= {sent_token, CANCELLED_STATUS_TOKEN}


def finish_process_if_done(process):
    """Passa el procés a Finalitzat si ja no li queda cap comunicació per enviar.

    Retorna si el procés ha quedat finalitzat. Un procés anul·lat no es toca.
    """
    process.refresh_from_db(fields=['status'])
    if process.status and process.status.token == CANCELLED_STATUS_TOKEN:
        return False
    if not communications_finished(process):
        return False
    finalized = CommunicationProcessStatus.objects.get(
        token=ConfigProject.objects.get(token='communication_process_status_finalized_token').value
    )
    if process.status_id != finalized.id:
        process.status = finalized
        process.save(update_fields=['status', 'updated_at'])
    return True
