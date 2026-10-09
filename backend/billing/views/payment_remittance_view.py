from rest_framework.decorators import action
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from django.http import HttpResponse
from django.utils.translation import gettext as _
import csv
import io

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from coredata.utils.language_utils import use_default_language
from billing.filter.payment_remittance_filter import PaymentRemittanceFilter
from billing.models import PaymentRemittance, PaymentRemittanceStatus, PaymentStatus, Payment
from billing.serializers.payment_remittance_serializer import PaymentRemittanceSerializer, PaymentRemittanceListSerializer
from billing.serializers.payment_serializer import PaymentSerializer, PaymentSEPASerializer
from coredata.models import ConfigProject
from billing.tasks import send_payment_remittances
from billing.permissions import PaymentPermission


class PaymentRemittanceViewSet(viewsets.ModelViewSet):
    queryset = PaymentRemittance.objects.select_related('company_bank').order_by('-created_at')
    serializer_class = PaymentRemittanceSerializer
    permission_classes = [IsAuthenticated, PaymentPermission]
    filterset_class = PaymentRemittanceFilter
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    search_fields = ['token']
    ordering_fields = ['token', 'created_at']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return PaymentRemittanceListSerializer
        return PaymentRemittanceSerializer

    @action(detail=False, methods=['post'], url_path='send')
    def send_remittances(self, request):
        ids = request.data.get('ids')
        sent_at = request.data.get('sent_at')
        user = request.user if request.user else None

        if not ids or not sent_at:
            return Response(
                {"detail": "Missing required fields: 'ids' and/or 'sent_at'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            status_token = ConfigProject.objects.get(token='payment_remittance_status_sent_token').value
            status_sent = PaymentRemittanceStatus.objects.get(token=status_token)
            
        except (ConfigProject.DoesNotExist, PaymentRemittanceStatus.DoesNotExist):
            return Response(
                {"detail": "Sent status configuration is missing."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        # Validate that all IDs exist before updating
        existing_ids = set(PaymentRemittance.objects.filter(id__in=ids).values_list('id', flat=True))
        requested_ids = set(ids)
        missing_ids = requested_ids - existing_ids
        
        if missing_ids:
            return Response(
                {"detail": f"Payment remittances not found: {list(missing_ids)}"},
                status=status.HTTP_404_NOT_FOUND
            )
        # Perform bulk update - this is already optimized
        updated_count = PaymentRemittance.objects.filter(id__in=ids).update(
            status=status_sent, 
            sent_at=sent_at, 
            sent_by=user
        )
        # Validate update was successful
        if updated_count != len(ids):
            return Response(
                {"detail": f"Expected to update {len(ids)} records, but updated {updated_count}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        # Start background task
        send_payment_remittances.delay(ids, sent_at)
        
        return Response({
            "message": f"Successfully sent {updated_count} payment remittances",
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['delete'], url_path='delete-payment-relation/(?P<payment_id>[^/.]+)')
    def delete_payment_relation(self, request, pk=None, payment_id=None):
        """
        Elimina la relació entre un PaymentRemittance i un Payment específic.
        URL: /billing/payment-remittance/{remittance_id}/delete-payment-relation/{payment_id}/
        """
        try:
            # Obtenir el PaymentRemittance
            payment_remittance = self.get_object()
            
            # Verificar que el Payment existeix
            try:
                payment = Payment.objects.get(id=payment_id)
            except Payment.DoesNotExist:
                return Response(
                    {"detail": f"Payment amb ID {payment_id} no existeix."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Verificar que el Payment està relacionat amb aquest PaymentRemittance
            if not payment_remittance.payments.filter(id=payment_id).exists():
                return Response(
                    {"detail": f"Payment {payment_id} no està relacionat amb PaymentRemittance {pk}."},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Eliminar la relació
            payment_remittance.payments.remove(payment)
            payment_remittance.pending_changes = True
            payment_remittance.save()
            
            return Response(
                {
                    "message": f"S'ha eliminat correctament la relació entre PaymentRemittance {pk} i Payment {payment_id}.",
                    "payment_remittance_id": pk,
                    "payment_id": payment_id
                },
                status=status.HTTP_200_OK
            )
            
        except PaymentRemittance.DoesNotExist:
            return Response(
                {"detail": f"PaymentRemittance amb ID {pk} no existeix."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": f"Error eliminant la relació: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'], url_path='payments')
    def get_payments(self, request, pk=None):
        # Obtenir el PaymentRemittance directament sense passar pels filtres
        # perquè el paràmetre 'search' és per als payments, no per al remittance
        try:
            payment_remittance = PaymentRemittance.objects.get(pk=pk)
        except PaymentRemittance.DoesNotExist:
            return Response(
                {"detail": f"PaymentRemittance amb ID {pk} no existeix."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        
        payments = (payment_remittance.payments.select_related('invoice', 'contract', 'status').all())

        
        # Cerca per paràmetre 'search'
        search_query = request.query_params.get('search', None)
        status_query = request.query_params.get('status', None)
        payment_type_query = request.query_params.get('type', None)
        if search_query:
            payments = payments.filter(
                Q(token__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(invoice__token__icontains=search_query) |
                Q(invoice__serie_final__icontains=search_query) |
                Q(invoice__contract__token__icontains=search_query)
            )
        if status_query:
            status_query = status_query.split(',')
            payments = payments.filter(status__id__in=status_query)
        if payment_type_query:
            payment_type_query = payment_type_query.split(',')
            payments = payments.filter(payment_type_token__in=payment_type_query)

        
        ALLOWED_ORDERING = {
            'id': 'id',
            'token': 'token',
            'amount': 'amount',
            'payment_date': 'payment_date',
            'due_date': 'due_date',
            'invoice': 'invoice__token',
            'contract': 'contract__token',
            # Tria si prefereixes ordenar pel nom d’estat o per la seva posició
            'status': 'status__position',  # o 'status__name'
        }

        ordering_param = request.query_params.get('ordering')
        if ordering_param:
            raw_fields = [f.strip() for f in ordering_param.split(',') if f.strip()]
            django_fields = []
            for f in raw_fields:
                desc = f.startswith('-')
                key = f[1:] if desc else f
                if key in ALLOWED_ORDERING:
                    mapped = ALLOWED_ORDERING[key]
                    django_fields.append(('-' if desc else '') + mapped)
            if django_fields:
                payments = payments.order_by(*django_fields)
            else:
                # Si no hi ha cap camp vàlid, fem un fallback estable
                payments = payments.order_by('-payment_date', 'id')
        else:
            # Ordre per defecte si no es passa res
            payments = payments.order_by('-payment_date', 'id')

        
        # Comprovar si es demana exportació CSV
        export_type = request.query_params.get('export', None)
        if export_type == 'csv':
            return self._generate_csv_response(payments, payment_remittance)
        
        # Paginar el queryset
        page = self.paginate_queryset(payments)
        if page is not None:
            serializer = PaymentSEPASerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # Si no hi ha paginació, retornar tots (per si de cas)
        serializer = PaymentSEPASerializer(payments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @use_default_language
    def _generate_csv_response(self, payments, payment_remittance):
        """Genera una resposta CSV amb els payments (només les columnes mostrades al frontend)"""
        serializer = PaymentSEPASerializer(payments, many=True)
        data = serializer.data
        
        # Crear el buffer per al CSV
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', lineterminator='\n')
        
        # Escriure capçalera (només les columnes del frontend)
        headers = [
            _('Token'),  # Identificació
            _('Invoice'),  # Factura o Commitment Deposit
            _('Amount'),  # Total
            _('Contract'),  # Contracte
            _('Payment Date'),  # Data de pagament
            _('Status'),  # Estat
            _('Due Date')  # Límit
        ]
        writer.writerow(headers)
        
        # Escriure dades
        for payment in data:
            # Determinar el valor de Invoice (token de la factura o "commitment_deposit")
            invoice_value = ''
            if payment.get('invoice'):
                invoice_value = payment.get('invoice', {}).get('token', '')
            elif payment.get('commitment_deposit'):
                invoice_value = 'commitment_deposit'
            
            # Contract token
            contract_token = payment.get('contract', {}).get('token', '') if payment.get('contract') else '-'
            
            # Status name
            status_name = payment.get('status', {}).get('name', '') if payment.get('status') else '-'
            
            row = [
                payment.get('token', ''),
                invoice_value,
                payment.get('amount', ''),
                contract_token,
                payment.get('payment_date', '') if payment.get('payment_date') else '-',
                status_name,
                payment.get('due_date', '') if payment.get('due_date') else '-',
            ]
            writer.writerow(row)
        
        # Crear la resposta HTTP
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
        filename = f'payment_remittance_{payment_remittance.id}_payments.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

