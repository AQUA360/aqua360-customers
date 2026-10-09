from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from coredata.models import PersonObservation
from coredata.serializers import PersonObservationSerializer
from coredata.filters.person_observation_filter import PersonObservationFilter
from coredata.permissions import PersonPermission
class PersonObservationViewSet(viewsets.ModelViewSet):
    
    queryset = PersonObservation.objects.all().filter(is_active=True)
    serializer_class = PersonObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = PersonObservationFilter
    permission_classes = [IsAuthenticated, PersonPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)