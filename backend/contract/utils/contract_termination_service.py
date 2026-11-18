import datetime
from billing.models import Reading
from coredata.models import ConfigProject
from django.template.loader import render_to_string
from io import BytesIO
from xhtml2pdf import pisa
from django.http import JsonResponse
from django.core.files.base import ContentFile
from coredata.serializers import AddressSerializer, PersonCardSerializer
from documentmanager.utils.sign_certificate_service import sign_pdf
from service.models import Exploitation
from service.utils.exploitation_logo import exploitation_logo_source
from django.conf import settings
from django.core.files.storage import default_storage
import uuid
import threading

from service.serializers.company_serializer import CompanySerializer

def getTerminationDocument(instance, request=None):
    print("getTerminationDocument")
    
    base_url = ''
    if request:
        base_url = request.build_absolute_uri('/').rstrip('/')
    else:
        domain_media = settings.DOMAIN_MEDIA if hasattr(settings, 'DOMAIN_MEDIA') else ''
        base_url = domain_media
    
    context = {'request': request, 'base_url': base_url}
    city = None
    try:
        exploitation = instance.contract.supply_point_default.connection.exploitation
    except:
        exploitation = None
    
    if not exploitation:
        try:
            exploitation = Exploitation.objects.first()
        except:
            exploitation = None
    
    if not exploitation:
        return JsonResponse({"error": "Exploitation not found"}, status=500)
    
    # Build signed image URL
    # signed_image_path = f"/media/uploads/logo/{exploitation.company.id}/signed.jpg"
    # signed_image = base_url + signed_image_path if base_url else signed_image_path
    # xhtml2pdf works better with http than https
    # signed_image = signed_image.replace('https', 'http')
    
    domain_media = settings.DOMAIN_MEDIA if hasattr(settings, 'DOMAIN_MEDIA') else ''
    signed_image = f"{domain_media}/media/uploads/logo/{exploitation.company.id}/signed.jpg"
    
    if (instance.contract.supply_point_default is not None and
        instance.contract.supply_point_default.address is not None and
        instance.contract.supply_point_default.address.city is not None):
      city = instance.contract.supply_point_default.address.city.name
    
    today = datetime.datetime.now()
    
    company = CompanySerializer(exploitation.company,context=context).data
    logo = company['logo']
    if logo and not logo.startswith('http'):
        logo = base_url + logo
        logo = logo.replace('https', 'http')
    holder = PersonCardSerializer(instance.contract.holder, context=context).data if instance.contract.holder else None
    person = PersonCardSerializer(instance.person, context=context).data if instance.person else None
    supply_address = AddressSerializer(instance.contract.supply_point_default.address).data if instance.contract.supply_point_default.address else None
    # Variable pròpia i no `exploitation_image`: algunes plantilles personalitzades
    # ja la fan servir i no han de canviar.
    exploitation_logo = exploitation_logo_source(exploitation)
    main_color = '#000000'
    try:
        main_color = ConfigProject.objects.get(token='invoice_main_color').value
    except:
        pass
    
    last_readings = []
    if instance.readings.count() > 0:
        last_readings = instance.readings.all()
    else:
        try:
            for supply_point in instance.contract.supply_points.all():
                meter = supply_point.meter
                if meter:
                    last_reading = Reading.objects.filter(meter=meter, supply_point=supply_point, is_control=False, contract=instance.contract).order_by('-reading_date').first()
                    if last_reading:
                        last_readings.append(last_reading)
        except:
            pass
        
    html_content = render_to_string('contract_termination_template.html', {
      'main_color': main_color, 'company': company, 'request': instance,
      'city': city, 'holder': holder, 'person': person, 'logo': logo, 'signed_image': signed_image,
      'exploitation_logo': exploitation_logo,
      'last_readings': last_readings, 'supply_address': supply_address, 'today': today
      })
    pdf_buffer = BytesIO()
    
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
    if pisa_status.err:
        return JsonResponse({"error": "PDF generation failed"}, status=500)
    
    signed_pdf_buffer = sign_pdf(pdf_buffer, company, 'CONTRACTE', 'CONTRACTE')
    
    pdf_filename = f"{instance.contract.token}_BAIXA.pdf"
    
    if request:
        unique_filename = f"temp_{pdf_filename}"
        temp_path = f"temp_termination_docs/{unique_filename.replace('/', '_')}"
        
        if default_storage.exists(temp_path):
            default_storage.delete(temp_path)
        
        saved_path = default_storage.save(temp_path, ContentFile(signed_pdf_buffer.getvalue()))
        
        file_url = request.build_absolute_uri(default_storage.url(temp_path))
        
        def _delete_later(path: str, delay_seconds: int = 100) -> None:
            def _run():
                try:
                    default_storage.delete(path)
                except Exception:
                    pass
            t = threading.Timer(delay_seconds, _run)
            t.daemon = True
            t.start()

        _delete_later(saved_path, delay_seconds=20)
        return file_url
    else:
        return signed_pdf_buffer.getvalue()


def mark_contract_terminated(contract, termination_request, termination_date=None):
    """Posa el contracte de baixa. És l'únic lloc on es fa, per a tots els camins de
    baixa (tancar la sol·licitud, completar-ne les ordres, canvi de titular...).

    Data de baixa: si el contracte passa a baixa ara, la que es passi o, si no, la
    que tingui o la d'avui; un contracte de baixa sempre en té. Si ja era de baixa,
    es conserva la que té (és la que s'ha notificat) i només s'omple si no en tenia.
    Només quan el contracte passa realment a baixa s'avisa el sistema extern
    (webhook), dins la mateixa transacció que el desa. Torna True si ha passat a
    baixa ara.
    """
    from django.db import transaction
    from contract.models import Contract, ContractStatus
    from integrations.outbound.webhooks.events import emit_contract_termination_confirmed

    terminated_token = ConfigProject.objects.get(token='contract_terminated_status').value
    with transaction.atomic():
        # Bloqueja la fila: dos camins de baixa alhora no avisen dues vegades
        locked = Contract.objects.select_for_update(of=("self",)).select_related("status").get(pk=contract.pk)
        was_terminated = bool(locked.status_id) and locked.status.token == terminated_token
        contract.status = ContractStatus.objects.get(token=terminated_token)
        if was_terminated:
            contract.termination_date = locked.termination_date or termination_date or datetime.date.today()
        elif termination_date:
            contract.termination_date = termination_date
        elif not contract.termination_date:
            contract.termination_date = datetime.date.today()
        contract.save()

        if not was_terminated:
            emit_contract_termination_confirmed(contract, termination_request)
    return not was_terminated


def cancel_contract_termination(instance, user):
    from django.db import transaction
    from contract.models import Contract, ContractStatus, ContractTerminationStatus
    from integrations.outbound.webhooks.events import emit_contract_termination_cancelled

    cancel_status = ContractTerminationStatus.objects.get(
        token=ConfigProject.objects.get(token='contract_termination_cancelled_token').value
    )
    instance.status = cancel_status
    instance.save()
    readings = instance.readings.all()
    readings.update(is_control=True)
    contract = instance.contract
    terminated_token = ConfigProject.objects.get(token='contract_terminated_status').value
    # La reactivació i l'avís es desen junts
    with transaction.atomic():
        locked = Contract.objects.select_for_update(of=("self",)).select_related("status").get(pk=contract.pk)
        was_terminated = bool(locked.status_id) and locked.status.token == terminated_token
        contract.status = ContractStatus.objects.get(token=ConfigProject.objects.get(token='contract_active_token').value)
        contract.termination_date = None
        contract.save()
        # Només si ja s'havia avisat de la baixa (el contracte era de baixa)
        if was_terminated:
            emit_contract_termination_cancelled(contract, instance)

    # reset bails status back to "No Retornat" if the termination is cancelled
    from contract.models import Bail, BailStatus
    from logger.models import LogBailStatus
    from django.utils import timezone

    pending_bail_token = ConfigProject.objects.get(token='bail_status_pending_token').value
    unreturned_bail_token = ConfigProject.objects.get(token='bail_status_unreturned_token').value
    unreturned_status = BailStatus.objects.get(token=unreturned_bail_token)

    bails = Bail.objects.filter(contract=contract, status__token=pending_bail_token)
    for bail in bails:
        prev_status = bail.status
        bail.status = unreturned_status
        bail.return_date = None
        bail.invoice = None
        bail.save()

        LogBailStatus.objects.create(
            object=bail,
            previous_status=prev_status,
            current_status=unreturned_status,
            user=user,
            timestamp=timezone.now(),
            observation="Baixa de contracte cancel·lada, fiança restablerta a No Retornat"
        )
