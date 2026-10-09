from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.core.files.base import ContentFile
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
import threading

from billing.models import Invoice
from billing.utils.payment_proof_service import (
    get_payments_from_request_data,
    render_payment_proof_pdf,
)


class PaymentProofDownloadViewSet(APIView):
    permission_classes = [IsAuthenticated]
    queryset = Invoice.objects.all().order_by('-created_at')

    def post(self, request, *args, **kwargs):
        payments = get_payments_from_request_data(request.data)
        if not payments:
            return JsonResponse({'error': 'No payments found'}, status=400)

        payment_date = request.data.get('date', None)
        observation = request.data.get('observation', None)

        try:
            signed_pdf_buffer, pdf_filename = render_payment_proof_pdf(
                payments,
                request,
                payment_date=payment_date,
                observation=observation,
            )
        except ValueError as exc:
            return JsonResponse({'error': str(exc)}, status=400)
        except RuntimeError:
            return JsonResponse({'error': 'PDF generation failed'}, status=500)

        signed_pdf_buffer.seek(0)

        temp_rel_path = f"tmp/payment_proof_docs/{pdf_filename}"
        saved_path = default_storage.save(temp_rel_path, ContentFile(signed_pdf_buffer.getvalue()))
        file_url = request.build_absolute_uri(default_storage.url(saved_path))

        def _delete_later(path: str, delay_seconds: int = 100) -> None:
            def _run():
                try:
                    default_storage.delete(path)
                except Exception:
                    pass
            t = threading.Timer(delay_seconds, _run)
            t.daemon = True
            t.start()

        _delete_later(saved_path, delay_seconds=20)

        return JsonResponse({'pdf_url': file_url})
