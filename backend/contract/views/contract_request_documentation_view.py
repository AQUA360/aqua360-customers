from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat


from django_filters.rest_framework import DjangoFilterBackend


from contract.filters.contract_request_documentation_filter import ContractRequestDocumentationFilter
from contract.models import (ContractRequestDocumentation)
from contract.serializers.value_objects_serializer import (ContractRequestDocumentationSerializer,ContractRequestDocumentationSaveSerializer)
from contract.permissions import ContractRequestPermission
class ContractRequestDocumentationViewSet(viewsets.ModelViewSet):
    queryset = ContractRequestDocumentation.objects.all().order_by('id')
    permission_classes = [IsAuthenticated, ContractRequestPermission]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = ContractRequestDocumentationFilter
    search_fields = ['type','file']
    ordering_fields = ['type','file']
    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            return ContractRequestDocumentationSerializer
        return ContractRequestDocumentationSaveSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = ContractRequestDocumentationSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = ContractRequestDocumentationSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')
    
    def perform_destroy(self, instance):
        if instance.file:
            instance.file.is_active = False
            instance.file.save(update_fields=['is_active'])
        super().perform_destroy(instance)