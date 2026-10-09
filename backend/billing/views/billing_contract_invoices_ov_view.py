import base64
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import Billing, Invoice, InvoiceStatus, PaymentStatus, Reading
from billing.views.invoice_pdf_view import generate_report_invoice_pdf
from contract.models import Contract
from billing.serializers.billing_contract_invoices_ov_serializer import BillingContractInvoicesOVSerializer, ContractConsumptionOVSerializer
from coredata.models import ConfigProject

class BillingContractInvoicesOVView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Contract.objects.all().order_by('-created_at')
    def get(self, request, contract_token):
        if not contract_token:
            return Response({'error': 'Contract token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        contract = Contract.objects.filter(token=contract_token).first()
        invoices = contract.invoices.all()
        
        serializer = BillingContractInvoicesOVSerializer(invoices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class BillingContractInvoiceOVView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Contract.objects.all().order_by('-created_at')
    def get(self, request, contract_token, invoice_token):
        if not contract_token or not invoice_token:
            return Response({'error': 'Contract token and invoice token are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        invoice = Invoice.objects.filter(token=invoice_token, contract__token=contract_token).first()
        
        if not invoice:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = BillingContractInvoicesOVSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def post(self, request, contract_token, invoice_token):
        if not contract_token or not invoice_token:
            return Response({'error': 'Contract token and invoice token are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        invoice = Invoice.objects.filter(token=invoice_token, contract__token=contract_token).first()
        
        if not invoice:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
        
        payment_status_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
        for payment in invoice.payments.all():
            payment.status = payment_status_paid
            payment.save()
        
        serializer = BillingContractInvoicesOVSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class BillingContractInvoiceOVPDFView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Contract.objects.all().order_by('-created_at')
    def get(self, request, contract_token, invoice_token):
        context = {'request': request}
        if not contract_token or not invoice_token:
            return Response({'error': 'Contract token and invoice token are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        invoice = Invoice.objects.filter(token=invoice_token, contract__token=contract_token).first()
        if not invoice:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
        
        url, doc_id, pdf_buffer = generate_report_invoice_pdf(invoice, request, context)
        pdf_base64 = base64.b64encode(pdf_buffer.getvalue()).decode('utf-8')
        
        return Response(pdf_base64, status=status.HTTP_200_OK)

class BillingContractInvoicesOVUnpaidView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Contract.objects.all().order_by('-created_at')
    def get(self, request, contract_token):
        if not contract_token:
            return Response({'error': 'Contract token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        contract = Contract.objects.filter(token=contract_token).first()
        invoice_expired_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_expired_token').value)
        invoice_confirmed_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_confirmed_token').value)
        invoice_endowment_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_endowment_token').value)
        invoices = contract.invoices.filter(status__in=[invoice_expired_status, invoice_confirmed_status, invoice_endowment_status])
        
        serializer = BillingContractInvoicesOVSerializer(invoices, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class BillingContractInvoiceOVPayView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Contract.objects.all().order_by('-created_at')
    def post(self, request, contract_token, invoice_token):
        if not contract_token or not invoice_token:
            return Response({'error': 'Contract token and invoice token are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        invoice = Invoice.objects.filter(token=invoice_token, contract__token=contract_token).first()
        
        if not invoice:
            return Response({'error': 'Invoice not found'}, status=status.HTTP_404_NOT_FOUND)
        
        payment_status_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
        for payment in invoice.payments.all():
            payment.status = payment_status_paid
            payment.save()
        
        serializer = BillingContractInvoicesOVSerializer(invoice)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
class ContractConsumptionOVView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Contract.objects.all().order_by('-created_at')
    def get(self, request, contract_token):
        if not contract_token:
            return Response({'error': 'Contract token is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        contract = Contract.objects.filter(token=contract_token).first()
        if not contract:
            return Response({'error': 'Contract not found'}, status=status.HTTP_404_NOT_FOUND)
        
        readings = Reading.objects.filter(
            invoices__contract=contract,
            is_active=True,
        ).distinct().order_by('reading_date')
        
        serializer = ContractConsumptionOVSerializer(readings, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    