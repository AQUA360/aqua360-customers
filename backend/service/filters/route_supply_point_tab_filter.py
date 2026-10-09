from django_filters import rest_framework as filters

from service.models import SupplyPoint


class RouteSupplyPointTabFilter(filters.FilterSet):
    status = filters.CharFilter(method='filter_status')
    contract_status = filters.CharFilter(method='filter_contract_status')

    class Meta:
        model = SupplyPoint
        fields = ['status', 'contract_status']

    def filter_status(self, queryset, name, value):
        if value:
            status_values = [v.strip() for v in value.split(',') if v.strip()]
            if status_values:
                return queryset.filter(status__id__in=status_values)
        return queryset

    def filter_contract_status(self, queryset, name, value):
        if value:
            status_values = [v.strip() for v in value.split(',') if v.strip()]
            if status_values:
                return queryset.filter(contracts__status_id__in=status_values).distinct()
        return queryset
