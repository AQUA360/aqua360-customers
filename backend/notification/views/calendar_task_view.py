from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from django.db.models import Count, Q
from django.utils import timezone

from notification.filters.calendar_task_filter import CalendarTaskFilter
from notification.serializers.calendar_task_serializer import CalendarTaskSerializer
from notification.utils.recurrence import stop_from
from pagination.large_pagination import LargeResultsSetPagination


from ..models import CalendarTask

class CalendarTaskViewSet(viewsets.ModelViewSet):
  queryset = CalendarTask.objects.all().filter(is_active=True).order_by('-created_at')
  permission_classes = [IsAuthenticated, DjangoModelPermissions]
  filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
  filterset_class = CalendarTaskFilter
  # El calendari demana un mes o una setmana sencera: sense paginació curta.
  pagination_class = LargeResultsSetPagination
  search_fields = ['token','name','description']
  ordering_fields = ['token','name','set_date','time','created_at']

  def get_queryset(self):
    qs = super().get_queryset().select_related('user', 'contract', 'order__type', 'recurrence')
    user = self.request.user

    # Show notifications where user is None (public) or assigned to the current user
    return qs.filter(Q(user=user) | Q(user__isnull=True))

  def get_serializer_class(self):
    return CalendarTaskSerializer

  def get_serializer_context(self):
    context = super().get_serializer_context()
    context['request'] = self.request
    return context

  def destroy(self, request, *args, **kwargs):
    """Amb `?series=true` en una ocurrència, s'esborren també les pendents posteriors."""
    instance = self.get_object()
    if instance.recurrence and request.query_params.get('series') in ('true', '1'):
      # Una sèrie privada d'un altre usuari no es pot aturar des d'una ocurrència compartida
      if instance.recurrence.user_id not in (None, request.user.id):
        return Response({'detail': 'This series belongs to another user'}, status=status.HTTP_403_FORBIDDEN)
      stop_from(instance.recurrence, instance.set_date, tasks_filter=Q(user=request.user) | Q(user__isnull=True))
      CalendarTask.objects.filter(pk=instance.pk).delete()
      return Response(status=status.HTTP_204_NO_CONTENT)
    return super().destroy(request, *args, **kwargs)

  @action(detail=False, methods=['get'], url_path='summary')
  def summary(self, request):
    """Comptadors per al menú i el dashboard: pendents d'avui i endarrerides."""
    today = timezone.localdate()
    qs = self.get_queryset().filter(task_done=False)
    if request.query_params.get('assigned') == 'me':
      qs = qs.filter(user=request.user)
    counts = qs.aggregate(
      today=Count('id', filter=Q(set_date=today)),
      overdue=Count('id', filter=Q(set_date__lt=today)),
    )
    return Response(counts, status=status.HTTP_200_OK)
