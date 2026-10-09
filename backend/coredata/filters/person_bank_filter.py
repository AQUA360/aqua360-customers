from django_filters import rest_framework as filters
from coredata.models import PersonBank

class PersonBankFilter(filters.FilterSet):
    person = filters.CharFilter(field_name='person__id', lookup_expr='exact')

    class Meta:
        model = PersonBank
        fields = ['person']
