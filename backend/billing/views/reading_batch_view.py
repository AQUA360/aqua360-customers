from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response
from django.db.models import Prefetch

from django.contrib.auth.models import Group

from auth.permissions import PermissionManager
from billing.filter.reading_batch_filter import ReadingBatchFilter
from billing.models import ReadingBatch, ReadingBatchStatus
from billing.serializers.reading_batch_serializer import ReadingBatchSaveSerializer, ReadingBatchSerializer, ReadingBatchMinimalSerializer
from billing.permissions import ReadingPermission
from billing.tasks import export_reading_batch_task
from billing.utils.reading_batch_service import get_missing_supply_points_queryset
from service.models import Meter, Route


class _ReadingBatchContentNegotiation(DefaultContentNegotiation):
    """
    DRF's ?format=… is meant for renderers (json, api, …). Values like csv/xlsx
    match no renderer and would raise Http404 before the view runs. If nothing
    matches, fall back to the full renderer list so the request can reach the
    view; download still reads export format via export_format / file_format /
    format when it is one of csv|xls|xlsx.
    """

    def filter_renderers(self, renderers, format):
        filtered = [r for r in renderers if r.format == format]
        return filtered if filtered else list(renderers)


class ReadingBatchViewSet(viewsets.ModelViewSet):
  """
  API endpoint that allows reading batches to be viewed or edited.
  """
  queryset = ReadingBatch.objects.all().filter(is_active=True).order_by('id')
  permission_classes = [IsAuthenticated, ReadingPermission]
  content_negotiation_class = _ReadingBatchContentNegotiation
  filter_backends = [DjangoFilterBackend, OrderingFilter]
  filterset_class = ReadingBatchFilter
  # search handled by ReadingBatchFilter.search (avoid double SearchFilter pass)
  ordering_fields = ['id','token','name','created_at','status__name']
  _download_file_formats = frozenset({"csv", "xls", "xlsx"})

  def get_queryset(self):
    qs = (
      ReadingBatch.objects.filter(is_active=True)
      .select_related('status')
      .order_by('id')
    )
    if self.action == 'list':
      qs = qs.prefetch_related(
        Prefetch('routes', queryset=Route.objects.only('id')),
        Prefetch('fix_meters', queryset=Meter.objects.only('id')),
      )
    return qs

  def get_serializer_class(self):
    
    if self.request.method in ['GET']:
        if self.action == 'list':  # Corresponds to GET / (list view)
            return ReadingBatchMinimalSerializer
        elif self.action == 'retrieve':  # Corresponds to GET /id (detail view)
            return ReadingBatchSerializer
    return ReadingBatchSaveSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context
  
  @action(detail=False, methods=['get'], url_path='permissions')
  def permissions(self, request):
      pk = request.query_params.get('id')
      if pk:
          user_permissions = PermissionManager.get_model_permissions(request.user, 'auth', 'group')
          if not user_permissions['can_view'] or not user_permissions['can_change'] or not request.user.is_superuser:
              return Response( None, status=status.HTTP_403_FORBIDDEN )
          group = Group.objects.filter(id=pk).first()
          if not group:
              return Response( None, status=status.HTTP_404_NOT_FOUND )
          group_permissions = PermissionManager.get_model_group_permissions(group, 'readingbatch')
          return Response(group_permissions, status=status.HTTP_200_OK)
      permissions = PermissionManager.get_model_permissions(request.user, 'readingbatch', 'billing')
      return Response(permissions, status=status.HTTP_200_OK)

  @action(detail=True, methods=['post'], url_path='create-missing-batch')
  def create_missing_batch(self, request, pk=None):
      """
      Crea un lot nou NOMÉS amb els comptadors dels subministraments d'aquest lot
      que han quedat sense lectura. El nou lot es fixa per comptadors (fix_meters),
      no per rutes, per així no arrossegar tot el padró.
      """
      source_batch = self.get_object()

      name = (request.data.get('name') or '').strip()
      if not name:
          return Response(
              {'detail': "El nom del nou lot és obligatori."},
              status=status.HTTP_400_BAD_REQUEST,
          )

      missing_supply_points = get_missing_supply_points_queryset(source_batch)
      meter_ids = set(
          missing_supply_points.filter(meter__isnull=False).values_list('meter_id', flat=True)
      )

      if not meter_ids:
          return Response(
              {'detail': "No hi ha subministraments sense lectura per crear un lot."},
              status=status.HTTP_400_BAD_REQUEST,
          )

      new_batch = ReadingBatch.objects.create(
          name=name,
          token=name,
          include_telecontrol=source_batch.include_telecontrol,
          include_manual=source_batch.include_manual,
          status=ReadingBatchStatus.objects.filter(is_default=True).first(),
      )
      new_batch.fix_meters.set(Meter.objects.filter(id__in=meter_ids))

      return Response(
          {
              'id': new_batch.id,
              'name': new_batch.name,
              'num_meters': len(meter_ids),
              'num_supply_points': missing_supply_points.count(),
          },
          status=status.HTTP_201_CREATED,
      )

  @action(detail=True, methods=['get'], url_path='download')
  def download(self, request, pk=None):
      reading_batch = ReadingBatch.objects.filter(pk=pk).first()
      if not reading_batch:
          return Response(None, status=status.HTTP_404_NOT_FOUND)
      self.check_object_permissions(request, reading_batch)
      raw = request.query_params.get("export_format") or request.query_params.get("file_format")
      if raw is None:
          fmt_q = (request.query_params.get("format") or "").strip().lower()
          if fmt_q in self._download_file_formats:
              raw = fmt_q
      file_format = (raw or "csv").strip().lower()
      if file_format not in self._download_file_formats:
          return Response(
              {
                  "detail": "Invalid export format; use csv, xls, or xlsx "
                  "(?export_format=, ?file_format=, or ?format= for those three only)."
              },
              status=status.HTTP_400_BAD_REQUEST,
          )
      task = export_reading_batch_task.delay(reading_batch.id, file_format=file_format)
      return Response(
          {"task_id": task.id, "status": "pending", "message": "Reading batch export in progress", "format": file_format},
          status=status.HTTP_202_ACCEPTED,
      )
      
  def get_permissions(self):
      if self.action == 'permissions':
          return [IsAuthenticated()]
      return super().get_permissions()