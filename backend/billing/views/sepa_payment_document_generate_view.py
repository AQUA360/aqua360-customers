from decimal import Decimal
import os
import uuid
import calendar
import json
from datetime import datetime, timedelta, date
from django.conf import settings
from django.utils import timezone
from django.http import FileResponse, JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import Invoice, InvoiceStatus, Payment, PaymentRemittance, PaymentRemittanceStatus, PaymentStatus
from billing.serializers.payment_serializer import PaymentSEPASerializer, PaymentSerializer
from billing.utils.payment_service import get_payment_SEPA_data, log_payment_status
from django.db.models import Sum
import xml.etree.ElementTree as ET
from django.core.files.base import ContentFile
from billing.utils.sepa_file_service import generate_xml, generate_xml_payments
from coredata.models import Bank, ConfigProject
from coredata.utils.iban_validator_utils import validate_iban
from coredata.utils.validators_utils import validate_nif
from documentmanager.utils.main_utils import upload_document
from service.models import Company, CompanyBank, Exploitation
from django.db.models import Q, Count, Exists, OuterRef, Value
from django.db.models.functions import Coalesce
from faker import Faker
fake = Faker()
from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 1000

def filter_payments_by_contracts_with_pending_invoices(payments, keep_only=False):
    """
    Filtra els pagaments segons si el seu contracte té factures pendents de pagar
    (estat `invoice_status_expired_token`, "Vençuda/Impagada"):
      - `keep_only=False` (per defecte): els treu de la remesa. És el filtre que
        redueix el llistat.
      - `keep_only=True`: es queda NOMÉS amb aquests pagaments, per poder-los
        marcar en massa com a exclosos des de `SEPAPaymentInvoicesViewSet.post()`.

    Dos matisos:
      - No hi compten les factures de despeses/recàrrec de devolució per impagat
        (`invoice_return_charge()`): no tenen un `origin` propi, però sempre tenen
        una línia amb la `PriceRate` indicada pel ConfigProject
        `invoice_return_price_rate_token` — el mateix marcador que fa servir
        `claimrequest/tasks.py::_build_claim_request_filters`.
      - No hi compta la factura del propi pagament que s'està remesant: només
        s'exclou si el contracte té ALTRES factures pendents. Així es pot tornar
        a remesar una factura vençuda si és l'únic deute del contracte.

    El contracte del pagament pot venir de la factura, del pla de pagament o del
    propi pagament (rebuts sense factura), per això es comproven les tres vies.
    """
    expired_status_token = ConfigProject.objects.filter(
        token='invoice_status_expired_token'
    ).values_list('value', flat=True).first()
    if not expired_status_token:
        return payments

    # Es resol l'id de l'estat un sol cop: dins de la subconsulta, filtrar per
    # `status_id` estalvia el JOIN amb `billing_invoicestatus` a cada fila.
    expired_status_id = InvoiceStatus.objects.filter(
        token=expired_status_token
    ).values_list('id', flat=True).first()
    if not expired_status_id:
        return payments

    pending_invoices = Invoice.objects.filter(status_id=expired_status_id)

    return_fee_price_rate_token = ConfigProject.objects.filter(
        token='invoice_return_price_rate_token'
    ).values_list('value', flat=True).first()
    if return_fee_price_rate_token:
        # `exclude()` sobre una relació multivaluada genera una subconsulta
        # (factures sense cap línia d'aquesta PriceRate), no duplica files.
        pending_invoices = pending_invoices.exclude(
            line_items__price_rate__token=return_fee_price_rate_token
        )

    pending_invoices = pending_invoices.filter(
        # El contracte del pagament pot venir de la factura, del pla de pagament
        # o del propi pagament (rebuts sense factura). Un sol `EXISTS` amb les
        # tres vies en OR en lloc de tres `EXISTS` per fila.
        Q(contract_id=OuterRef('invoice__contract_id'))
        | Q(contract_id=OuterRef('commitment_deposit__contract_id'))
        | Q(contract_id=OuterRef('contract_id'))
    ).exclude(
        # `Coalesce(..., 0)`: si el pagament no té factura (rebuts de devolució),
        # un `NOT (id = NULL)` deixaria la subconsulta sempre buida i no
        # s'aplicaria el filtre. Amb el 0 la comparació és sempre certa i no
        # s'exclou cap factura pendent del contracte.
        id=Coalesce(OuterRef('invoice_id'), Value(0))
    )

    if keep_only:
        return payments.filter(Exists(pending_invoices))

    return payments.exclude(Exists(pending_invoices))


class RequestData:
    """
    Embolcall minim amb l'atribut `data`, per poder cridar
    `get_sepa_payments_and_batches()` amb un payload derivat (el d'un banc
    concret) en comptes de la request original.
    """

    def __init__(self, data):
        self.data = data


def get_sepa_payments_and_batches(request):
    exploitation = request.data.get('exploitation', None)
    billing = request.data.get('billing', None)
    origin = request.data.get('origin', None)
    search = request.data.get('search', None)
    
    bank_id = request.data.get('selected_bank', None)
    send_date = request.data.get('selected_send_date', None)
    max_total_remittance = request.data.get('maxTotalRemittance', None)
    
    # is_commitment = request.data.get('is_commitment', False)
    selected_payments_type = request.data.get('payments_type', None)
    include_excluded = request.data.get('include_excluded', True)
    only_excluded = request.data.get('only_excluded', False)
    exclude_contracts_with_pending_invoices = request.data.get('exclude_contracts_with_pending_invoices', False)
    only_contracts_with_pending_invoices = request.data.get('only_contracts_with_pending_invoices', False)
    
    contracts = request.data.get('contracts', [])
    invoices = request.data.get('invoices', [])
    commitment = request.data.get('commitment', None)
    
    invoice_statuses = request.data.get('invoice_statuses', [])
    payment_statuses = request.data.get('payment_statuses', [])
    
    send_date_start = request.data.get('send_date_start', None)
    send_date_end = request.data.get('send_date_end', None)
    issue_date_start = request.data.get('issue_date_start', None)
    issue_date_end = request.data.get('issue_date_end', None)
    due_date_start = request.data.get('due_date_start', None)
    due_date_end = request.data.get('due_date_end', None)
    
    excluded_status_tokens = list(
        ConfigProject.objects.filter(
            token__in=[
                "payment_status_payoff_token",
                "payment_status_dropped_token",
                "payment_status_piggy_token",
                "payment_status_cancelled_token",
                "payment_status_irrecoverable_token",
                "payment_status_commitment_token",
                "payment_status_paid_token",
            ]
        ).values_list("value", flat=True)
    )
    
    joined_payment_status_tokens_config = [
        "joined_payment_status_paid_token",
        "joined_payment_status_pending_token",
        "joined_payment_status_expired_token"
    ]
    joined_payment_status_tokens = ConfigProject.objects.filter(token__in=joined_payment_status_tokens_config).values_list('value', flat=True)
    if selected_payments_type == "return":
        filters = Q(payment_type_token="BANK_TRANSFER")
    else:
        filters = Q(payment_type_token="DIRECT_DEBIT")
    
    # If is_commitment is True, we only want commitments.
    # If False, we might want both or just invoices. 
    # Based on user request, it should probably include both if not specified otherwise, 
    # but let's stick to showing commitments if is_commitment=True or if they fit the general filters.
    if selected_payments_type == "commitment":
        filters &= Q(commitment_deposit__isnull=False)
    
    if selected_payments_type == "return":
        filters &= Q(commitment_deposit__isnull=True, invoice__isnull=True)
    
    if exploitation:
        filters &= (
            Q(invoice__exploitation__id=exploitation) | 
            Q(commitment_deposit__contract__supply_point_default__connection__exploitation__id=exploitation) |
            Q(commitment_deposit__invoices__exploitation__id=exploitation) |
            Q(contract__supply_point_default__connection__exploitation__id=exploitation) |
            Q(person__isnull=False)
        )
    
    if origin:
        filters &= Q(invoice__origin__id=origin)
        
    if billing:
        filters &= Q(invoice__billing__id=billing)
        
    if contracts:
        filters &= (Q(invoice__contract__id__in=contracts) | Q(commitment_deposit__contract__id__in=contracts))
        
    if invoices:
        filters &= (Q(invoice__id__in=invoices) | Q(commitment_deposit__invoices__id__in=invoices))
        
    if send_date_start:
        filters &= (Q(invoice__send_at__gte=send_date_start) | Q(due_date__gte=send_date_start))
        
    if send_date_end:
        filters &= (Q(invoice__send_at__lte=send_date_end) | Q(due_date__lte=send_date_end))
        
    if issue_date_start:
        filters &= (Q(invoice__issue_date__gte=issue_date_start) | Q(commitment_deposit__invoices__issue_date__gte=issue_date_start))
        
    if issue_date_end:
        filters &= (Q(invoice__issue_date__lte=issue_date_end) | Q(commitment_deposit__invoices__issue_date__lte=issue_date_end))
        
    if due_date_start:
        filters &= Q(due_date__gte=due_date_start)
        
    if due_date_end:
        filters &= Q(due_date__lte=due_date_end)
        
    if invoice_statuses:
        filters &= Q(invoice__status__id__in=invoice_statuses)
        
    if payment_statuses:
        filters &= Q(status__id__in=payment_statuses)
        
    if commitment:
        filters &= Q(commitment_deposit__id=commitment)

    # Empresa emissora: la remesa d'una empresa no pot arrossegar rebuts d'una
    # altra. L'empresa del rebut es dedueix igual que a
    # `remittance_routing.get_payment_company_id()`: de la factura, de la seva
    # explotacio si la factura no la porta (hi ha clients amb `Invoice.company`
    # buit a quasi totes les factures) i, si no hi ha factura, de l'explotacio
    # del contracte.
    selected_companies = request.data.get('selected_companies') or []
    if not isinstance(selected_companies, (list, tuple)):
        selected_companies = [selected_companies]
    selected_companies = [c for c in selected_companies if c not in (None, "")]
    if selected_companies:
        from_selected_company = (
            Q(invoice__company__id__in=selected_companies)
            | Q(invoice__company__isnull=True, invoice__exploitation__company__id__in=selected_companies)
            | Q(invoice__isnull=True, commitment_deposit__contract__supply_point_default__connection__exploitation__company__id__in=selected_companies)
            | Q(invoice__isnull=True, contract__supply_point_default__connection__exploitation__company__id__in=selected_companies)
        )
        # Els rebuts on l'empresa no es pot determinar de cap manera no
        # s'atribueixen a ningu: si s'exclogessin, les instal·lacions amb aquestes
        # dades incompletes es quedarien sense remesa sense dir-ho.
        without_company = (
            Q(
                invoice__isnull=False,
                invoice__company__isnull=True,
                invoice__exploitation__company__isnull=True,
            )
            | Q(
                invoice__isnull=True,
                commitment_deposit__contract__supply_point_default__connection__exploitation__company__isnull=True,
                contract__supply_point_default__connection__exploitation__company__isnull=True,
            )
        )
        filters &= (from_selected_company | without_company)

    # Restriccions per id de pagament, que fa servir el repartiment per banc de
    # `get_bank_distribution()`: el banc per defecte rep tot el que no s'ha
    # assignat explícitament a un altre banc (`exclude_payment_ids`) i la resta
    # de bancs només el que tenen assignat (`payment_ids`).
    # `payment_ids` buit (llista, no None) ha de donar zero pagaments.
    payment_ids = request.data.get('payment_ids', None)
    if payment_ids is not None:
        filters &= Q(id__in=payment_ids)

    exclude_payment_ids = request.data.get('exclude_payment_ids', None)
    if exclude_payment_ids:
        filters &= ~Q(id__in=exclude_payment_ids)
        
    if search and search != "":
        filters &= (
            Q(token__icontains=search) | 
            Q(invoice__token__icontains=search) | 
            Q(invoice__serie_final__icontains=search) | 
            Q(invoice__contract__token__icontains=search) | 
            Q(invoice__contract__holder__token__icontains=search) | 
            Q(invoice__contract__holder__name__icontains=search) | 
            Q(invoice__customer_final__icontains=search) | 
            Q(invoice__customer_token_final__icontains=search) |
            Q(commitment_deposit__token__icontains=search) |
            Q(commitment_deposit__contract__token__icontains=search)
        )
        
    # `only_excluded` serveix a la pestanya d'exclosos del llistat de pagaments:
    # mostra exactament el que NO es remesarà. Té prioritat sobre
    # `include_excluded`, que només distingeix entre tots i els no exclosos.
    if str(only_excluded).upper() == "TRUE":
        filters &= Q(is_excluded=True)
    elif not include_excluded:
        filters &= Q(is_excluded=False)
    
    payments = (
        Payment.objects.filter(filters)
        .exclude(status__token__in=excluded_status_tokens)
        .exclude(remittances__id__isnull=False, remittances__sent_at__isnull=True)
        .exclude(joined_payments__status__token__in=joined_payment_status_tokens)
        .distinct()
        .order_by("-token")
    )
    
    if str(exclude_contracts_with_pending_invoices).upper() == "TRUE":
        payments = filter_payments_by_contracts_with_pending_invoices(payments)
    elif str(only_contracts_with_pending_invoices).upper() == "TRUE":
        payments = filter_payments_by_contracts_with_pending_invoices(payments, keep_only=True)

    use_remittance_date = request.data.get('use_remittance_date', False)
    today = timezone.localdate()
    groups = {}
    if use_remittance_date:
        for payment in payments:
            contract = payment.commitment_deposit.contract if payment.commitment_deposit else payment.invoice.contract if payment.invoice else None
            r_date_str = None
            if contract and contract.remittance_date:
                ref_date = None
                if payment.commitment_deposit:
                    ref_date = payment.due_date
                else:
                    if payment.invoice and payment.invoice.billing_period_year and payment.invoice.billing_period_month:
                        try:
                            ref_date = datetime(payment.invoice.billing_period_year, payment.invoice.billing_period_month, 1).date()
                        except:
                            ref_date = payment.invoice.send_at or payment.invoice.issue_date or payment.invoice.due_date
                    else:
                        ref_date = (payment.invoice.send_at or payment.invoice.issue_date or payment.invoice.due_date) if payment.invoice else payment.due_date
                
                if not ref_date: ref_date = datetime.now().date()
                if hasattr(ref_date, 'date'): ref_date = ref_date.date()
                    
                year = ref_date.year
                month = ref_date.month
                day = contract.remittance_date
                last_day = calendar.monthrange(year, month)[1]
                if day > last_day: day = last_day
                candidate = datetime(year, month, day).date()
                if candidate < today:
                    # Preferred day already passed this month → advance to next month
                    if month == 12:
                        year, month = year + 1, 1
                    else:
                        month += 1
                    last_day = calendar.monthrange(year, month)[1]
                    if day > last_day: day = last_day
                    candidate = datetime(year, month, day).date()
                r_date_str = candidate.strftime("%Y-%m-%d")
            else:
                d = (payment.invoice.send_at or payment.invoice.due_date) if (payment.invoice and (payment.invoice.send_at or payment.invoice.due_date)) else payment.due_date
                if d:
                    r_date_str = d.strftime("%Y-%m-%d") if isinstance(d, (datetime, date)) else str(d)[:10]
                else:
                    r_date_str = datetime.now().strftime("%Y-%m-%d")
            
            if r_date_str not in groups:
                groups[r_date_str] = {'remittance_date': r_date_str, 'total_amount': Decimal("0"), 'payments': [], 'invoices': []}
            
            groups[r_date_str]['total_amount'] += Decimal(str(payment.amount))
            groups[r_date_str]['payments'].append(payment)
            if payment.invoice:
                groups[r_date_str]['invoices'].append({'id': payment.invoice.id, 'token': payment.invoice.token, 'contract_id': contract.id if contract else None, 'contract_token': contract.token if contract else None, 'amount': payment.amount})
            else:
                groups[r_date_str]['invoices'].append({'id': payment.id, 'token': payment.token, 'contract_id': contract.id if contract else None, 'contract_token': contract.token if contract else None, 'amount': payment.amount})

    payments_batches = []
    max_limit = Decimal(str(max_total_remittance)) if max_total_remittance and Decimal(str(max_total_remittance)) > 0 else None
    
    if use_remittance_date:
        sorted_dates = sorted(groups.keys())
        for d_str in sorted_dates:
            group_payments = groups[d_str]['payments']
            if max_limit:
                current_batch, current_sum = [], Decimal("0")
                for p in group_payments:
                    amt = Decimal(str(p.amount))
                    if amt > max_limit:
                        if current_batch:
                            payments_batches.append((current_batch, d_str))
                            current_batch, current_sum = [], Decimal("0")
                        payments_batches.append(([p], d_str))
                        continue
                    if current_sum + amt > max_limit:
                        payments_batches.append((current_batch, d_str))
                        current_batch, current_sum = [p], amt
                    else:
                        current_batch.append(p)
                        current_sum += amt
                if current_batch: payments_batches.append((current_batch, d_str))
            else:
                payments_batches.append((group_payments, d_str))
    else:
        if max_limit:
            current_batch, current_sum = [], Decimal("0")
            for p in payments:
                amt = Decimal(str(p.amount))
                if amt > max_limit:
                    if current_batch:
                        payments_batches.append((current_batch, send_date))
                        current_batch, current_sum = [], Decimal("0")
                    payments_batches.append(([p], send_date))
                    continue
                if current_sum + amt > max_limit:
                    payments_batches.append((current_batch, send_date))
                    current_batch, current_sum = [p], amt
                else:
                    current_batch.append(p)
                    current_sum += amt
            if current_batch: payments_batches.append((current_batch, send_date))
        else:
            payments_batches = [(list(payments), send_date)]
            
    return payments, payments_batches, selected_payments_type == "return"


def get_bank_distribution(request_data, required=True):
    """
    Reparteix una cerca de pagaments entre comptes, per generar un fitxer SEPA
    independent per cada compte. Veure `get_bank_distribution_with_warnings()`.
    """
    distribution, _ = get_bank_distribution_with_warnings(request_data, required=required)
    return distribution


def get_bank_distribution_with_warnings(request_data, required=True):
    """
    Igual que `get_bank_distribution()` pero tornant tambe els avisos de
    l'encaminament, per ensenyar-los abans de generar la remesa.

    Hi ha dues maneres de dir a qui es remesa, i la primera te prioritat:

      - `selected_companies`: ids d'empreses emissores. El repartiment entre els
        comptes de cada empresa el decideix el mapa d'encaminament
        (`service.models.CompanyBankRouting`), segons l'entitat del pagador.
        Es el mode de la pantalla de remeses.
      - `selected_banks` / `selected_bank`: ids de `CompanyBank` triats a ma. El
        primer banc es el per defecte i recull tot el que no s'ha assignat
        expressament a un altre. Es manté per als payloads antics.

    A tots dos modes, `bank_assignments` ({id_pagament: id_banc}) son les
    excepcions que ha marcat l'usuari al llistat de rebuts i manen per sobre de
    tot. Les claus arriben com a text (JSON) i els ids poden ser int o str, per
    això es normalitza tot a str per comparar.

    Amb `required=False` (recomptes i previsualitzacions, que es demanen abans
    de triar res) una cerca sense bancs ni empreses retorna un sol grup sense
    banc en comptes de petar.

    Retorna `([(bank_id, per_bank_request_data)], avisos)`: el payload original
    mes `payment_ids` / `exclude_payment_ids`, per passar-lo a
    `get_sepa_payments_and_batches()`. Els comptes sense cap pagament no hi
    surten: no te sentit generar-los un fitxer buit.
    """
    selected_companies = request_data.get('selected_companies') or []
    if not isinstance(selected_companies, (list, tuple)):
        selected_companies = [selected_companies]
    selected_companies = [c for c in selected_companies if c not in (None, "")]
    if selected_companies:
        return get_distribution_from_routing(request_data, selected_companies)

    selected_banks = request_data.get('selected_banks') or []
    if not isinstance(selected_banks, (list, tuple)):
        selected_banks = [selected_banks]
    selected_banks = [str(b) for b in selected_banks if b not in (None, "")]

    default_bank = request_data.get('selected_bank', None)
    default_bank = str(default_bank) if default_bank not in (None, "") else None
    if default_bank is None and selected_banks:
        default_bank = selected_banks[0]
    if default_bank and default_bank not in selected_banks:
        selected_banks = [default_bank] + selected_banks

    if not selected_banks:
        if not required:
            return [(None, dict(request_data))], []
        raise ValueError("Missing required field `selected_bank`")

    # dict.fromkeys manté l'ordre de selecció i treu duplicats.
    selected_banks = list(dict.fromkeys(selected_banks))

    assignments = request_data.get('bank_assignments') or {}
    payments_by_bank = {}
    for payment_id, bank_id in assignments.items():
        bank_id = str(bank_id)
        if bank_id not in selected_banks:
            raise ValueError(
                f"Payment {payment_id} assigned to bank {bank_id}, which is not selected"
            )
        payments_by_bank.setdefault(bank_id, []).append(payment_id)

    # Una cerca ja restringida a uns pagaments concrets (`payment_ids` al payload
    # d'entrada) segueix manant: el repartiment per banc nomes pot reduir-la.
    base_payment_ids = request_data.get('payment_ids', None)
    base_payment_ids = [str(p) for p in base_payment_ids] if base_payment_ids is not None else None

    distribution = []
    for bank_id in selected_banks:
        bank_data = dict(request_data)
        bank_data['selected_bank'] = bank_id
        if bank_id == default_bank:
            # El banc per defecte es queda amb la resta de la cerca.
            bank_data['exclude_payment_ids'] = [
                payment_id
                for other_bank, ids in payments_by_bank.items()
                if other_bank != bank_id
                for payment_id in ids
            ]
        else:
            bank_payment_ids = payments_by_bank.get(bank_id, [])
            if base_payment_ids is not None:
                bank_payment_ids = [p for p in bank_payment_ids if p in base_payment_ids]
            if not bank_payment_ids:
                continue
            bank_data['payment_ids'] = bank_payment_ids
            bank_data.pop('exclude_payment_ids', None)
        distribution.append((bank_id, bank_data))

    return distribution, []


def get_distribution_from_routing(request_data, selected_companies):
    """
    Reparteix els rebuts de la cerca aplicant el mapa d'encaminament de cada
    empresa emissora (veure `billing/utils/remittance_routing.py`).

    A diferencia del mode per bancs, aqui tots els rebuts queden assignats
    explicitament, aixi que no hi ha cap compte "per defecte" que reculli la
    resta: cada compte rep el seu `payment_ids`.
    """
    from billing.utils.remittance_routing import resolve_payment_banks

    payments, _, _ = get_sepa_payments_and_batches(RequestData(request_data))
    assignments, warnings = resolve_payment_banks(
        payments,
        manual_assignments=request_data.get('bank_assignments') or {},
        companies=selected_companies,
    )

    payments_by_bank = {}
    for payment_id, bank_id in assignments.items():
        payments_by_bank.setdefault(str(bank_id), []).append(payment_id)

    distribution = []
    for bank_id, payment_ids in payments_by_bank.items():
        bank_data = dict(request_data)
        bank_data['selected_bank'] = bank_id
        bank_data['payment_ids'] = payment_ids
        bank_data.pop('exclude_payment_ids', None)
        # El grup ja surt resolt: si es tornés a passar per l'encaminament es
        # repetiria la feina i s'hi tornarien a comptar els avisos.
        bank_data.pop('selected_companies', None)
        bank_data.pop('selected_banks', None)
        distribution.append((bank_id, bank_data))

    return distribution, warnings


class SEPAPaymentDocumentGenerateViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Payment.objects.all().order_by('-created_at')

    def put(self, request, *args, **kwargs):
        create_doc = request.data.get('create_doc', False)

        if create_doc:
            # Enqueue background generation and return the Celery task id.
            from billing.tasks import generate_sepa_document

            # Ensure payload is JSON serializable for Celery.
            payload = request.data.copy() if hasattr(request.data, "copy") else dict(request.data)
            payload = json.loads(json.dumps(payload, default=str))

            task = generate_sepa_document.apply_async(kwargs={"request_data": payload})
            return JsonResponse({"task_id": task.id}, status=status.HTTP_202_ACCEPTED)

        payments, _, _ = get_sepa_payments_and_batches(request)

        total_import = sum(payment.amount for payment in payments) if hasattr(payments, '__iter__') else Decimal("0")
        total_excluded = payments.filter(is_excluded=True).count() if hasattr(payments, 'filter') else 0
        _, total_anomalies = check_for_anomalies(payments, return_list=False) if hasattr(payments, '__iter__') else (None, 0)

        # El recompte de fitxers es fa banc a banc: cada banc seleccionat genera
        # els seus propis fitxers SEPA amb els pagaments que te assignats.
        try:
            distribution, routing_warnings = get_bank_distribution_with_warnings(request.data, required=False)
        except ValueError as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        company_banks = {
            str(company_bank.id): company_bank
            for company_bank in CompanyBank.objects.filter(
                id__in=[bank_id for bank_id, _ in distribution if bank_id]
            ).select_related('bank', 'company')
        }

        banks_summary = []
        total_sepa_files = 0
        for bank_id, bank_data in distribution:
            company_bank = company_banks.get(str(bank_id))
            bank_payments, bank_batches, _ = get_sepa_payments_and_batches(RequestData(bank_data))
            bank_batches = [batch for batch, _ in bank_batches if batch]
            total_sepa_files += len(bank_batches)
            banks_summary.append({
                "bank": bank_id,
                "bank_name": company_bank.bank.name if company_bank and company_bank.bank else None,
                "bank_iban": company_bank.iban if company_bank else None,
                "company": company_bank.company.id if company_bank and company_bank.company else None,
                "company_name": company_bank.company.alias if company_bank and company_bank.company else None,
                "total_invoices": len(bank_payments),
                "total_amount": sum(payment.amount for payment in bank_payments),
                "total_sepa_files": len(bank_batches),
            })

        response_data = {
            "total_invoices": len(payments),
            "total_amount": total_import,
            "total_anomalies": total_anomalies,
            "total_excluded": total_excluded,
            "total_sepa_files": total_sepa_files,
            "banks": banks_summary,
            "routing_warnings": routing_warnings,
        }

        return JsonResponse(response_data)



def check_for_anomalies(payments, return_list=True, exclude_all=False):
    anomaly_types = {
        "negative_total": [],
        "validate_nif_not": [],
        "validate_iban_not": [],
    }
    total_anomalies = 0
    for payment in payments:
        nif_valid, _ = validate_nif(payment.customer_token_final)
        if payment.amount < 0:
            if return_list: anomaly_types['negative_total'].append(PaymentSEPASerializer(payment).data)
            if exclude_all:
                payment.is_excluded = True
            total_anomalies += 1
        if not nif_valid:
            if return_list: anomaly_types['validate_nif_not'].append(PaymentSEPASerializer(payment).data)
            if exclude_all:
                payment.is_excluded = True
            total_anomalies += 1
        if (payment.payment_bank and not validate_iban(payment.payment_bank)) or not payment.payment_bank:
            if return_list: anomaly_types['validate_iban_not'].append(PaymentSEPASerializer(payment).data)
            if exclude_all:
                payment.is_excluded = True
            total_anomalies += 1
    Payment.objects.bulk_update(payments, ['is_excluded'])
    return anomaly_types if return_list else None, total_anomalies
    

def get_valid_sepa_date(due_date):
    if isinstance(due_date, str):
        due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
    
    # Ensure at least next day to avoid rejection
    min_date = datetime.now().date() + timedelta(days=1)  
    return max(due_date, min_date).strftime("%Y-%m-%d")

def calculate_control_code(dni):
    dni = dni.upper()  
    numeric_dni = ""

    for char in dni:
        if '0' <= char <= '9':
            numeric_dni += char
        elif 'A' <= char <= 'Z':
            numeric_dni += str(ord(char) - ord('A') + 10) 
        else:
            return "Invalid DNI"

    numeric_dni += "142800"

    remainder = int(numeric_dni) % 97
    control_code = str(remainder).zfill(2)

    return control_code

class SEPAPaymentInvoicesViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Payment.objects.all()
    
    def put(self, request, *args, **kwargs):
        payments, _, _ = get_sepa_payments_and_batches(request)
        paginator = StandardResultsSetPagination()
        paginated_payments = paginator.paginate_queryset(payments, request)
        serialized_payments = PaymentSEPASerializer(paginated_payments, many=True).data

        # A cada fila, el compte on acabaria segons el mapa d'encaminament de la
        # seva empresa, perquÃ¨ el llistat pugui ensenyar-ho i deixar canviar-ho.
        # NomÃ©s es resol la pÃ gina que s'ensenya, no tota la cerca.
        selected_companies = request.data.get('selected_companies') or []
        if selected_companies and paginated_payments:
            from billing.utils.remittance_routing import resolve_payment_banks

            page_payments = Payment.objects.filter(
                id__in=[payment.id for payment in paginated_payments]
            )
            assignments, _ = resolve_payment_banks(
                page_payments,
                manual_assignments=request.data.get('bank_assignments') or {},
                companies=selected_companies,
            )
            for row in serialized_payments:
                row['routed_company_bank'] = assignments.get(str(row['id']))

        return paginator.get_paginated_response(serialized_payments)

    def post(self, request, *args, **kwargs):
        is_excluded = request.data.get('is_excluded')
        if is_excluded is None:
            return Response({"error": "Missing is_excluded parameter"}, status=status.HTTP_400_BAD_REQUEST)
        
        payments, _, _ = get_sepa_payments_and_batches(request)
        count = payments.count()
        payments.update(is_excluded=is_excluded)
        return Response({"message": f"{count} payments updated successfully", "updated_count": count}, status=status.HTTP_200_OK)

class SEPAPaymentAnomaliesViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Payment.objects.all()
    
    def put(self, request, *args, **kwargs):
        payments, _, _ = get_sepa_payments_and_batches(request)
        exclude_all_anomalies = request.data.get('exclude_all', False)
        exclude_all = str(exclude_all_anomalies).upper() == "TRUE"
        anomalies, total_anomalies = check_for_anomalies(payments, return_list=True, exclude_all=exclude_all) if payments else ({}, 0)
        return JsonResponse({"anomalies": anomalies, "total_anomalies": total_anomalies})

class SEPAPaymentFilesPreviewViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Payment.objects.all()
    
    def put(self, request, *args, **kwargs):
        # is_commitment = request.data.get('is_commitment', False)
        selected_payments_type = request.data.get('payments_type', None)
        try:
            distribution = get_bank_distribution(request.data, required=False)
        except ValueError as error:
            return Response({"error": str(error)}, status=status.HTTP_400_BAD_REQUEST)

        banks = {
            str(company_bank.id): company_bank
            for company_bank in CompanyBank.objects.filter(
                id__in=[bank_id for bank_id, _ in distribution if bank_id]
            ).select_related('bank', 'company')
        }

        sepa_files_preview = []
        # Un fitxer per lot i per banc: aixi la previsualitzacio ensenya
        # exactament els fitxers que generara la remesa.
        for bank_id, bank_data in distribution:
            company_bank = banks.get(str(bank_id))
            _, payments_batches, _ = get_sepa_payments_and_batches(RequestData(bank_data))
            for batch_payments, d_str in payments_batches:
                if not batch_payments: continue
                batch_invoices, batch_total = [], Decimal("0")
                for payment in batch_payments:
                    batch_total += Decimal(str(payment.amount))
                    contract = payment.commitment_deposit.contract if payment.commitment_deposit else payment.invoice.contract if payment.invoice else None
                    if payment.invoice:
                        batch_invoices.append({'id': payment.invoice.id, 'token': payment.invoice.token, 'contract_id': contract.id if contract else None, 'contract_token': contract.token if contract else None, 'amount': payment.amount})
                    else:
                        batch_invoices.append({'id': payment.id, 'token': payment.token, 'contract_id': contract.id if contract else None, 'contract_token': contract.token if contract else None, 'amount': payment.amount})
                sepa_files_preview.append({
                    'remittance_date': d_str if d_str else datetime.now().strftime("%Y-%m-%d"),
                    'total_amount': batch_total,
                    'invoices': batch_invoices,
                    'bank': company_bank.id if company_bank else None,
                    'bank_name': company_bank.bank.name if company_bank and company_bank.bank else None,
                    'bank_iban': company_bank.iban if company_bank else None,
                    'company': company_bank.company.id if company_bank and company_bank.company else None,
                    'company_name': company_bank.company.alias if company_bank and company_bank.company else None,
                })
        return JsonResponse({"sepa_files_preview": sepa_files_preview})
