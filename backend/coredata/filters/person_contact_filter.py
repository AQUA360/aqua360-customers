from django_filters import rest_framework as filters
from coredata.models import PersonContact

class PersonContactFilter(filters.FilterSet):
    person = filters.CharFilter(field_name='person__id', lookup_expr='exact')

    class Meta:
        model = PersonContact
        fields = ['person']
