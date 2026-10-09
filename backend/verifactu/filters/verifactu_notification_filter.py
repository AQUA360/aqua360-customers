from django_filters import rest_framework as filters
from ..models import VerifactuNotification


class VerifactuNotificationFilter(filters.FilterSet):
    batch_id = filters.NumberFilter(field_name='batch__id', lookup_expr='exact')
    
    class Meta:
        model = VerifactuNotification
        fields = ['batch_id']

