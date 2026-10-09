from communication.models import CommunicationProcess, CommunicationProcessStatus, CommunicationUseType
from coredata.models import ConfigProject
from coredata.utils.name_utils import generate_token

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