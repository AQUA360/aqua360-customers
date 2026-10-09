from django_filters import rest_framework as filters
from ..models import GeneralPaymentSepaDocument

class GeneralPaymentSepaDocumentFilter(filters.FilterSet):
    general_payment = filters.CharFilter(field_name='general_payment_id', lookup_expr='exact')
    
    class Meta:
        model = GeneralPaymentSepaDocument
        fields = ['general_payment']