from django_filters import rest_framework as filters

from coredata.models import CallRegister


class CallRegisterFilter(filters.FilterSet):
    contract = filters.CharFilter(
        field_name='contract__id',
        lookup_expr='exact'
    )

    person = filters.CharFilter(
        field_name='person_contact__person__id',
        lookup_expr='exact'
    )

    class Meta:
        model = CallRegister
        fields = ['contract', 'person']