from django_filters import rest_framework as filters
from service.models import Cluster, ClusterNozzle, Route, SupplyPoint, RoutePosition, Meter
from django.db.models import Q


class ClusterNozzleFilter(filters.FilterSet):
    cluster = filters.NumberFilter(field_name='cluster__id', lookup_expr='exact')
    class Meta:
        model = ClusterNozzle
        fields = ['cluster']