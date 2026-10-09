from django_filters import rest_framework as filters
from ..models import BonificationTypeDocumentationType

class BonificationTypeDocumentationTypeFilter(filters.FilterSet):
    bonification_type_id = filters.CharFilter(field_name='bonification_type__id', lookup_expr='exact')

    class Meta:
        model = BonificationTypeDocumentationType
        fields = ['bonification_type']
