from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import Q

from django.db import transaction
from django.utils import timezone
from auth.permissions import PermissionManager
from lecturapp.mixins import LecturappAuthMixin
from notification.filters.incident_filter import IncidentFilter
from notification.serializers.incident_serializer import *

from ..models import Incident
from coredata.models import ConfigProject
from order.models import OrderStatus
import logging

logger = logging.getLogger(__name__)

class IncidentPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size' 

class IncidentViewSet(viewsets.ModelViewSet):
  queryset = Incident.objects.filter(is_active=True).select_related(
      'status', 'type', 'channel', 'assigned_to', 'contract', 'invoice', 'order_incident', 'receipt_document',
  ).order_by('status__position', '-created_at')
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = IncidentFilter
  pagination_class = IncidentPagination
  search_fields = ['token','name']
  ordering_fields = ['token','name','created_at','due_at','assigned_to']
  
  def get_serializer_class(self):
    if self.action == 'list':
      return IncidentListSerializer
    elif self.action == 'retrieve':
      return IncidentSerializer
    return IncidentSaveSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  
  def perform_destroy(self, instance):
      # Esborrat lògic: es desa qui l'ha esborrat i quan
      instance.is_active = False
      instance.deleted_at = timezone.now()
      instance.deleted_by = self.request.user
      instance.save(update_fields=['is_active', 'deleted_at', 'deleted_by', 'updated_at'])
  
  def perform_update(self, serializer):
      with transaction.atomic():
          instance = serializer.save()
          # We check if the close_associated_orders flag is present in the request data
          close_associated_orders = self.request.data.get('close_associated_orders', False)
          
          if close_associated_orders:
              # Check permissions for updating order statuses
              # We log a warning if the user lacks permissions, but proceed with the update 
              # as a system-level action if requested.
              user_permissions = PermissionManager.get_model_permissions(self.request.user, 'order', 'order')
              if not user_permissions.get('can_change'):
                  import logging
                  logger = logging.getLogger(__name__)
                  logger.warning(f"User {self.request.user} closing associated orders for incident {instance.token} via system-level update.")

              # Retrieve the correct token for 'Closed' statuses from ConfigProject
              config = ConfigProject.objects.filter(token='order_status_completed_token').first()
              if config:
                  closed_status_token = config.value
              else:
                  # Fallback to 'CLOSED' if config is not found, as per instructions
                  closed_status_token = 'CLOSED'
              
              try:
                  closed_status = OrderStatus.objects.get(token=closed_status_token)
                  # Update all associated non-closed orders
                  # We iterate and save to ensure signals (logging, completed_at) are triggered
                  orders_to_close = instance.orders.exclude(status=closed_status)
                  for order in orders_to_close:
                      order.status = closed_status
                      order.save()
              except OrderStatus.DoesNotExist:
                  import logging
                  logger = logging.getLogger(__name__)
                  logger.error(f"OrderStatus with token {closed_status_token} not found. Could not close associated orders for incident {instance.token}.")
  
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
          group_permissions = PermissionManager.get_model_group_permissions(group, 'incident')
          return Response(group_permissions, status=status.HTTP_200_OK)
      permissions = PermissionManager.get_model_permissions(request.user, 'incident', 'notification')
      return Response(permissions, status=status.HTTP_200_OK)
    
  @action(detail=False, methods=['get'], url_path='export/excel')
  def export_csv(self, request, *args, **kwargs):
      try:
          # Obtenir els paràmetres del query string
          query_params = request.query_params.dict()
          
          # La cua d'exportacions deixa constància de qui exporta, quan i amb quins filtres
          from documentmanager.utils.export_jobs import enqueue_export, export_job_response
          from notification.tasks import export_incidents_csv_task
          job = enqueue_export(
              request, export_incidents_csv_task, kind='incidents', name="Incidències",
              args=[query_params], kwargs={'user_id': request.user.id}, params=query_params,
          )
          return Response(export_job_response(job), status=status.HTTP_202_ACCEPTED)
          
      except Exception as e:
          logger.exception("Error inesperat")
          return Response(
              {"error": "Error en iniciar l'exportació."},
              status=status.HTTP_500_INTERNAL_SERVER_ERROR
          )

  @action(detail=True, methods=['get'], url_path='timeline')
  def timeline(self, request, pk=None):
      """Cronologia unificada de la incidència: estats, canvis, trucades, informes i observacions."""
      from notification.utils.incident_timeline import build_timeline
      return Response(build_timeline(self.get_object()))

  @action(detail=True, methods=['post'], url_path='send-receipt')
  def send_receipt(self, request, pk=None):
      """Genera (i envia, si hi ha correu) el justificant de registre."""
      from notification.utils.incident_utils import send_receipt
      incident = self.get_object()
      try:
          sent = send_receipt(incident)
      except Exception:
          logger.exception("Error generant el justificant de la incidència %s", incident.pk)
          return Response({"error": "Error generating the receipt."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
      return Response({"sent": sent, "document_id": incident.receipt_document_id})

  def get_permissions(self):
      if self.action == 'permissions':
          return [IsAuthenticated()]
      return super().get_permissions()
    

class IncidentAppViewSet(LecturappAuthMixin, viewsets.ModelViewSet):
  """
  API endpoint that allows incident to be viewed or edited.
  """
  queryset = Incident.objects.filter(is_active=True).order_by('id')
  serializer_class = IncidentAppSerializer
  permission_classes = [AllowAny]