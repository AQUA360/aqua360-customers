from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.decorators import action
from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from billing.filter.joined_payment_filter import JoinedPaymentFilter
from billing.models import JoinedPayment
from billing.permissions import PaymentPermission
from billing.serializers.joined_payment_serializer import JoinedPaymentListSerializer, JoinedPaymentSerializer, JoinedPaymentSaveSerializer
from billing.utils.joined_payment_service import get_pending_client_data, generate_report_joined_payment_pdf
from billing.utils.payment_proof_service import get_payments_from_request_data, render_payment_proof_pdf
from statistics.utils.report_service import delete_file_later


class JoinedPaymentViewSet(viewsets.ModelViewSet):
  """
  API endpoint that allows reading batches to be viewed or edited.
  """
  queryset = JoinedPayment.objects.filter(is_active=True).order_by('-created_at')
  permission_classes = [IsAuthenticated, PaymentPermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = JoinedPaymentFilter
  search_fields = ['token','contract__token','person__token']
  ordering_fields = [
    'token','contract__token','person__token',
    'total_final','status__position','payment_type',
    'payment_date', 'due_date', 'created_at'
    ]
  
  def get_serializer_class(self):
    
    if self.request.method in ['GET']:
        if self.action == 'list':  
          return JoinedPaymentListSerializer
        elif self.action == 'retrieve':
          return JoinedPaymentSerializer
    return JoinedPaymentSaveSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  
  @action(detail=False, methods=['post'], url_path='pending-client-data')
  def obtain_pending_client_data(self, request):
      data = request.data
      client_data = get_pending_client_data(data)
      return Response({"client_data": client_data}, status=status.HTTP_200_OK)
  
  
  @action(detail=False, methods=['post'], url_path='payment-proof')
  def generate_payment_proof(self, request):
    id = request.data.get('id', None)
    joined_payment = JoinedPayment.objects.get(id=id)
  
    payments = joined_payment.payments.all()
    payment_date = request.data.get('date', None)
    observation = request.data.get('observation', None)

    try:
        signed_pdf_buffer, pdf_filename = render_payment_proof_pdf(
            payments,
            request,
            payment_date=payment_date,
            observation=observation,
        )
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except RuntimeError:
        return JsonResponse({'error': 'PDF generation failed'}, status=500)

    signed_pdf_buffer.seek(0)

    temp_rel_path = f"tmp/payment_proof_docs/{pdf_filename}"
    saved_path = default_storage.save(temp_rel_path, ContentFile(signed_pdf_buffer.getvalue()))
    file_url = request.build_absolute_uri(default_storage.url(saved_path))

    delete_file_later(saved_path, delay_seconds=20)

    return JsonResponse({'pdf_url': file_url})
  
    
  @action(detail=True, methods=['get', 'post'], url_path='generate-pdf')
  def generate_joined_payment_pdf(self, request, pk=None):
      user = request.user
      if request.method == 'GET':
          instance = self.get_object()
      else:
          instance = None
      
      return generate_report_joined_payment_pdf(instance, user, request)