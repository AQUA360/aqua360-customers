from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from contract.models import PaymentType
from contract.serializers.value_objects_serializer import PaymentTypeSerializer

class PaymentTypeViewSet(viewsets.ModelViewSet):
    queryset = PaymentType.objects.all().order_by('position')
    serializer_class = PaymentTypeSerializer
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
