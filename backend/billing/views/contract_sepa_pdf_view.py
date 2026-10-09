from datetime import datetime
from io import BytesIO

from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from xhtml2pdf import pisa

from billing.models import GeneralPaymentSepaDocument, PersonBank
from contract.models import Contract, ContractRequest
from coredata.models import Address, Person
from coredata.serializers import PersonAddressSerializer, PersonSerializer
from coredata.utils.iban_validator_utils import resolve_account_bic
from documentmanager.utils.sign_certificate_service import sign_pdf
from service.serializers.company_serializer import CompanySerializer


def _resolve_person_bank(request_data, default_person_bank):
    bank_id = request_data.get("bank_id") or request_data.get("person_bank_id")
    if not bank_id:
        return default_person_bank
    person_bank = PersonBank.objects.filter(id=bank_id).first()
    return person_bank or default_person_bank


def _resolve_person(request_data):
    person_id = request_data.get("person_id")
    if not person_id:
        return None
    if isinstance(person_id, int):
        return Person.objects.filter(id=person_id).first()
    if isinstance(person_id, dict):
        token = person_id.get("id")
        if token:
            return Person.objects.filter(token=token).first()
    return None


def _billing_address(holder, holder_person, contract, context):
    if not holder or not holder_person:
        return None

    contract_billing_address_id = contract.address_billing.id if contract.address_billing else None
    if contract_billing_address_id:
        billing_address = next(
            (address for address in holder.get("addresses", []) if address.get("id") == contract_billing_address_id),
            None,
        )
        if billing_address:
            return billing_address

    billing_address = next(
        (address for address in holder.get("addresses", []) if address.get("is_billing")),
        None,
    )
    if billing_address:
        return billing_address

    if contract.address_billing:
        return PersonAddressSerializer(contract.address_billing, context=context).data
    return None


def _debtor_address(billing_address):
    # La representació serialitzada de l'adreça només porta els ids de població/província/país:
    # la plantilla necessita el model per mostrar-ne el nom.
    address = billing_address.get("address") if isinstance(billing_address, dict) else None
    address_id = address.get("id") if isinstance(address, dict) else address
    if not address_id:
        return None
    return Address.objects.select_related("city", "province", "country").filter(id=address_id).first()


def _company_from_contract(contract, context):
    supply_point = contract.supply_point_default
    if (
        supply_point is not None
        and supply_point.connection is not None
        and supply_point.connection.exploitation is not None
        and supply_point.connection.exploitation.company is not None
    ):
        return CompanySerializer(supply_point.connection.exploitation.company, context=context).data
    return None


# Permet personalitzar per client: si existeix contract_sepa_pdf_view_personalized,
# s'usa la seva _company_from_contract en lloc de la d'aquest mòdul.
try:
    from billing.views import contract_sepa_pdf_view_personalized
    if hasattr(contract_sepa_pdf_view_personalized, '_company_from_contract'):
        _company_from_contract = contract_sepa_pdf_view_personalized._company_from_contract
except ImportError:
    pass


def _iban_and_swift(person_bank):
    if person_bank and person_bank.iban:
        iban = "IBAN" + person_bank.iban.upper()
        iban = " ".join(iban[i : i + 4] for i in range(0, len(iban), 4))
    else:
        iban = ""

    # El SWIFT del compte mana; si no n'hi ha, el del catàleg o el registre oficial (mai un BIC endevinat)
    swift = ""
    if person_bank:
        swift = resolve_account_bic(
            person_bank.iban, person_bank.swift, person_bank.bank.bic if person_bank.bank else None
        ) or ""
    return iban, swift


class ContractSepaPDFView(APIView):
    """
    Generate a SEPA mandate PDF for a contract.

    If the contract has a GeneralPayment, the document is stored on it and its
    URL is returned. If the contract has no payment configured, the contract
    holder is used as the person and the generated PDF is returned directly
    (there is no GeneralPayment to persist it on).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, contract_id, *args, **kwargs):
        is_request = str(request.query_params.get("is_request", "")).lower() == "true"
        if is_request:
            # contract_id is treated as a ContractRequest id.
            contract = get_object_or_404(ContractRequest, id=contract_id)
        else:
            contract = get_object_or_404(Contract, id=contract_id)
        general_payment = contract.payment

        default_person_bank = general_payment.IBAN if general_payment and general_payment.IBAN else None
        person_bank = _resolve_person_bank(request.data, default_person_bank)
        context = {"request": request}
        company = _company_from_contract(contract, context)
        holder_person = _resolve_person(request.data) or contract.holder
        holder = PersonSerializer(holder_person, context=context).data if holder_person else None
        if holder and holder_person:
            holder["addresses"] = PersonAddressSerializer(
                holder_person.addresses.all(), many=True, context=context
            ).data

        billing_address = _billing_address(holder, holder_person, contract, context)
        iban, swift = _iban_and_swift(person_bank)
        person_fullname = (
            person_bank.name if person_bank and person_bank.name else holder.get("full_name") if holder else ""
        )
        person_token = (
            person_bank.dni if person_bank and person_bank.dni else holder.get("token") if holder else ""
        )

        html_content = render_to_string(
            "sepa_template.html",
            {
                "iban": iban,
                "swift": swift,
                "now_date": datetime.now().date(),
                "company": company or "",
                "city": (
                    contract.supply_point_default.address.city.name
                    if contract.supply_point_default
                    and contract.supply_point_default.address
                    and contract.supply_point_default.address.city
                    else ""
                ),
                "holder": holder or "",
                "holder_address": billing_address or "",
                "debtor_address": _debtor_address(billing_address),
                "person_fullname": person_fullname or "",
                "person_token": person_token or "",
                "contract": contract,
                "no_sepa": True,
                "data_protection_law_text": company.get("data_protection_law_text") if company else None,
            },
        )

        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
        if pisa_status.err:
            return JsonResponse({"error": "PDF generation failed"}, status=500)

        signed_pdf_buffer = sign_pdf(pdf_buffer, company, "SEPA DIRECT DEBIT", "SEPA")
        pdf_filename = f"SEPA_{contract.token}.pdf"

        if general_payment:
            # Persist the document on the contract's GeneralPayment (reused per payment).
            sepa, _ = GeneralPaymentSepaDocument.objects.get_or_create(general_payment=general_payment)
        else:
            # No payment to attach to: store a standalone document (built from the
            # contract holder). Can't get_or_create on a null OneToOne, so create one.
            sepa = GeneralPaymentSepaDocument.objects.create()
        sepa.template.save(pdf_filename, ContentFile(signed_pdf_buffer.getvalue()))

        file_url = request.build_absolute_uri(sepa.template.url)
        return JsonResponse({"pdf_url": file_url, "sepa_document_id": sepa.id})
