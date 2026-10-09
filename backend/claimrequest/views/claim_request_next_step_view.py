from rest_framework import status
from rest_framework.response import Response
from rest_framework import viewsets
from claimrequest.utils.claim_request_service import process_claim_request_next_step
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from claimrequest.models import ClaimRequest

class ClaimRequestNextStepViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ClaimRequest.objects.all().order_by('-created_at')

    def retrieve(self, request, id=None, *args, **kwargs):
        result = process_claim_request_next_step(id)

        if 'error' in result:
            return Response(
                {'error': result['error']}, status=status.HTTP_400_BAD_REQUEST
            )
        else:
            return Response(result['data'], status=status.HTTP_202_ACCEPTED)