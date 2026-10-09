from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from coredata.models import (PersonPiggyBankMovement)
from coredata.serializers import PersonPiggyBankMovementSerializer
from coredata.permissions import PersonPermission

class PersonPiggyBankMovementViewSet(viewsets.ModelViewSet):
    queryset = PersonPiggyBankMovement.objects.all().order_by('-amount')
    serializer_class = PersonPiggyBankMovementSerializer
    permission_classes = [IsAuthenticated, PersonPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    
    