import threading

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework.views import APIView

from contract.utils.contract_pdf_service import (
    ContractPdfGenerationError,
    generate_contract_pdf_bytes,
    get_contract_pdf_filename,
)

from ..models import Contract, ContractRequest


class ReportPDFDownloadViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ContractRequest.objects.all().order_by("-created_at")

    def get(self, request, id, *args, **kwargs):
        is_contract = request.query_params.get("is_contract", "false").lower() == "true"
        if is_contract:
            contract_request = Contract.objects.get(id=id)
        else:
            og_instance = get_object_or_404(ContractRequest, id=id)
            try:
                contract_request = Contract.objects.get(contract_request=og_instance)
            except Contract.DoesNotExist:
                contract_request = og_instance

        try:
            pdf_bytes = generate_contract_pdf_bytes(
                contract_request,
                include_requested_at=not is_contract,
                request=request,
            )
        except ContractPdfGenerationError:
            return JsonResponse({"error": "PDF generation failed"}, status=500)

        pdf_filename = get_contract_pdf_filename(contract_request)
        if not is_contract and isinstance(contract_request, ContractRequest):
            contract_request.contract_file_template.save(
                pdf_filename, ContentFile(pdf_bytes)
            )
            file_url = request.build_absolute_uri(
                contract_request.contract_file_template.url
            )
        else:
            temp_rel_path = f"tmp/contract_docs/{pdf_filename}"
            saved_path = default_storage.save(
                temp_rel_path, ContentFile(pdf_bytes)
            )
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

        return JsonResponse({"pdf_url": file_url})
