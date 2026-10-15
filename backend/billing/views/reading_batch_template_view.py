from rest_framework.decorators import action
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from billing.filter.invoice_filter import InvoiceFilter
from billing.models import ReadingBatchTemplate
from billing.serializers.reading_batch_serializer import ReadingBatchTemplateSerializer
from billing.permissions import ReadingPermission
from billing.utils.reading_batch_service import get_meters_from_file
class ReadingBatchTemplateViewSet(viewsets.ModelViewSet):
  """
  API endpoint that allows reading batches to be viewed or edited.
  """
  queryset = ReadingBatchTemplate.objects.all().filter()
  permission_classes = [IsAuthenticated, ReadingPermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  # filterset_class = InvoiceFilter
  search_fields = ['token','name']
  ordering_fields = ['token','name']
  
  def get_serializer_class(self):
    
    if self.request.method in ['GET']:
        if self.action == 'list':  
            return ReadingBatchTemplateSerializer
        elif self.action == 'retrieve':
            return ReadingBatchTemplateSerializer
    return ReadingBatchTemplateSerializer
  
  def get_queryset(self):
    queryset = super().get_queryset()
    # Filtres opcionals per a selectors (p. ex. reclamació d'impagats):
    # plantilles amb rutes de les zones indicades i/o només les que tenen rutes.
    route_zone = self.request.query_params.get('route_zone')
    if route_zone:
      queryset = queryset.filter(routes__route_zone__id__in=route_zone.split(',')).distinct()
    if self.request.query_params.get('has_routes') == 'true':
      queryset = queryset.filter(routes__isnull=False).distinct()
    return queryset

  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context

  @action(detail=False, methods=['post'], url_path='load-batch-template-by-file')
  def load_batch_template_by_file(self, request):
      try:
          file = request.data.get('file', None)
          meters, readings, not_found_meters = get_meters_from_file(file)
          return Response({"meters": meters, "readings": readings, "not_found_meters": not_found_meters}, status=status.HTTP_200_OK)
      except Exception as e:
          return Response(
              {"error": str(e)}, 
              status=status.HTTP_500_INTERNAL_SERVER_ERROR
          )