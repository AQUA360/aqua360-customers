from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from billing.filter.commitment_deposit_observation_filter import CommitmentDepositObservationFilter
from billing.permissions import CommitmentDepositPermission
from billing.serializers.commitment_deposit_serializer import CommitmentDepositObservationSerializer

from billing.models import CommitmentDepositObservation


class CommitmentDepositObservationViewSet(viewsets.ModelViewSet):
    queryset = CommitmentDepositObservation.objects.all().filter(is_active=True)
    serializer_class = CommitmentDepositObservationSerializer
    filter_backends = (DjangoFilterBackend,)
    filterset_class = CommitmentDepositObservationFilter
    permission_classes = [IsAuthenticated, CommitmentDepositPermission]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.is_active = False
        instance.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


