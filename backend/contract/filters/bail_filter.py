from django_filters import rest_framework as filters
from contract.models import Bail
from django.db.models import Q

class BailFilter(filters.FilterSet):
    search = filters.CharFilter(method='filter_search')
    status = filters.CharFilter(method='filter_status')
    exploitation = filters.NumberFilter(field_name='contract__supply_point_default__connection__exploitation__id', lookup_expr='exact')
    contract_status = filters.CharFilter(method='filter_contract_status')
    
    class Meta:
        model = Bail
        fields = ['search', 'status', 'contract_status', 'exploitation']
   
    def filter_search(self, queryset, name, value):
        if not value:
            return queryset

        # Es parteix per espais perque "Nom Cognom" ha de poder creuar els camps
        # name i surname del titular: cada paraula ha de coincidir en algun camp
        # i totes han de coincidir (AND entre paraules, OR entre camps).
        terms = value.split()
        if not terms:
            return queryset

        for term in terms:
            queryset = queryset.filter(
                Q(token__icontains=term) |
                Q(contract__token__icontains=term) |
                Q(contract__holder__name__icontains=term) |
                Q(contract__holder__surname__icontains=term) |
                Q(contract__holder__token__icontains=term) |
                Q(product__name__icontains=term) |
                Q(product__token__icontains=term)
            )
        return queryset
        
    def filter_contract_status(self, queryset, name, value):
        if not value:
            return queryset
        # Accepta una llista separada per comes d'ids (el que envia el frontend)
        # o de tokens, per mantenir compatibilitat amb les crides antigues.
        values = [v.strip() for v in value.split(',') if v.strip()]
        ids = [v for v in values if v.isdigit()]
        tokens = [v for v in values if not v.isdigit()]
        query = Q()
        if ids:
            query |= Q(contract__status__id__in=ids)
        if tokens:
            query |= Q(contract__status__token__in=tokens)
        if not query:
            return queryset
        return queryset.filter(query)
    
    def filter_status(self, queryset, name, value):
        if value:
            status_values = value.split(',')
            return queryset.filter(status__id__in=status_values)
        return queryset
    
  