from django_filters import rest_framework as filters
from ..models import Incident
from django.db.models import F, Q
from django.utils import timezone

class IncidentFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    
    contract = filters.CharFilter(field_name='contract__id', lookup_expr='exact')
    order = filters.CharFilter(method='filter_order')
    invoice = filters.CharFilter(field_name='invoice__id', lookup_expr='exact')
    commitment_deposit = filters.CharFilter(field_name='commitment_deposit__id', lookup_expr='exact')
    supply_point = filters.CharFilter(field_name='supply_point__id', lookup_expr='exact')
    cluster = filters.CharFilter(field_name='cluster__id', lookup_expr='exact')
    incident_type = filters.CharFilter(method='filter_incident_type')
    exploitation = filters.NumberFilter(method='filter_exploitation')
    status = filters.BaseInFilter(field_name='status__id', lookup_expr='in')
    supply_cut = filters.NumberFilter(field_name='supply_cut__id', lookup_expr='exact')
    assigned_to = filters.NumberFilter(field_name='assigned_to__id', lookup_expr='exact')
    created_by = filters.NumberFilter(field_name='created_by__id', lookup_expr='exact')
    assigned_to_me = filters.BooleanFilter(method='filter_assigned_to_me')
    overdue = filters.BooleanFilter(method='filter_overdue')
    channel = filters.BaseInFilter(field_name='channel__id', lookup_expr='in')
    closed_out_of_term = filters.BooleanFilter(method='filter_closed_out_of_term')
    created_from = filters.DateFilter(field_name='created_at__date', lookup_expr='gte')
    created_to = filters.DateFilter(field_name='created_at__date', lookup_expr='lte')

    class Meta:
        model = Incident
        fields = ['search', 'contract', 'invoice', 'incident_type', 'commitment_deposit', 'order', 'supply_point', 'cluster', 'status',
                  'supply_cut', 'assigned_to', 'created_by', 'assigned_to_me', 'overdue', 'channel', 'closed_out_of_term',
                  'created_from', 'created_to']
   
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(token__icontains=value) |
            Q(name__icontains=value) |
            Q(description__icontains=value) |
            Q(contract__token__icontains=value) |
            Q(contract__holder__token__icontains=value) |
            Q(contract__tenant__token__icontains=value) |
            Q(contract__owner__token__icontains=value) |
            Q(invoice__token__icontains=value) |
            Q(invoice__customer_final__icontains=value) |
            Q(commitment_deposit__token__icontains=value) |
            Q(order_incident__token__icontains=value) |
            Q(order_incident__supply_point__token__icontains=value) |
            Q(supply_point__token__icontains=value) |
            Q(cluster__token__icontains=value)
        )
    
    def filter_order(self, queryset, name, value):
        # Incidències vinculades a l'ordre: les que la referencien (order_incident)
        # i la que l'ha originada (Order.incident)
        if value:
            return queryset.filter(
                Q(order_incident__id=value) |
                Q(orders__id=value)
            ).distinct()
        return queryset

    def filter_assigned_to_me(self, queryset, name, value):
        user = getattr(self.request, 'user', None)
        if value and user and user.is_authenticated:
            return queryset.filter(assigned_to=user)
        return queryset

    def filter_overdue(self, queryset, name, value):
        # Vençudes: pendents (no tancades) amb la data de venciment passada
        if value:
            from notification.utils.incident_utils import pending_incidents
            return pending_incidents(queryset).filter(due_at__lt=timezone.now(), paused_at__isnull=True)
        return queryset

    def filter_closed_out_of_term(self, queryset, name, value):
        # Tancades després de la data límit
        if value:
            return queryset.filter(closed_at__isnull=False, due_at__isnull=False, closed_at__gt=F('due_at'))
        return queryset

    def filter_incident_type(self, queryset, name, value):
        if value:
            value_ids = value.split(',')
            return queryset.filter(type__id__in=value_ids)
        return queryset
    
    def filter_exploitation(self, queryset, name, value):
        if value:
            return queryset.filter(
                Q(contract__supply_point_default__connection__exploitation__id=value) |
                Q(invoice__exploitation__id=value) |
                Q(commitment_deposit__contract__supply_point_default__connection__exploitation__id=value) |
                Q(order_incident__contract__supply_point_default__connection__exploitation__id=value) |
                Q(order_incident__contract_request__supply_point_default__connection__exploitation__id=value) |
                Q(order_incident__supply_point__connection__exploitation__id=value) |
                Q(order_incident__connection__exploitation__id=value) |
                Q(order_incident__connection_request__exploitation__id=value) |
                Q(order_incident__claim_request__payments__contract__supply_point_default__connection__exploitation__id=value) |
                Q(supply_point__connection__exploitation__id=value) |
                Q(cluster__connection__exploitation__id=value)
            ).distinct()
        return queryset
    
  