from decimal import Decimal
import os
import uuid
from datetime import datetime, timedelta
import uuid
from django.conf import settings
from django.http import FileResponse, JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import InvoiceStatus, Payment, PaymentRemittance, PaymentRemittanceStatus, PaymentStatus
from billing.serializers.payment_serializer import PaymentSEPASerializer, PaymentSerializer
from billing.utils.payment_service import get_payment_SEPA_data, log_payment_status
from django.db.models import Sum
import xml.etree.ElementTree as ET
from django.core.files.base import ContentFile
from billing.utils.sepa_file_service import generate_xml, generate_xml_payments
from coredata.models import Bank, ConfigProject
from documentmanager.utils.main_utils import upload_document
from service.models import Company, CompanyBank, Exploitation
from django.db.models import Q, Count
from faker import Faker
fake = Faker()

class SEPAPaymentDocumentGenerateViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Payment.objects.all().order_by('-created_at')
    def put(self, request, *args, **kwargs):
        user = request.user
        is_commitment = request.data['is_commitment'] if 'is_commitment' in request.data else False
        is_piggy_bank = request.data['is_piggy_bank'] if 'is_piggy_bank' in request.data else False
        send_date = request.data['send_date'] if 'send_date' in request.data else None
        
        payments = []
        if( 'is_massive' in request.data):
            is_massive = request.data['is_massive']
            filter_data = request.data['data']
            exploitation = request.data['exploitation_id']
            billing = request.data['billing_id']

            if is_massive:
                filters = Q()
                
                if filter_data['origins'] or filter_data['send_date'] or is_commitment or is_piggy_bank:
                    if filter_data['origins']:
                        filters |= Q(invoice__origin__id__in=filter_data['origins'])
                    if is_commitment:
                        filters |= Q(commitment_deposit__isnull=False)
                        #filters &= Q(invoice__isnull=True)
                    if is_piggy_bank:
                        # filter piggy bank payments
                        filters |= Q(piggy_bank_movements__isnull=False)
                    filters &= Q(invoice__is_suppressed=False)
                    if filter_data['start_date']:
                        filters &= Q(payment_date__gte=filter_data['start_date'])
                    if filter_data['end_date']:
                        filters &= Q(payment_date__lte=filter_data['end_date'])
                    if filter_data['send_date']:
                        filters &= Q(invoice__send_at__lte=filter_data['send_date'])
                    if exploitation:
                        filters &= Q(invoice__exploitation=exploitation)
                    if billing:
                        filters &= Q(invoice__billing=billing)
                    try:
                        direct_debit_value = ConfigProject.objects.get(token='direct_debit_token').value
                        filters &= Q(payment_type_token=direct_debit_value)
                    except ConfigProject.DoesNotExist:
                        direct_debit_value = None
                    
                    try:
                        status_returned_token = ConfigProject.objects.get(token='payment_status_returned_token').value 
                        status_pending_token = ConfigProject.objects.get(token='payment_status_pending_token').value
                        status_expired_token = ConfigProject.objects.get(token='payment_status_expired_token').value
                        """ status_commitment_token = ConfigProject.objects.get(token='payment_status_commitment_token').value """
                        statuses = [status_returned_token, status_pending_token, status_expired_token]
                        filters &= Q(status__token__in=statuses)
                    except ConfigProject.DoesNotExist:
                        status_pending_token = None
                    filters &= Q(is_excluded=False)
                    print("filters")
                    print(filters)
                    payments = (
                        Payment.objects.filter(filters)
                        .filter(is_excluded=False)
                        .distinct()
                    )
                    payment_ids = payments.values_list('id', flat=True)
                    serializedPayments = PaymentSEPASerializer(payments, many=True).data
                    return JsonResponse({
                            "payment_ids": list(payment_ids) if payment_ids else None,
                            "payments": serializedPayments if payments else None,
                            "anomalies": None,
                            "document_file": None
                            })
                    
                return JsonResponse({
                            "payment_ids": None,
                            "payments": None,
                            "anomalies": None, 
                            "document_file": None})
                
                
        
        #raise Exception("Changing massive management")
        if(request.data['sentPayments'] and 'sentPayments' in request.data):
            status_sent = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_sent_token').value)
            payments = Payment.objects.filter(id__in=request.data['payments'])
            for payment in payments:
                log_payment_status(payment, status_sent, user)
            payments.update(status=status_sent, sent_date=datetime.now().date())
            return Response(status=status.HTTP_200_OK)
        
        payment_ids = request.data['payments']
        payments = Payment.objects.filter(id__in=payment_ids)
        payments.update(is_excluded=False)
        
        """ document, anomalies, document_data = get_payment_SEPA_data(payment_ids, request.data["data"])
        
        date_year = datetime.now().year
        date_month = datetime.now().month
        bank = CompanyBank.objects.get(id=request.data["bank_id"])
        xml_data = generate_xml(document, document_data, bank) """
        
        
        date_year = datetime.now().year
        date_month = datetime.now().month
        bank = CompanyBank.objects.get(id=request.data["bank_id"])
        xml_data, ident_msg = generate_xml_payments(payments, bank, send_date)
        
        random_uuid = uuid.uuid4()
        xml_file_name = f"sepa_{date_year}{date_month}{str(random_uuid.int)[:11]}.xml"
        
        service = settings.DOCUMENT_MANAGER_SERVICES.get("billing")
        xml_file = ContentFile(xml_data.encode("utf-8"), name=xml_file_name)
        
        payments_delete = request.data["payments_del"] if "payments_del" in request.data else None
        pmts_delete = []
        if payments_delete:
            print("getting payments to delete")
            pmts_delete = Payment.objects.filter(id__in=[p['id'] for p in payments_delete])
            pmts_delete.update(is_excluded=True)
        
        anomalies = []
        
        #get together all payments (both querysets) in a single value
        all_payments = list(payments) + list(pmts_delete)
        
        for payment in all_payments:
            if payment.amount <= 0:
                anomalies.append(payment.id)
                
        print("anomalies")
        print(anomalies)
        
        document = None
        
        print("\n\n\nSAVE FILE")
        #TODO: REMESA MODEL FALTA
        if(request.data['saveFile']):
            
            document = PaymentRemittance.objects.create(
                token=ident_msg,
                company_bank=bank,
                status=PaymentRemittanceStatus.objects.get(is_default=True),
            )
            document.payments.set(payments)
            number = fake.random_number(digits=5)
            document_file = upload_document(xml_file, 'REBUTS', 'REBUTS', document.id, document.token, '', service, xml_file_name)
            document.document = document_file
            document.save()
            payments = Payment.objects.filter(id__in=request.data['payments'])
            payments.update(document=document_file)
        
        
        serializedPayments = PaymentSEPASerializer(payments, many=True).data
        serializedPaymentsDelete = PaymentSEPASerializer(pmts_delete, many=True).data
        
        #return json data with anomalies and document_data
        return JsonResponse({
            "payment_ids": payment_ids if payment_ids else None,
            "payments": serializedPayments if payments else None,
            "payments_delete": serializedPaymentsDelete if pmts_delete else None,
            "anomalies": anomalies if anomalies else None,
            "document_file": document.document.id if document and document.document else None,
            "doc_id": document.id if document else None
            })


    

def get_valid_sepa_date(due_date):
    if isinstance(due_date, str):
        due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
    
    # Ensure at least next day to avoid rejection
    min_date = datetime.now().date() + timedelta(days=1)  
    return max(due_date, min_date).strftime("%Y-%m-%d")

def calculate_control_code(dni):
    dni = dni.upper()  
    numeric_dni = ""

    for char in dni:
        if '0' <= char <= '9':
            numeric_dni += char
        elif 'A' <= char <= 'Z':
            numeric_dni += str(ord(char) - ord('A') + 10) 
        else:
            return "Invalid DNI"

    numeric_dni += "142800"

    remainder = int(numeric_dni) % 97
    control_code = str(remainder).zfill(2)

    return control_code