from django_filters import rest_framework as filters
from coredata.models import PersonCNAE

class PersonCnaeFilter(filters.FilterSet):
    person = filters.CharFilter(field_name='person__id', lookup_expr='exact')

    class Meta:
        model = PersonCNAE
        fields = ['person']
