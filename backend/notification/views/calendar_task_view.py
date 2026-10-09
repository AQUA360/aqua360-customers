from rest_framework import viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import Q

from notification.filters.calendar_task_filter import CalendarTaskFilter
from notification.serializers.calendar_task_serializer import CalendarTaskSerializer


from ..models import CalendarTask

class CalendarTaskViewSet(viewsets.ModelViewSet):
  queryset = CalendarTask.objects.all().filter(is_active=True).order_by('-created_at')
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = CalendarTaskFilter
  search_fields = ['token','name']
  ordering_fields = ['token','name']
  
  def get_queryset(self):
    qs = super().get_queryset()
    user = self.request.user

    # Show notifications where user is None (public) or assigned to the current user
    return qs.filter(Q(user=user) | Q(user__isnull=True))
  
  def get_serializer_class(self):
    return CalendarTaskSerializer
  
  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context