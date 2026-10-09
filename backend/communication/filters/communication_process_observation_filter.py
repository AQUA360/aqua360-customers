from django_filters import rest_framework as filters
from communication.models import CommunicationProcessObservation

class CommunicationProcessObservationFilter(filters.FilterSet):
    process = filters.CharFilter(field_name='process__id', lookup_expr='exact')

    class Meta:
        model = CommunicationProcessObservation
        fields = ['process']