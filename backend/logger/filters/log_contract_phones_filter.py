from django_filters import rest_framework as filters

from logger.models import LogContractPhones


class LogContractPhonesFilter(filters.FilterSet):
    object = filters.NumberFilter(field_name='object__id')

    class Meta:
        model = LogContractPhones
        fields = ['object', 'timestamp']
