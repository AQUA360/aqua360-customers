# coredata/views/person_contact_view.py

from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from coredata.models import (Person, PersonContact, Bank)
from coredata.serializers import (PersonSerializer, PersonContactSerializer, PersonContactSaveSerializer)
from coredata.permissions import PersonPermission
from coredata.filters.person_contact_filter import PersonContactFilter

class PersonContactViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows PersonContact to be viewed or edited.
    """
    queryset = PersonContact.objects.all().order_by('-id')
    permission_classes = [IsAuthenticated, PersonPermission]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_class = PersonContactFilter
    search_fields = ['phone', 'email', 'role']
    ordering_fields = ['id', 'phone', 'email', 'role']

    
    def get_serializer_class(self):
        if self.request.method in ['GET']:
            return PersonContactSerializer
        return PersonContactSaveSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        instance = serializer.instance
        read_serializer = PersonContactSerializer(instance, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = PersonContactSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')