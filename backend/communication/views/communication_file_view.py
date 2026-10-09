from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend

from django.db.models import Prefetch, F, CharField, Value
from django.db.models.functions import Concat

from django_filters.rest_framework import DjangoFilterBackend

from coredata.utils.name_utils import generate_token

from communication.models import Communication, CommunicationFile
from communication.serializers.value_objects_serializer import CommunicationFileSerializer
from communication.filters.communication_file_filter import CommunicationFileFilter
from communication.permissions import CommunicationPermission
from communication.utils.communication_service import get_uploaded_file_from_request, upload_communication_document

class CommunicationFileViewSet(viewsets.ModelViewSet):
    queryset = CommunicationFile.objects.all().filter(is_active=True).order_by('id')
    permission_classes = [IsAuthenticated, CommunicationPermission]
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CommunicationFileFilter
    search_fields = ['type','file']
    ordering_fields = ['type','file']
    
    def get_serializer_class(self):
        return CommunicationFileSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        # Get communication ID
        communication_id = request.data.get('communication')
        if not communication_id:
            return Response(
                {"error": "El camp 'communication' és obligatori"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            communication = Communication.objects.get(id=communication_id)
        except Communication.DoesNotExist:
            return Response(
                {"error": f"La comunicació amb ID {communication_id} no existeix"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get file using helper function
        uploaded_file = get_uploaded_file_from_request(request, 'document')
        if not uploaded_file:
            return Response(
                {"error": "El camp 'document' és obligatori"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Upload document and create CommunicationFile using helper function
        try:
            comm_file = upload_communication_document(uploaded_file, communication, is_letter=False)
        except Exception as e:
            return Response(
                {"error": f"Error en pujar el document: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Return the created CommunicationFile using serializer
        read_serializer = CommunicationFileSerializer(comm_file, context=self.get_serializer_context())
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers, content_type='application/json')

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        instance = serializer.instance
        read_serializer = CommunicationFileSerializer(instance, context=self.get_serializer_context())
        return Response(read_serializer.data, status=status.HTTP_200_OK, content_type='application/json')