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
from django.utils import timezone
from billing.models import Invoice
from contract.models import ContractUseType, Variable
from coredata.models import ConfigProject
from service.models import SupplyPoint
from service.serializers.supply_point_serializer import SupplyPointListSerializer
from claimrequest.models import ClaimRequest, ClaimRequestPayment, VulnerabilityRequest
from statistics.utils.report_service import delete_file_later


TRUE_VALUES = {'1', 'true', 'si', 'sí', 's', 'yes', 'y'}


def split_supply_address(address):
    # Carrer sense el tipus de via, i el municipi en una columna a part
    if not address:
        return {'street': '', 'number': '', 'floor_door': '', 'city': ''}
    street = ''
    if address.street:
        street = address.street.name or ''
        if address.street.name_2:
            street = f"{street} / {address.street.name_2}"
    number = str(address.street_number) if address.street_number else ''
    floor_door = '-'.join([str(p) for p in (address.floor, address.door) if p])
    extra_parts = [
        str(address.building) if address.building else '',
        f"Esc. {address.stair}" if address.stair else '',
        floor_door,
        (address.address_extra or '').strip(),
    ]
    city = str(address.city) if address.city else (address.city_name or '')
    return {
        'street': street.strip(),
        'number': number if number != 'None' else '',
        'floor_door': ' '.join([p for p in extra_parts if p]),
        'city': city,
    }


def contract_variables_by_contract(contract_ids, today=None):
    # Variables actives i vigents dels contractes, d'un sol cop (sense N+1).
    # No es mira si el tipus està actiu: un tipus desactivat només deixa de
    # sortir per a variables noves, però les que ja tenen els contractes compten.
    # Es mostren les marques (booleans certs), les de text i les de vulnerabilitat;
    # les numèriques i de data de càlcul (m3, unitats...) no aporten res a l'Excel.
    today = today or timezone.localdate()
    variables = (
        Variable.objects.filter(
            contract_id__in=contract_ids,
            is_active=True,
            type__isnull=False,
        )
        .filter(Q(start_at__isnull=True) | Q(start_at__lte=today))
        .filter(Q(end_at__isnull=True) | Q(end_at__gte=today))
        .select_related('type')
        .order_by('type__position', 'type__token', 'id')
    )
    result = {}
    for variable in variables:
        var_type = variable.type
        value = (variable.value or '').strip()
        label = var_type.token or var_type.name or ''
        if not label:
            continue
        if var_type.data_type == 'bool':
            if value.lower() not in TRUE_VALUES:
                continue
            display = label
        elif var_type.data_type == 'char' or var_type.is_vulnerable:
            if not value:
                continue
            display = f"{label}: {value}"
        else:
            continue
        displays = result.setdefault(variable.contract_id, [])
        if display not in displays:
            displays.append(display)
    return {contract_id: ', '.join(displays) for contract_id, displays in result.items()}

class ClaimRequestExcelGenerateViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = ClaimRequest.objects.all().order_by('-created_at')
    def get(self, request, id, *args, **kwargs):
        print("Customer Excel File Generation View")
        claim_request = get_object_or_404(ClaimRequest, id=id)
        file_name = f"{claim_request.token}.csv"
        
        domestic_use_value = ConfigProject.objects.get(token="contract_domestic_use_type_token").value or ""
        # Admet diversos tokens d'ús domèstic separats per "|"
        domestic_use_tokens = [t.strip() for t in domestic_use_value.split("|") if t.strip()]
        paid_payment_token = ConfigProject.objects.get(token="payment_status_paid_token").value
        claim_payments = ClaimRequestPayment.objects.filter(
            claim_request=claim_request,
            is_excluded=False,
            contract__use_type__token__in=domestic_use_tokens,
            )
        contracts = list({cp.contract_id: cp.contract for cp in claim_payments.select_related(
            'contract__supply_point_default__address__street',
            'contract__supply_point_default__address__street_number__number_type',
            'contract__supply_point_default__address__city',
        ) if cp.contract_id}.values())
        variables_by_contract = contract_variables_by_contract([contract.id for contract in contracts])
        
        persons = []
        with override(settings.LANGUAGE_CODE):
            for contract in contracts:
                supply_point = contract.supply_point_default
                contract_claim_payments = claim_payments.filter(contract=contract, payment__isnull=False).exclude(payment__status__token=paid_payment_token).distinct()
                last_vulnerability_request = VulnerabilityRequest.objects.filter(contract=contract).order_by('-created_at').first()
                person = contract.tenant if contract.tenant and contract.holder.is_juridic else contract.holder
                address = split_supply_address(supply_point.address if supply_point else None)
                person = {
                    _("Contracte"): contract.token,
                    _("Tipus d'ús"): contract.use_type.name,
                    _("NIF"): person.token,
                    _("Affected"): person.name + ' ' + person.surname,
                    _("Carrer"): address['street'],
                    _("Número"): address['number'],
                    _("Pis-porta"): address['floor_door'],
                    _("Municipi"): address['city'],
                    _("Variables"): variables_by_contract.get(contract.id, ''),
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
    

    