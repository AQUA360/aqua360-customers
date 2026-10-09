from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from service.models import CompanyConfigEmail 
from service.serializers.value_objects_serializer import CompanyConfigEmailSerializer
from rest_framework.response import Response
from rest_framework import status
from service.permissions import CompanyPermission

class CompanyConfigEmailViewSet(viewsets.ModelViewSet):
    queryset = CompanyConfigEmail.objects.all().order_by('token')
    serializer_class = CompanyConfigEmailSerializer
    permission_classes = [IsAuthenticated, CompanyPermission]
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)

