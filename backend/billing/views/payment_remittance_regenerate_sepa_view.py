from datetime import datetime
from django.http import JsonResponse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

from billing.models import PaymentRemittance, PaymentRemittanceStatus
from coredata.models import ConfigProject


class PaymentRemittanceRegenerateSepaView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = PaymentRemittance.objects.all()
    
    def post(self, request, id, *args, **kwargs):
        """
        Regenera el document SEPA d'un PaymentRemittance existent.
        
        Endpoint: POST /billing/payment-remitance/<id>/sepa-document-generate
        
        Opcionalment pot rebre:
        - send_date: Data d'enviament (format: 'YYYY-MM-DD')
        """
        try:
            # Obtenir el PaymentRemittance
            payment_remittance = PaymentRemittance.objects.get(id=id)
        except PaymentRemittance.DoesNotExist:
            return JsonResponse(
                {"error": f"PaymentRemittance amb ID {id} no existeix."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Obtenir els payments associats
        payments = payment_remittance.payments.all()
        
        if not payments.exists():
            return JsonResponse(
                {"error": "El PaymentRemittance no té cap payment associat."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Obtenir el company_bank
        if not payment_remittance.company_bank:
            return JsonResponse(
                {"error": "El PaymentRemittance no té cap company_bank associat."},
                status=status.HTTP_400_BAD_REQUEST
            )

        send_date = request.data.get("send_date", None)
        if send_date:
            try:
                datetime.strptime(send_date, "%Y-%m-%d")
            except Exception:
                return JsonResponse(
                    {"error": "send_date ha d'estar en format 'YYYY-MM-DD'."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        payment_ids = list(payments.values_list("id", flat=True))

        from billing.tasks import regenerate_sepa_file

        processing_token = ConfigProject.objects.get(
            token="payment_remittance_status_processing_token"
        ).value
        processing_status = PaymentRemittanceStatus.objects.get(token=processing_token)

        task = regenerate_sepa_file.delay(payment_remittance.id, payment_ids, send_date)
        payment_remittance.task_id = task.id
        payment_remittance.status = processing_status
        payment_remittance.pending_changes = True
        payment_remittance.save(update_fields=["task_id", "status", "pending_changes"])

        return JsonResponse({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)
