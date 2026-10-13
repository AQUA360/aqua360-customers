import io
import zipfile

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response

from auth.permissions import PermissionManager
from billing.models import Invoice
from billing.tasks import generate_electronic_invoices
from billing.views.epayment_document_generate_view import generate_xml
from communication import process_policy
from communication.filters.communication_process_filter import CommunicationProcessFilter
from communication.models import Communication, CommunicationProcess, CommunicationProcessStatus, CommunicationStatus
from communication.permissions import CommunicationPermission
from communication.serializers.communication_process_serializer import CommunicationProcessSerializer, CommunicationProcessListSerializer, CommunicationProcessSaveSerializer
from coredata.models import ConfigProject
from statistics.utils.report_service import delete_file_later
class CommunicationProcessViewSet(viewsets.ModelViewSet):
  queryset = CommunicationProcess.objects.all().filter(is_active=True).order_by('-token', '-due_date')
  permission_classes = [IsAuthenticated, CommunicationPermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = CommunicationProcessFilter
  search_fields = ['token']
  ordering_fields = ['token']
  
  def get_serializer_class(self):
    
    if self.request.method in ['GET']:
        if self.action == 'list':  
            return CommunicationProcessListSerializer
        elif self.action == 'retrieve':
            return CommunicationProcessSerializer
    return CommunicationProcessSaveSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  
  @action(detail=False, methods=['get'], url_path='supply-cut-status')
  def supply_cut_status(self, request):
      """Preflight before starting a process for one or more supply cuts.

      Returns the tier the shared policy assigns ('block', 'warn' or 'none')
      together with the linked processes, so the UI can warn early instead of
      discovering it at save time. The write path re-runs the same policy under
      a row lock, so this is only advisory.
      """
      raw = request.query_params.get('supply_cut') or request.query_params.get('supply_cut_ids')
      if not raw:
          return Response({'detail': 'supply_cut is required'}, status=status.HTTP_400_BAD_REQUEST)

      try:
          cut_ids = sorted({int(value) for value in str(raw).split(',') if str(value).strip()})
      except (TypeError, ValueError):
          return Response({'detail': 'invalid supply_cut'}, status=status.HTTP_400_BAD_REQUEST)

      tier, processes = process_policy.inspect(cut_ids)
      return Response({
          'tier': tier,
          'supply_cut_ids': cut_ids,
          'processes': CommunicationProcessListSerializer(processes, many=True).data,
      })

  @action(detail=True, methods=['get'], url_path='e-invoices')
  def generate_electronic_invoices(self, request, pk=None):
      communication_process = CommunicationProcess.objects.get(id=pk)
      
      if not communication_process.communications.filter(types__token='electronic_inv').exists():
          return JsonResponse({"task_id": None})
      
      status_token = ConfigProject.objects.get(token='communication_status_sent_token').value
      sent_status = CommunicationStatus.objects.get(token=status_token)
      
      base_url = request.build_absolute_uri('/')
      task_result = generate_electronic_invoices.delay(pk, base_url)
      communication_process.communications.filter(types__token='electronic_inv').update(status=sent_status)
      communication_process.download_einvoices_task_id = task_result.id
      communication_process.save()
      
      if all(communication.status.token == status_token for communication in communication_process.communications.all()):
          process_finalized = CommunicationProcessStatus.objects.get(token=ConfigProject.objects.get(token='communication_process_status_finalized_token').value)
          communication_process.status = process_finalized
          communication_process.save()
      
      return JsonResponse({"task_id": task_result.id})
  
  @action(detail=False, methods=['get'], url_path='permissions')
  def permissions(self, request):
      pk = request.query_params.get('id')
      if pk:
          from django.contrib.auth.models import Group
          user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
          if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
              return Response( None, status=status.HTTP_403_FORBIDDEN )
          group = Group.objects.filter(id=pk).first()
          if not group:
              return Response( None, status=status.HTTP_404_NOT_FOUND )
          group_permissions = PermissionManager.get_model_group_permissions(group, 'communicationprocess')
          return Response(group_permissions, status=status.HTTP_200_OK)
      permissions = PermissionManager.get_model_permissions(request.user, 'communicationprocess', 'communication')
      return Response(permissions, status=status.HTTP_200_OK)
    
  def destroy(self, request, *args, **kwargs):
      from django.db import transaction
      from logger.models import LogCommunicationProcessStatusChange, LogCommunicationStatusChange

      instance = self.get_object()
      cancel_status = CommunicationProcessStatus.objects.filter(token='-1').first()
      if not cancel_status:
          return Response({"error": "Cancelled status not found"}, status=status.HTTP_400_BAD_REQUEST)
      
      cancel_comm_status = CommunicationStatus.objects.filter(token='-1').first()
      if not cancel_comm_status:
          return Response({"error": "Communication cancelled status not found"}, status=status.HTTP_400_BAD_REQUEST)

      with transaction.atomic():
          # Log and cancel process
          LogCommunicationProcessStatusChange.objects.create(
              object=instance,
              previous_status=instance.status,
              current_status=cancel_status,
              user=request.user
          )
          instance.status = cancel_status
          instance.save()

          # Log and cancel all internal communications
          for comm in instance.communications.all():
              prev_status = comm.status
              if prev_status != cancel_comm_status:
                  LogCommunicationStatusChange.objects.create(
                      object=comm,
                      previous_status=prev_status,
                      current_status=cancel_comm_status,
                      user=request.user
                  )
                  comm.status = cancel_comm_status
                  comm.save()

      return Response({"message": "Communication process and all its communications cancelled successfully"}, status=status.HTTP_200_OK)
    
  def get_permissions(self):
      if self.action == 'permissions':
          return [IsAuthenticated()]
      return super().get_permissions()