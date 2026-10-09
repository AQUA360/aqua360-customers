from django.db.models import Q
from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from auth.permissions import PermissionManager
from billing.models import Invoice, Reading
from billing.serializers.invoice_serializer import InvoiceMinimalSerializer
from billing.serializers.reading_serializer import ReadingMinimalSerializer
from communication.models import Communication, CommunicationProcess, CommunicationProcessStatus, CommunicationStatus, MessageType
from communication.filters.communication_filter import CommunicationFilter
from communication.serializers.communication_serializer import CommunicationSerializer, CommunicationListSerializer, CommunicationSaveSerializer
from communication.utils.communication_service import get_email_image_preview
from contract.models import Contract
from coredata.models import ConfigProject, Person

class CommunicationViewSet(viewsets.ModelViewSet):
  queryset = Communication.objects.all().filter(is_active=True).order_by('-created_at', '-status', '-sent_at')
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  filter_backends = [DjangoFilterBackend, OrderingFilter]
  filterset_class = CommunicationFilter
  search_fields = [
    'token', 'process__token', 'person__token',
    'status__name'
  ]
  ordering_fields = '__all__'
  
  def get_serializer_class(self):
    
    if self.request.method in ['GET']:
        if self.action == 'list':  
            return CommunicationListSerializer
        elif self.action == 'retrieve':
            return CommunicationSerializer
    return CommunicationSaveSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  
  @action(detail=False, methods=['post'], url_path='mark-as-sent')
  def mark_as_sent(self, request):
    """
    Marca comunicacions postals (letter) com a enviades.
    Accepta:
      - process_id: totes les cartes del procés (flux massiu)
      - communication_ids: una o més comunicacions individuals
    Assigna status=enviada i sent_at (abans només es canviava l'estat).
    """
    from django.utils import timezone
    from logger.models import LogCommunicationStatusChange

    process_id = request.data.get('process_id')
    communication_ids = request.data.get('communication_ids')
    if not process_id and not communication_ids:
      return Response(
        {"error": "process_id or communication_ids is required"},
        status=status.HTTP_400_BAD_REQUEST
      )

    status_token = ConfigProject.objects.get(token='communication_status_sent_token').value
    status_sent = CommunicationStatus.objects.get(token=status_token)
    now = timezone.now()
    process = None

    if process_id:
      process_sent = CommunicationProcessStatus.objects.get(
        token=ConfigProject.objects.get(token='communication_process_status_current_token').value
      )
      process = CommunicationProcess.objects.get(id=process_id)
      process.status = process_sent
      process.save()
      communications = Communication.objects.filter(
        process__id=process_id, types__token='letter'
      ).select_related('status')
    else:
      if not isinstance(communication_ids, list):
        communication_ids = [communication_ids]
      communications = Communication.objects.filter(
        id__in=communication_ids, types__token='letter'
      ).select_related('status')

    log_entries = []
    for communication in communications:
      if communication.status_id != status_sent.id:
        log_entries.append(LogCommunicationStatusChange(
          object=communication,
          previous_status=communication.status,
          current_status=status_sent,
          user=request.user if request.user and request.user.is_authenticated else None,
        ))
      communication.status = status_sent
      communication.sent_at = now
      communication.save(update_fields=['status', 'sent_at'])

    if log_entries:
      LogCommunicationStatusChange.objects.bulk_create(log_entries)

    if process:
      if all(
        communication.status.token == status_token
        for communication in process.communications.all()
      ):
        process_finalized = CommunicationProcessStatus.objects.get(
          token=ConfigProject.objects.get(token='communication_process_status_finalized_token').value
        )
        process.status = process_finalized
        process.save()

    return Response({"message": "Communications marked as sent"}, status=status.HTTP_200_OK)

  @action(detail=False, methods=['post'], url_path='return-letter')
  def return_letter(self, request):
    """
    Marca una comunicació (carta) com a Retornada.
    Accepta:
      - id: id de la comunicació individual
    """
    from logger.models import LogCommunicationStatusChange

    comm_id = request.data.get('id')
    if not comm_id:
      return Response(
        {"error": "id is required"},
        status=status.HTTP_400_BAD_REQUEST
      )

    try:
      communication = Communication.objects.select_related('status').get(id=comm_id)
    except Communication.DoesNotExist:
      return Response(
        {"error": "Communication not found"},
        status=status.HTTP_404_NOT_FOUND
      )

    status_returned = CommunicationStatus.objects.filter(token='-3').first()
    if not status_returned:
      return Response(
        {"error": "Returned status not found"},
        status=status.HTTP_400_BAD_REQUEST
      )

    if communication.status_id != status_returned.id:
      LogCommunicationStatusChange.objects.create(
        object=communication,
        previous_status=communication.status,
        current_status=status_returned,
        user=request.user if request.user and request.user.is_authenticated else None,
      )

    communication.status = status_returned
    communication.save(update_fields=['status'])

    return Response({"message": "Communication marked as returned"}, status=status.HTTP_200_OK)

  @action(detail=False, methods=['post'], url_path='email-preview')
  def get_email_preview(self, request):
    
    message = request.data.get('message')
    comm_id = request.data.get('comm_id')
    return get_email_image_preview(message, comm_id)
  
  @action(detail=False, methods=['get'], url_path='get-client-info')
  def get_client_info(self, request):
    contract_id = request.query_params.get('contract_id')
    person_id = request.query_params.get('person_id')
    if not contract_id and not person_id:
      return Response({"error": "contract_id or person_id is required"}, status=status.HTTP_400_BAD_REQUEST)
    if contract_id:
      contract = Contract.objects.get(id=contract_id)
      person = None
    else:
      person = Person.objects.get(id=person_id)
      contract = None
    
    invoice_type_final = ConfigProject.objects.get(token='invoice_type_invoice_token').value
    
    invoice_filters = Q()
    readings = []
    if contract:
      invoice_filters |= Q(contract__id=contract.id)
      invoice_filters |= Q(contract_request__contract__id=contract.id)
      readings = Reading.objects.filter(is_control=False, is_initial=False
        ).filter(
          Q(contract__id=contract.id) |
          Q(invoices__contract__id=contract.id)
          ).order_by('-reading_date')
    if person:
      person_name_variations = [
            f"{person.name} {person.surname if person.surname else ''}",
            f"{person.name}{person.surname if person.surname else ''}",
            f"{person.name}{person.surname}" if person.surname else person.name,
        ]
      invoice_filters &= Q(customer_token_final=person.token, 
                   customer_final__in=person_name_variations)
      readings = Reading.objects.filter(
        is_control=False, is_initial=False).filter(
        Q(invoices__person__id=person.id) | 
        Q(contract__holder__id=person.id) |
        Q(contract__tenant__id=person.id, contract__tenant__isnull=False) |
        Q(contract__owner__id=person.id, contract__owner__isnull=False)
      )
    invoices = Invoice.objects.filter(invoice_filters).filter(type_final=invoice_type_final).order_by('-issue_date')
    
    invoices_serialized = InvoiceMinimalSerializer(invoices, many=True).data
    readings_serialized = ReadingMinimalSerializer(readings, many=True).data
    
    return Response({"invoices": invoices_serialized, "readings": readings_serialized}, status=status.HTTP_200_OK)
  
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
          group_permissions = PermissionManager.get_model_group_permissions(group, 'communication')
          return Response(group_permissions, status=status.HTTP_200_OK)
      permissions = PermissionManager.get_model_permissions(request.user, 'communication', 'communication')
      return Response(permissions, status=status.HTTP_200_OK)
    
  def destroy(self, request, *args, **kwargs):
      instance = self.get_object()
      cancel_status = CommunicationStatus.objects.filter(token='-1').first()
      if not cancel_status:
          return Response({"error": "Cancelled status not found"}, status=status.HTTP_400_BAD_REQUEST)
      
      from logger.models import LogCommunicationStatusChange
      LogCommunicationStatusChange.objects.create(
          object=instance,
          previous_status=instance.status,
          current_status=cancel_status,
          user=request.user
      )
      
      instance.status = cancel_status
      instance.save()
      return Response({"message": "Communication cancelled successfully"}, status=status.HTTP_200_OK)
    
  @action(detail=False, methods=['post'], url_path='export')
  def export_csv(self, request, *args, **kwargs):
      from communication.tasks import export_communications_csv_task

      task = export_communications_csv_task.delay(request.query_params.dict())
      return Response(
          {"task_id": task.id, "status": "pending", "message": "Communications export in progress"},
          status=status.HTTP_202_ACCEPTED,
      )
     
  def get_permissions(self):
      if self.action == 'permissions':
          return [IsAuthenticated()]
      if self.action == 'export_csv':
          # Exportar és una acció de només lectura: exigim `view_communication`
          # encara que la petició sigui un POST (DjangoModelPermissions exigiria
          # `add_communication`, permís equivocat per a aquesta acció).
          from documentmanager.utils.export_permissions import export_permission_class
          return [IsAuthenticated(), export_permission_class('communication', 'communication')()]
      return super().get_permissions()