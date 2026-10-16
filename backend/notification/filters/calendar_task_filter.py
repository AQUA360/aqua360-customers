from django_filters import rest_framework as filters
from django.utils import timezone
from ..models import CalendarTask
from django.db.models import Q

class CalendarTaskFilter(filters.FilterSet):

    year = filters.NumberFilter(method='filter_year')
    month = filters.NumberFilter(method='filter_month')
    set_date = filters.DateFilter(field_name='set_date', lookup_expr='exact')
    date_from = filters.DateFilter(field_name='set_date', lookup_expr='gte')
    date_to = filters.DateFilter(field_name='set_date', lookup_expr='lte')
    task_done = filters.BooleanFilter(field_name='task_done')
    # 'me': només les assignades a l'usuari; 'all_users': només les de tothom
    assigned = filters.CharFilter(method='filter_assigned')
    overdue = filters.BooleanFilter(method='filter_overdue')
    source = filters.CharFilter(field_name='source', lookup_expr='exact')
    source_key = filters.CharFilter(field_name='source_key', lookup_expr='exact')

    contract = filters.CharFilter(field_name='contract__id', lookup_expr='exact')
    order = filters.CharFilter(field_name='order__id', lookup_expr='exact')

    class Meta:
        model = CalendarTask
        fields = ['contract', 'order', 'year', 'month', 'set_date']

    def filter_year(self, queryset, name, value):
        if value:
            return queryset.filter(set_date__year=value)
        return queryset

    def filter_month(self, queryset, name, value):
        if value:
            return queryset.filter(set_date__month=value)
        return queryset

    def filter_assigned(self, queryset, name, value):
        if value == 'me':
            return queryset.filter(user=self.request.user)
        if value == 'all_users':
            return queryset.filter(user__isnull=True)
        return queryset

    def filter_overdue(self, queryset, name, value):
        overdue = Q(task_done=False, set_date__lt=timezone.localdate())
        return queryset.filter(overdue) if value else queryset.exclude(overdue)
