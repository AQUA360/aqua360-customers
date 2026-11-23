from django_filters import rest_framework as filters

from coredata.models import PersonAnomaly


class PersonAnomalyFilter(filters.FilterSet):
    person_id = filters.NumberFilter(field_name='person__id', lookup_expr='exact')

    class Meta:
        model = PersonAnomaly
        fields = ['person']
