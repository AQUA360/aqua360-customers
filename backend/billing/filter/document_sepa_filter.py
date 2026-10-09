from django_filters import rest_framework as filters
from ..models import DocumentSEPA


class DocumentSEPAFilter(filters.FilterSet):
    payment = filters.NumberFilter(
        field_name='lines__payments__id',
        lookup_expr='exact'
    )
    
    class Meta:
        model = DocumentSEPA
        fields = ['payment']

    
   