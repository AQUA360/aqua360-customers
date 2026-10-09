from django_filters import rest_framework as filters

from coredata.models import PersonObservation

class PersonObservationFilter(filters.FilterSet):
    person_id = filters.CharFilter(field_name='person__id', lookup_expr='exact')

    class Meta:
        model = PersonObservation
        fields = ['person']