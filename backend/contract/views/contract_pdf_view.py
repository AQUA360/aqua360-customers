import threading
import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from contract.utils.contract_pdf_service import (
    ContractPdfGenerationError,
    generate_contract_pdf_bytes,
    get_contract_pdf_filename,
)

from ..models import Contract, ContractRequest
from ..permissions import ContractPdfPermission, can_read


class ReportPDFDownloadViewSet(APIView):
    permission_classes = [IsAuthenticated, ContractPdfPermission]
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
            # Es descarrega el contracte: cal poder-lo veure, no només la sol·licitud.
            if isinstance(contract_request, Contract) and not can_read(request.user, "contract.view_contract"):
                raise PermissionDenied()

        try:
            pdf_bytes = generate_contract_pdf_bytes(
                contract_request,
                include_requested_at=not is_contract,
                request=request,
            )
        except ContractPdfGenerationError:
            return JsonResponse({"error": "PDF generation failed"}, status=500)

        pdf_filename = get_contract_pdf_filename(contract_request)
        # El PDF generat queda desat a la sol·licitud (l'assistent el fa servir per
        # avançar de pas): només si l'usuari la pot modificar. Si no, fitxer temporal.
        if (
            not is_contract
            and isinstance(contract_request, ContractRequest)
            and request.user.has_perm("contract.change_contractrequest")
        ):
            contract_request.contract_file_template.save(
                pdf_filename, ContentFile(pdf_bytes)
            )
            file_url = request.build_absolute_uri(
                contract_request.contract_file_template.url
            )
        else:
            # Carpeta aleatòria: /media/ només demana sessió i el nom no s'ha de poder endevinar.
            temp_rel_path = f"tmp/contract_docs/{uuid.uuid4().hex}/{pdf_filename}"
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
