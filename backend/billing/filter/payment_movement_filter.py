from django_filters import rest_framework as filters
from ..models import PaymentMovement

class PaymentMovementFilter(filters.FilterSet):
    payment = filters.CharFilter(field_name='payment_id', lookup_expr='exact')
    
    class Meta:
        model = PaymentMovement
        fields = ['payment']