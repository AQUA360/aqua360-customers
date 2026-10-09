from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from billing.models import ReadingRoute
from billing.serializers.reading_route_serializer import ReadingRouteSerializer, ReadingRouteMinimalSerializer
from billing.permissions import ReadingPermission
class ReadingRouteViewSet(viewsets.ModelViewSet):
  """
  API endpoint that allows reading batches to be viewed or edited.
  """
  queryset = ReadingRoute.objects.all().filter(is_active=True).order_by('token')
  permission_classes = [IsAuthenticated, ReadingPermission]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  search_fields = ['token','name']
  ordering_fields = ['token','name']
  
  def get_serializer_class(self):
    if self.request.method in ['GET']:
        if self.action == 'list':  # Corresponds to GET / (list view)
            return ReadingRouteMinimalSerializer
        elif self.action == 'retrieve':  # Corresponds to GET /id (detail view)
            return ReadingRouteSerializer
    return ReadingRouteMinimalSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context