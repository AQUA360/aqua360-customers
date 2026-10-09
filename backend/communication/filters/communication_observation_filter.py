from django_filters import rest_framework as filters
from communication.models import CommunicationObservation

class CommunicationObservationFilter(filters.FilterSet):
    communication = filters.CharFilter(field_name='communication__id', lookup_expr='exact')

    class Meta:
        model = CommunicationObservation
        fields = ['communication']