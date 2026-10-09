from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import Invoice

class InvoiceBudgetView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Invoice.objects.all()

    def delete(self, request, id, *args, **kwargs):
        try:
            budget = Invoice.objects.get(id=id)
            if budget.payments.count() > 0:
                return Response({"error": "Budget record has payments"}, status=status.HTTP_400_BAD_REQUEST)
            budget.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Invoice.DoesNotExist:
            return Response({"error": "Budget record not found"}, status=status.HTTP_404_NOT_FOUND)
