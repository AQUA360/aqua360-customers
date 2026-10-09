from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.http import FileResponse, JsonResponse
from django.core.files.base import ContentFile
from django.utils.dates import WEEKDAYS
from django.utils.encoding import force_str
from django.utils.translation import gettext as _
from django.utils.translation import pgettext_lazy
from rest_framework.views import APIView, Response
from rest_framework import status
from io import BytesIO
from xhtml2pdf import pisa
from datetime import datetime
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import CommitmentDeposit, PaymentCommitment
from contract.models import Contract, ContractRequest
from coredata.models import Person, PersonBank, PersonAddress
from coredata.serializers import AddressSerializer, PersonCardSerializer, PersonSerializer, PersonAddressSerializer
from documentmanager.utils.sign_certificate_service import sign_pdf
from service.models import Exploitation
from service.serializers.company_serializer import CompanySerializer
from service.serializers.supply_point_serializer import SupplyPointListSerializer

# El mes ja porta la preposició que toqui a cada idioma («d'octubre», «de octubre», «October»).
_MONTHS_WITH_PREPOSITION = {
    1: pgettext_lazy('date month with preposition', 'of January'),
    2: pgettext_lazy('date month with preposition', 'of February'),
    3: pgettext_lazy('date month with preposition', 'of March'),
    4: pgettext_lazy('date month with preposition', 'of April'),
    5: pgettext_lazy('date month with preposition', 'of May'),
    6: pgettext_lazy('date month with preposition', 'of June'),
    7: pgettext_lazy('date month with preposition', 'of July'),
    8: pgettext_lazy('date month with preposition', 'of August'),
    9: pgettext_lazy('date month with preposition', 'of September'),
    10: pgettext_lazy('date month with preposition', 'of October'),
    11: pgettext_lazy('date month with preposition', 'of November'),
    12: pgettext_lazy('date month with preposition', 'of December'),
}


def localized_long_date(value):
    return _('%(weekday)s, %(day)s %(month)s %(year)s') % {
        'weekday': force_str(WEEKDAYS[value.weekday()]),
        'day': value.day,
        'month': force_str(_MONTHS_WITH_PREPOSITION[value.month]),
        'year': value.year,
    }


class CommitmentDepositPDFDownloadViewSet(APIView):
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  queryset = CommitmentDeposit.objects.all().order_by('-created_at')
  def get(self, request, id, *args, **kwargs):
    deposit = CommitmentDeposit.objects.get(id=id)
    deposit_payments = PaymentCommitment.objects.filter(commitment_deposit=deposit, is_guide=True).order_by('due_date')
    payments_list = list(deposit_payments)
    half = (len(payments_list) + 1) // 2
    payments_col1 = payments_list[:half]
    payments_col2 = payments_list[half:]
    contract = deposit.contract
    if contract:
        holder = contract.holder
        holder_address = PersonAddress.objects.filter(person=holder, is_billing=True).first()
        address_complete = AddressSerializer(holder_address.address).data.get('address_complete') if holder_address and holder_address.address else None
        
        supply_point = contract.supply_point_default
        supply_point_address = supply_point.address if supply_point else None
        supply_point_address_complete = SupplyPointListSerializer(supply_point).data.get('address_complete') if supply_point else None
    else:
        holder = {
            'name': deposit.customer_final,
            'surname': '',
            'token': deposit.customer_token_final,
        }
        holder_address = None
        address_complete = deposit.address_final + ', ' + deposit.location_final if deposit.address_final and deposit.location_final else (deposit.address_final or deposit.location_final)
        supply_point = None
        supply_point_address = None
        supply_point_address_complete = address_complete
    
    print("holder_address")
    print(holder_address)
    
    exploitation = Exploitation.objects.filter(is_active=True).first()
    if not exploitation:
        return JsonResponse({"error": "No active exploitation found"}, status=500)
        
    company = CompanySerializer(exploitation.company, context={'request': request}).data
    # Fetch logo and exploitation image
    logo = company.get('logo')
    if logo and not logo.startswith('http'):
        logo = request.build_absolute_uri(logo)
        logo = logo.replace('https', 'http')

    exploitation_image = exploitation.logo.url if exploitation and exploitation.logo else None
    if exploitation_image and not exploitation_image.startswith('http'):
        exploitation_image = request.build_absolute_uri(exploitation_image)
        exploitation_image = exploitation_image.replace('https', 'http')

    now_date = datetime.now().date()
    now_date_ca = localized_long_date(now_date)

    # Render HTML content
    html_content = render_to_string('commitment_deposit_template.html', 
                                    {'now_date': now_date,
                                     'now_date_ca': now_date_ca,
                                     'contract': contract,
                                     'logo': logo,
                                     'exploitation_image': exploitation_image,
                                     'main_color': company.get('invoice_main_color') or '#eaeaea',
                                     'secondary_color': company.get('invoice_secondary_color') or '#074df0',
                                     'tertiary_color': '#f5f5f5',
                                     'is_digital': True,
                                     'holder': holder,
                                     'holder_address': holder_address,
                                     'address_complete': address_complete,
                                     'supply_point_address': supply_point_address,
                                     'supply_point_address_complete': supply_point_address_complete,
                                     'deposit': deposit,
                                     'invoices': deposit.invoices.all().prefetch_related('readings'),
                                     'deposit_payments': deposit_payments,
                                     'payments_col1': payments_col1,
                                     'payments_col2': payments_col2,
                                     'company': company,
                                    }
                                    )
    pdf_buffer = BytesIO()

    # Generate PDF from HTML
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
    if pisa_status.err:
        return JsonResponse({"error": "PDF generation failed"}, status=500)
    pdf_buffer.seek(0)

    signed_pdf_buffer = sign_pdf(pdf_buffer, company, 'RECONEIXEMENT DEL DEUTE', 'COMMITMENT_DEPOSIT')
    
    response = FileResponse(
            signed_pdf_buffer,
            as_attachment=True,
            content_type='application/pdf'
        )
    
    return response