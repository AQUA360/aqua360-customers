from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.http import FileResponse, JsonResponse
from django.core.files.base import ContentFile
from rest_framework.views import APIView, Response
from io import BytesIO
from xhtml2pdf import pisa
from datetime import datetime
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import GeneralPayment, GeneralPaymentSepaDocument, Payment, PersonBank
from contract.models import Contract, ContractRequest
from coredata.models import Person
from coredata.serializers import AddressSerializer, PersonAddressSerializer, PersonCardSerializer, PersonSerializer
from coredata.utils.iban_validator_utils import resolve_account_bic
from documentmanager.utils.sign_certificate_service import sign_pdf
from service.serializers.company_serializer import CompanySerializer

from documentmanager.utils.main_utils import upload_document
from billing.views.contract_sepa_pdf_view import _company_from_contract, _debtor_address

class SepaPDFDownloadViewSet(APIView):
  permission_classes = [IsAuthenticated] #Since it's a view that shows a document, no further permissions are needed
  queryset = Payment.objects.all().order_by('-created_at')
  def post(self, request, id, *args, **kwargs):
    
    general_payment = GeneralPayment.objects.get(id=id)
    company = None
    city = None
    print(request.data)
    request_id = request.data.get('id')
    person_id = request.data.get('person_id')
    value = request.data.get('value')
    contract_request = None
    person = None
    if value == 'request':
      contract_request = get_object_or_404(ContractRequest, id=request_id)
    elif value == 'contract':
      contract_request = get_object_or_404(Contract, id=request_id)

    # El compte bancari a mostrar ha de ser sempre el vinculat al payment del
    # contracte/sol·licitud (contract_request.payment), no el que arribi per URL
    # (id), que nomes es fa servir de fallback si el contracte no en te cap.
    if contract_request is not None and contract_request.payment is not None:
      general_payment = contract_request.payment
    personBank = general_payment.IBAN if general_payment.IBAN else None

    # Permet triar explicitament un altre compte de la persona (bank_id/person_bank_id),
    # en lloc del ja persistit al GeneralPayment. Si no s'envia, o l'id no existeix,
    # es manté el comportament actual (el compte ja guardat).
    bank_id = request.data.get('bank_id') or request.data.get('person_bank_id')
    if bank_id:
      selected_bank = PersonBank.objects.filter(id=bank_id).first()
      if selected_bank:
        personBank = selected_bank

    if person_id:
      if isinstance(person_id, int):
        try:
          person = get_object_or_404(Person, id=person_id)
        except:
          person = None
      else:
        try:
          person = get_object_or_404(Person, token=person_id['id'])
        except:
          person = None

    context = {'request': request}
    company = _company_from_contract(contract_request, context)

    if (contract_request.supply_point_default is not None and
        contract_request.supply_point_default.address is not None and
        contract_request.supply_point_default.address.city is not None):
      city = contract_request.supply_point_default.address.city.name

    payment_holder = personBank.person if personBank and personBank.person else None
    holder_person = person if person else payment_holder if payment_holder else contract_request.holder
    holder = PersonSerializer(holder_person, context=context).data if holder_person else None
    if holder and holder_person:
      holder['addresses'] = PersonAddressSerializer(holder_person.addresses.all(), many=True, context=context).data
    
    billing_address = None
    if holder:
      contract_billing_address_id = contract_request.address_billing.id if contract_request.address_billing else None
      
      if contract_billing_address_id:
        billing_address = next((address for address in holder.get('addresses', []) if address.get('id') == contract_billing_address_id), None)
        
      if not billing_address:
        billing_address = next((address for address in holder.get('addresses', []) if address.get('is_billing')), None)
      
      if not billing_address:
        billing_address = PersonAddressSerializer(contract_request.address_billing, context=context).data if contract_request else None
      
    now_date = datetime.now().date()
    
    print(personBank)
    
    if personBank and personBank.iban:
      iban = 'IBAN'+ personBank.iban.upper()
      iban = ' '.join(iban[i:i+4] for i in range(0, len(iban), 4))
    else:
      iban = None
    
    # El SWIFT del compte mana; si no n'hi ha, el del catàleg o el registre oficial (mai un BIC endevinat)
    swift = resolve_account_bic(
      personBank.iban, personBank.swift, personBank.bank.bic if personBank.bank else None
    ) if personBank else None
    
    person_fullname = personBank.name if personBank and personBank.name else holder.get('full_name') if holder else ''
    person_token = personBank.dni if personBank and personBank.dni else holder.get('token') if holder else ''
    
    # Render HTML content
    html_content = render_to_string('sepa_template.html', 
                                    {'iban': iban or '', 'swift':swift or '',
                                     'now_date': now_date, 'company': company or '', 
                                     'city': city or '', 'holder': holder or '', 
                                     'holder_address': billing_address or '',
                                     'debtor_address': _debtor_address(billing_address),
                                     # La referència del mandat ha de ser la que la remesa envia com a MndtId
                                     'mandate_reference': general_payment.mandate_id if general_payment else None,
                                     'person_fullname': person_fullname or '',
                                     'person_token': person_token or '',
                                     'contract': contract_request or '',
                                     'holder_fullname': holder.get('full_name') if holder else '',
                                     'holder_token': holder.get('token') if holder else '',
                                     'data_protection_law_text': company['data_protection_law_text'] if company and 'data_protection_law_text' in company else None})
    pdf_buffer = BytesIO()

    # Generate PDF from HTML
    pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
    if pisa_status.err:
        return JsonResponse({"error": "PDF generation failed"}, status=500)

    #SIGNATURE
    signed_pdf_buffer = sign_pdf(pdf_buffer, company, 'SEPA DIRECT DEBIT', 'SEPA')

    # Save PDF to `contract_file` field in ContractRequest instance
    pdf_filename = f"SEPA_{contract_request.token}.pdf"
    
    sepa, _ = GeneralPaymentSepaDocument.objects.get_or_create(general_payment=general_payment)
    
    sepa.template.save(pdf_filename, ContentFile(signed_pdf_buffer.getvalue()))

    
    # Return the URL to the saved PDF file
    file_url = request.build_absolute_uri(sepa.template.url)
    
    #upload_document
    #upload_document(ContentFile(pdf_buffer.getvalue()), 'SEPA', 'contract', request_id, f"{personBank.person.surname.lower()}_{personBank.person.name.lower()}", 'hdd', pdf_filename) 
    
    return JsonResponse({"pdf_url": file_url, "sepa_document_id": sepa.id})