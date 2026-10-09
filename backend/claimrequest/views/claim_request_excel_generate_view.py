import io
from django.conf import settings
from django.db.models import Q
import pandas as pd
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.core.files.storage import default_storage
from rest_framework import status
from django.utils.translation import gettext as _
from django.utils.translation import override
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.core.files.base import ContentFile
from billing.models import Invoice
from contract.models import ContractUseType
from coredata.models import ConfigProject
from service.models import SupplyPoint
from service.serializers.supply_point_serializer import SupplyPointListSerializer
from claimrequest.models import ClaimRequest, ClaimRequestPayment, VulnerabilityRequest
from statistics.utils.report_service import delete_file_later

class ClaimRequestExcelGenerateViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ClaimRequest.objects.all().order_by('-created_at')
    def get(self, request, id, *args, **kwargs):
        print("Customer Excel File Generation View")
        claim_request = get_object_or_404(ClaimRequest, id=id)
        file_name = f"{claim_request.token}.csv"
        
        domestic_use_token = ConfigProject.objects.get(token="contract_domestic_use_type_token").value
        paid_payment_token = ConfigProject.objects.get(token="payment_status_paid_token").value
        claim_payments = ClaimRequestPayment.objects.filter(
            claim_request=claim_request, 
            contract__use_type__token=domestic_use_token,
            )
        contracts = list({cp.contract_id: cp.contract for cp in claim_payments if cp.contract_id}.values())
        
        persons = []
        with override(settings.LANGUAGE_CODE):
            for contract in contracts:
                supply_point = contract.supply_point_default
                contract_claim_payments = claim_payments.filter(contract=contract).exclude(payment__status__token=paid_payment_token).distinct()
                last_vulnerability_request = VulnerabilityRequest.objects.filter(contract=contract).order_by('-created_at').first()
                person = contract.tenant if contract.tenant and contract.holder.is_juridic else contract.holder
                person = {
                    _("Contracte"): contract.token,
                    _("Tipus d'ús"): contract.use_type.name,
                    _("NIF"): person.token,
                    _("Affected"): person.name + ' ' + person.surname,
                    _("Adreça subm."): str(supply_point.address),
                    _("REBUTS").capitalize(): contract_claim_payments.count(),
                    _("Deute Pendent"): str(sum([claim_payment.payment.amount for claim_payment in contract_claim_payments])).replace('.', ','),
                    _("Last vuln data"): last_vulnerability_request.request_at if last_vulnerability_request and last_vulnerability_request.request_at else last_vulnerability_request.created_at if last_vulnerability_request else "",
                }
                persons.append(person)


        csv_data = pd.DataFrame(persons)

        csv_buffer = io.StringIO()
        csv_data.to_csv(csv_buffer, sep=";", index=False)
        file_bytes = ("\ufeff" + csv_buffer.getvalue()).encode("utf-8")

        temp_rel_path = f"tmp/CLAIM/{file_name}"
        saved_path = default_storage.save(temp_rel_path, ContentFile(file_bytes))
        file_url = request.build_absolute_uri(default_storage.url(saved_path))

        delete_file_later(saved_path, delay_seconds=20)

        return JsonResponse({"file_url": file_url}, status=status.HTTP_200_OK)
    

    