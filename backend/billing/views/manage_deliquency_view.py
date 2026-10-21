import json

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.views import APIView

from billing.models import Invoice
from billing.tasks import manage_deliquency


class ManageDeliquencyViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all().order_by('-created_at')

    def post(self, request, *args, **kwargs):
        payload = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
        payload = json.loads(json.dumps(payload, default=str))
        task = manage_deliquency.delay(payload, request.user.id if request.user else None)
        return Response({"task_id": task.id}, status=status.HTTP_200_OK)
