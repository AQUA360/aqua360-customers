import base64
from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
import os
import uuid
from celery import shared_task
from celery_progress.backend import ProgressRecorder
from django.conf import settings
from django.core.files.base import ContentFile
from billing.utils.barcode_service import generate_barcode, get_barcode_values
from billing.utils.confirm_invoice_service import confirm_invoice
from billing.utils.invoice_service import generate_empty_invoice
from contract.models import Contract, PaymentType
from coredata.models import ConfigProject
from django.utils import timezone, translation
from coredata.serializers import AddressSerializer, PersonSerializer
from coredata.utils.template_utils import build_template_candidates
from documentmanager.utils.main_utils import upload_document
from documentmanager.utils.sign_certificate_service import sign_pdf
from django.utils.translation import gettext as _
from django.db.models import Q, Count, Sum
from billing.models import Invoice, InvoiceStatus, JoinedPayment, JoinedPaymentStatus, Payment, PaymentStatus
from pricing.models import PriceRate
from claimrequest.models import ClaimRequest, ClaimRequestPayment, ClaimRequestStatus, ClaimRequestStep, VulnerabilityRequest, VulnerabilityRequestStatus
from contract.models import Contract
from contract.serializers.contract_serializer import ContractWithPaymentsSerializer
from notification.models import Notification
from service.models import Exploitation, Company
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from service.serializers.company_serializer import CompanySerializer
from service.utils.exploitation_logo import exploitation_logo_source



@shared_task
def generate_claim_document_pdf(claim_request_id, contract_id, step_id, joined_payment_id=None):
    try:
        claim_request = ClaimRequest.objects.get(id=claim_request_id)
        contract = Contract.objects.get(id=contract_id)
        
        claim_step = ClaimRequestStep.objects.get(id=step_id)
        document_type = claim_step.document_type
        now_date = datetime.now().date()
        # Objecte date, no string: les plantilles hi apliquen |date:"j F Y" i el
        # filtre `date` de Django sobre un string retorna cadena buida, de manera
        # que la data límit de la carta d'avís d'impagament sortia en blanc.
        limit_date = now_date + timedelta(days=claim_step.duration)
        formatted_date = now_date.strftime("%d de %B de %Y")

        # Idioma del document: el del contracte, amb l'idioma del projecte com a
        # fallback. Determina tant la plantilla (variants `_es`, `_en`... resoltes
        # per build_template_candidates) com els noms de mes i les cadenes
        # traduïbles que renderitzen els filtres.
        claim_lang = getattr(contract, 'language', None) or settings.LANGUAGE_CODE

        company = None
        company_obj = None
        sp_address = None

        if (
            contract.supply_point_default
            and contract.supply_point_default.connection
            and contract.supply_point_default.connection.exploitation
            and contract.supply_point_default.connection.exploitation.company
        ):
            company_obj = contract.supply_point_default.connection.exploitation.company
            company = CompanySerializer(
                company_obj
            ).data
        logo_db = company['logo'] if company else None
        logo = None
        if not logo_db:
            c = Company.objects.all().first()
            company = CompanySerializer(c, context={'request': None}).data if c else None
            logo_db = company['logo'] if company else None
        
        if logo_db:
            # netejem logo_db assegurant-nos que sempre arriba el mateix format, potser que arribi una url o un path que comenci per /media/
            logo_db = f'uploads/{logo_db.split("uploads/")[1]}'
            
            # Logo és un path relatiu, construir path complet
            if hasattr(settings, 'DOMAIN_MEDIA') and settings.DOMAIN_MEDIA:
                logo = os.path.join(settings.DOMAIN_MEDIA, f'media/{logo_db}')
            else:
                logo = os.path.join(settings.MEDIA_ROOT, logo_db)

        if contract.supply_point_default and contract.supply_point_default.address:
            sp_address = AddressSerializer(contract.supply_point_default.address).data

        meter_code = None
        if contract.supply_point_default and contract.supply_point_default.meter:
            meter_code = contract.supply_point_default.meter.code

        exploitation_image = None
        exploitation = None
        if (
            contract.supply_point_default
            and contract.supply_point_default.connection
            and contract.supply_point_default.connection.exploitation
        ):
            exploitation = contract.supply_point_default.connection.exploitation
            exploitation_image = exploitation_logo_source(exploitation)

        company_bank = None
        if company_obj:
            company_bank = company_obj.company_banks.filter(is_default=True, is_active=True).first()
            if not company_bank:
                company_bank = company_obj.company_banks.filter(is_active=True).first()

        holder = PersonSerializer(contract.holder).data
        holder_address = next(
            (address for address in holder.get("addresses", []) if address.get("is_billing")),
            None,
        )
        
        claim_payments = ClaimRequestPayment.objects.filter(claim_request=claim_request)
        payments = claim_payments.values_list("payment", flat=True).distinct()
        
        invoices = Invoice.objects.filter(payments__id__in=payments).distinct()
        contract_invoices = invoices.filter(contract=contract)
        invoice_total = sum(invoice.left_to_pay for invoice in contract_invoices)
        invoice_total += Decimal(holder.get("debt_amount", 0))

        # Tarifa de despeses de retorn/tràmits per impagats: el ConfigProject només indica
        # l'identificador (token) de la PriceRate a utilitzar. Per defecte és null i, en
        # aquest cas, no es mostra la dada a la plantilla.
        return_fee_amount = None
        try:
            return_fee_config = ConfigProject.objects.filter(token='claim_letter_return_fee_price_rate_token').first()
            price_rate_token = return_fee_config.value if return_fee_config else None
            if price_rate_token:
                price_rate = PriceRate.objects.filter(token=price_rate_token, is_active=True).first()
                billing_range = price_rate.billing_range_active if price_rate else None
                line_item = billing_range.line_item_types.filter(is_active=True).order_by('id').first() if billing_range else None
                if line_item and line_item.price is not None:
                    return_fee_amount = Decimal(str(line_item.price))
        except Exception:
            return_fee_amount = None

        return_fees_total = (return_fee_amount * contract_invoices.count()) if return_fee_amount else Decimal(0)
        invoice_total_with_fees = invoice_total + return_fees_total
        
        barcode = None
        barcode_base64 = None
        barcode_values = None
        
        joined_payment = None
        if claim_request.current_step.step_template.group_payments and joined_payment_id:
            try:
                joined_payment = JoinedPayment.objects.get(id=joined_payment_id)
                original_payments = joined_payment.payments.filter(claim_requests__claim_step__isnull=True).distinct()
                expense_payments = joined_payment.payments.filter(claim_requests__claim_step__isnull=False).distinct()
                contract_invoices = Invoice.objects.filter(payments__in=original_payments, contract=contract).distinct()
                invoice_total = original_payments.aggregate(total=Sum('amount'))['total'] or Decimal(0)
                return_fee_amount = expense_payments.aggregate(total=Sum('amount'))['total'] or Decimal(0)  
                invoice_total_with_fees = invoice_total + return_fee_amount
            except JoinedPayment.DoesNotExist:
                joined_payment = None
        
        if joined_payment:
            ident = joined_payment.due_date.strftime("%d%m%y") if joined_payment.due_date else limit_date.strftime("%d%m%y")
            if limit_date:
                ident = limit_date.strftime("%d%m%y")
            token = joined_payment.token or ""
            barcode_data = {
                'reference': token if len(token) == 11 else token[:-2],
                'total_final': joined_payment.total_final,
                'company': company_obj,
                'ident': ident,
            }
            barcode = generate_barcode(barcode_data)
            barcode_values = get_barcode_values(barcode_data)
            if barcode:
                barcode_base64 = base64.b64encode(barcode.getvalue()).decode('utf-8')
        
        main_color = "#074df0"
        secondary_color = "#ffffff"
        try:
            main_color = company_obj.invoice_main_color if company_obj and company_obj.invoice_main_color else ConfigProject.objects.get(token='invoice_main_color').value
            secondary_color = company_obj.invoice_secondary_color if company_obj and company_obj.invoice_secondary_color else ConfigProject.objects.get(token='invoice_secondary_color').value
        except:
            pass
        
        template_candidates = build_template_candidates(
            f"{document_type.token}_template.html", lang=claim_lang
        )
        with translation.override(claim_lang):
            html_content = render_to_string(
                template_candidates,
                {
                    "now_date": now_date,
                    "limit_date": limit_date,
                    "formatted_date": formatted_date,
                    "company": company,
                    "sp_address": sp_address,
                    "holder": holder,
                    "holder_address": holder_address.get("address") if holder_address else None,
                    "contract": contract,
                    "invoices": contract_invoices,
                    "invoice_total": invoice_total,
                    "barcode": barcode_base64,
                    "barcode_values": barcode_values,
                    "main_color": main_color,
                    "secondary_color": secondary_color,
                    "logo": logo,
                    "meter_code": meter_code,
                    "exploitation_image": exploitation_image,
                    "company_bank": company_bank,
                    "return_fee_amount": return_fee_amount,
                    "return_fees_total": return_fees_total,
                    "invoice_total_with_fees": invoice_total_with_fees,
                    "joined_payment": joined_payment,
                },
            )
        pdf_buffer = BytesIO()
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)

        if pisa_status.err:
            return {"status": "error", "message": "PDF generation failed"}

        pdf_buffer.seek(0)
        
        #SIGNATURE
        signed_pdf_buffer = sign_pdf(pdf_buffer, company, document_type.name, document_type.token)
        
        return {"status": "success", "pdf_content": signed_pdf_buffer.getvalue()}
    except Exception as e:
        raise Exception(f"Error generating claim document: {e}")

def generate_claim_document(claim_request, contract):
    # Aquí va la lògica per generar el PDF
    # Aquesta funció hauria d'estar definida a claimrequest/utils/claim_document_service.py
    pass 

@shared_task
def set_expired_vulnerability_request():
    now = timezone.now().date()
    status_accepted = VulnerabilityRequestStatus.objects.get(token=ConfigProject.objects.get(token="vulnerability_request_status_accepted_token").value)
    status_expired = VulnerabilityRequestStatus.objects.get(token=ConfigProject.objects.get(token="vulnerability_request_status_expired_token").value)
    expired_vulnerable_requests = VulnerabilityRequest.objects.filter(status=status_accepted, end_at__lte=now)
    
    for request in expired_vulnerable_requests:
        request.status = status_expired
        related_requests = VulnerabilityRequest.objects.filter(person=request.person, status=status_accepted)
        #get related requests that are not request itself
        related_requests = related_requests.exclude(id=request.id)

        if not (related_requests.exists() and len(related_requests) > 0):
            request.person.vulnerability_level = 0
            #request.person.is_vulnerable = False
            request.person.save()

        request.save()

@shared_task
def notify_claim_request_step_due_date():
    tomorrow = timezone.now().date() + timedelta(days=1)
    status_pending = ClaimRequestStatus.objects.get(token=ConfigProject.objects.get(token="claim_request_status_pending_token").value)
    status_accepted = ClaimRequestStatus.objects.get(token=ConfigProject.objects.get(token="claim_request_status_accepted_token").value)
    claim_requests = ClaimRequest.objects.filter(status__in=[status_pending, status_accepted], current_step__due_date__lte=tomorrow)
    for claim_request in claim_requests:
        notification_save = {
            'token': uuid.uuid4(),
            'name': f"Gestió d'impagats pendent",
            'description': f"Gestió d'impagats {claim_request.token} al pas de {claim_request.current_step.name} amb venciment proper",
            'module': 'claimrequest',
            'entity': 'claim-request',
            'object_id': claim_request.id,
            'is_active': True,
            'user': claim_request.user,
        }
        Notification.objects.create(**notification_save)
    

def _build_claim_request_filters(payload):
    filters = Q()
    payment_filters = Q()
    
    payment_config_tokens = [
        'payment_status_expired_token',
        'payment_status_returned_token',
        'payment_status_endowment_token',
        'payment_status_irrecoverable_token'
    ]
    payment_status_tokens = ConfigProject.objects.filter(token__in=payment_config_tokens).values_list('value', flat=True)
    
    claim_request_status_accepted_token = ConfigProject.objects.get(token='claim_request_status_accepted_token').value
    claim_request_status_pending_token = ConfigProject.objects.get(token='claim_request_status_pending_token').value

    payment_statuses = PaymentStatus.objects.filter(token__in=payment_status_tokens)
    filters &= Q(invoices__payments__status__in=payment_statuses, invoices__total_final__gt=0)
    payment_filters &= Q(status__in=payment_statuses, amount__gt=0)

    date_start = payload.get('filter_date_start')
    date_end = payload.get('filter_date_end')
    due_date_start = payload.get('filter_due_date_start')
    due_date_end = payload.get('filter_due_date_end')
    return_start = payload.get('filter_return_start')
    return_end = payload.get('filter_return_end')
    max_pending_invoices = payload.get('max_pending_invoices')
    min_pending_invoices = payload.get('min_pending_invoices')
    exploitation_id = payload.get('selectedExploitationId')
    
    if date_start and date_start != "":
        filters &= Q(invoices__payments__payment_date__gte=date_start)
        payment_filters &= Q(payment_date__gte=date_start)
    if date_end and date_end != "":
        filters &= Q(invoices__payments__payment_date__lte=date_end)
        payment_filters &= Q(payment_date__lte=date_end)
    if due_date_start and due_date_start != "":
        filters &= Q(invoices__payments__due_date__gte=due_date_start)
        payment_filters &= Q(due_date__gte=due_date_start)
    if due_date_end and due_date_end != "":
        filters &= Q(invoices__payments__due_date__lte=due_date_end)
        payment_filters &= Q(due_date__lte=due_date_end)
    if return_start and return_start != "":
        filters &= Q(invoices__payments__reject_date__gte=return_start)
        payment_filters &= Q(reject_date__gte=return_start)
    if return_end and return_end != "":
        filters &= Q(invoices__payments__reject_date__lte=return_end)
        payment_filters &= Q(reject_date__lte=return_end)
    if exploitation_id and exploitation_id != "":
        filters &= Q(invoices__exploitation__id=exploitation_id) | Q(invoices__exploitation__isnull=True)
        payment_filters &= Q(invoice__exploitation_id=exploitation_id) | Q(invoice__exploitation__isnull=True) | Q(contract__supply_points__connection__exploitation__id=exploitation_id) | Q(commitment_deposit__invoices__exploitation__id=exploitation_id) | Q(commitment_deposit__invoices__exploitation__isnull=True)

    use_types = payload.get('selectedUseTypesIds')
    client_types = payload.get('selectedClientTypesIds')
    zones = payload.get('selectedZonesIds')
    contract_statuses = payload.get('selectedContractStatusesIds')
    debt_management = payload.get('selectedDebtMngsIds')
    check_without_debt = payload.get('check_without_debt', True)
    rejection_motives = payload.get('rejection_motives')
    selected_contracts_ids = payload.get('selected_contracts_id')

    if selected_contracts_ids:
        filters &= Q(id__in=selected_contracts_ids)
    if use_types:
        filters &= Q(use_type__id__in=use_types)
    if client_types:
        filters &= Q(client_type__id__in=client_types)
    if zones:
        filters &= Q(supply_point_default__property__route_position__route__route_zone__id__in=zones)
    if contract_statuses:
        filters &= Q(status__id__in=contract_statuses)
    if rejection_motives:
        filters &= Q(invoices__payments__reject__id__in=rejection_motives)
        payment_filters &= Q(reject__id__in=rejection_motives)
    if debt_management:
        filters &= Q(holder__vulnerability_level__in=debt_management, holder__is_juridic=False) | Q(tenant__vulnerability_level__in=debt_management, holder__is_juridic=True) | Q(holder__vulnerability_level__isnull=True)
    # if debt_management:
    #     include_null = "null" in debt_management or len(debt_management) == 0
    #     debt_management = [v for v in debt_management if v != "null"]
    #     debt_query = Q()
    #     if debt_management:
    #         debt_query |= Q(debt_management__id__in=debt_management)
    #     if include_null:
    #         debt_query |= Q(debt_management__isnull=True)
    #     filters &= debt_query
    elif not check_without_debt:
        filters &= Q(debt_management__isnull=False)

    contracts_ignored = payload.get('ignore_contracts')
    if contracts_ignored:
        filters &= ~Q(id__in=contracts_ignored)

    ignore_payments = payload.get('ignore_payments', [])

    if ignore_payments:
        filters &= ~Q(invoices__payments__id__in=ignore_payments)
        payment_filters &= ~Q(id__in=ignore_payments)

    # No comptabilitzar com a "vençudes" les factures de despeses/recàrrec de
    # retorn (invoice_return_charge()): tenen una línia amb la PriceRate
    # indicada per `invoice_return_price_rate_token`. Precalculem els ids
    # d'aquestes factures (en lloc de filtrar per `invoices__line_items__...`
    # dins dels Q de `filters`/`annotation_filters`) per evitar duplicar files
    # via la relació multivaluada `line_items` quan es fa servir amb Count/Sum.
    return_fee_invoice_ids = None
    exclude_return_fee = payload.get('exclude_return_fee_invoices', False)
    if exclude_return_fee:
        return_fee_price_rate_token = ConfigProject.objects.filter(
            token='invoice_return_price_rate_token'
        ).values_list('value', flat=True).first()
        if return_fee_price_rate_token:
            return_fee_invoice_ids = list(
                Invoice.objects.filter(
                    line_items__price_rate__token=return_fee_price_rate_token
                ).values_list('id', flat=True).distinct()
            )
            filters &= ~Q(invoices__id__in=return_fee_invoice_ids)
            payment_filters &= ~Q(invoice_id__in=return_fee_invoice_ids)

    annotation_filters = Q()
    annotation_filters &= Q(invoices__payments__status__in=payment_statuses)

    expired_status_token = ConfigProject.objects.get(token='invoice_status_expired_token').value
    annotation_filters &= Q(invoices__status=InvoiceStatus.objects.get(token=expired_status_token))

    if date_start and date_start != "":
        annotation_filters &= Q(invoices__payments__payment_date__gte=date_start)
    if date_end and date_end != "":
        annotation_filters &= Q(invoices__payments__payment_date__lte=date_end)
    if due_date_start and due_date_start != "":
        annotation_filters &= Q(invoices__payments__due_date__gte=due_date_start)
    if due_date_end and due_date_end != "":
        annotation_filters &= Q(invoices__payments__due_date__lte=due_date_end)
    if return_start and return_start != "":
        annotation_filters &= Q(invoices__payments__reject_date__gte=return_start)
    if return_end and return_end != "":
        annotation_filters &= Q(invoices__payments__reject_date__lte=return_end)
    if rejection_motives:
        annotation_filters &= Q(invoices__payments__reject__id__in=rejection_motives)
    if ignore_payments:
        annotation_filters &= ~Q(invoices__payments__id__in=ignore_payments)
    if return_fee_invoice_ids is not None:
        annotation_filters &= ~Q(invoices__id__in=return_fee_invoice_ids)
    if exploitation_id and exploitation_id != "":
        annotation_filters &= Q(invoices__exploitation__id=exploitation_id) | Q(invoices__exploitation__isnull=True)
    
    annotation_filters &= ~Q(invoices__payments__claim_requests__claim_request__status__token__in=[claim_request_status_accepted_token,claim_request_status_pending_token])

    has_min_pending_invoices = min_pending_invoices and min_pending_invoices != "" and min_pending_invoices != 0
    has_max_pending_invoices = max_pending_invoices and max_pending_invoices != "" and max_pending_invoices != 0
    if has_min_pending_invoices or has_max_pending_invoices:
        pending_invoices_qs = Contract.objects.annotate(
            pending_invoices_count=Count(
                'invoices',
                filter=annotation_filters & Q(invoices__total_final__gt=0),
                distinct=True,
            )
        )
        if has_min_pending_invoices:
            pending_invoices_qs = pending_invoices_qs.filter(
                pending_invoices_count__gte=min_pending_invoices
            )
        if has_max_pending_invoices:
            pending_invoices_qs = pending_invoices_qs.filter(
                pending_invoices_count__lte=max_pending_invoices
            )
        filters &= Q(id__in=pending_invoices_qs.values('id'))

    return filters, payment_filters, annotation_filters, ignore_payments, return_fee_invoice_ids


@shared_task(bind=True)
def generate_claim_expenses(self, claim_request_id, claim_request_step_id, contract_ids, price_rate_ids):
    progress_recorder = ProgressRecorder(self)
    try:
        
        claim_request = ClaimRequest.objects.get(id=claim_request_id)
        claim_request_step = ClaimRequestStep.objects.get(id=claim_request_step_id)
        contracts = Contract.objects.filter(id__in=contract_ids).distinct()
        price_rates = PriceRate.objects.filter(id__in=price_rate_ids)
        joined_payment_status_expired_token = ConfigProject.objects.get(token='joined_payment_status_expired_token').value
        joined_payment_status_pending_token = ConfigProject.objects.get(token='joined_payment_status_pending_token').value
        joined_payment_pending = JoinedPaymentStatus.objects.get(token=joined_payment_status_pending_token)
        
        bank_payment = PaymentType.objects.get(token="BANK_PAYMENT")
        
        confirmed_status = InvoiceStatus.objects.get(token=ConfigProject.objects.get(token='invoice_status_confirmed_token').value)
        
        total_contracts = contracts.count()
        progress_recorder.set_progress(0, 100, description=f"Generant factures de despeses (0/{total_contracts})")
        
        invoices = []
        billing_type = claim_request_step.step_template.billing_type
        
        contract_invoices = Invoice.objects.filter(payments__claim_requests__claim_request=claim_request, payments__claim_requests__claim_step__isnull=True, is_active=True).filter(
            Q(contract__in=contracts) |
            Q(contract_request__contract__in=contracts) |
            Q(contract_termination__contract__in=contracts)
        )
        if billing_type == 'contract':
            for contract in contracts:
                invoices, progress_recorder, _ = _generate_claim_expenses_invoice(invoices, progress_recorder, contract, price_rates, confirmed_status, total_contracts)
        elif billing_type == 'invoice':
            open_joined_payment_status_tokens = [
                joined_payment_status_pending_token,
                joined_payment_status_expired_token,
            ]
            
            for contract_invoice in contract_invoices:
                contract = None
                if contract_invoice.contract:
                    contract = contract_invoice.contract
                elif contract_invoice.contract_request:
                    try:
                        contract = Contract.objects.get(contract_request=contract_invoice.contract_request)
                    except Contract.DoesNotExist:
                        contract = None
                elif contract_invoice.contract_termination:
                    contract = contract_invoice.contract_termination.contract
                if not contract:
                    print(f"Contract not found for invoice {contract_invoice.serie_final}")
                    continue
                invoices, progress_recorder, expense_invoice = _generate_claim_expenses_invoice(
                    invoices, progress_recorder, contract, price_rates, confirmed_status, total_contracts, contract_invoice
                )
                
                if claim_request_step.step_template.group_payments:
                    _upsert_joined_payment_for_claim_invoice(
                        claim_request=claim_request,
                        contract=contract,
                        original_invoice=contract_invoice,
                        expense_invoice=expense_invoice,
                        joined_payment_pending=joined_payment_pending,
                        open_status_tokens=open_joined_payment_status_tokens,
                        payment_type_fallback=bank_payment,
                    )
                        
        
        
        
        Invoice.objects.filter(id__in=invoices).update(status=confirmed_status)
        payments = Payment.objects.filter(invoice__id__in=invoices)
        total_payments = payments.count()
        progress_recorder.set_progress(50, 100, description=f"Assignant pagaments a la gestió d'impagats (0/{total_payments})")
        
        new_request_payments = []
        for payment in payments:
            claim_request_payment = ClaimRequestPayment(
                claim_request=claim_request,
                payment=payment,
                contract=payment.invoice.contract,
                claim_step=claim_request_step,
            )
            new_request_payments.append(claim_request_payment)
            progress_recorder.set_progress(
                50 + (int((len(new_request_payments) / total_payments) * 50) if total_payments else 50),
                100,
                description=f"Assignant pagaments a la gestió d'impagats ({len(new_request_payments)}/{total_payments})"
            )
        ClaimRequestPayment.objects.bulk_create(new_request_payments)
        claim_request_step.task_id = None
        claim_request_step.save()
        
       
                    
                
            
        
        progress_recorder.set_progress(100, 100, description="Despeses de reclamació generades")
        
        return {
            "status": "success",
            "message": "Claim expenses generated successfully",
            "total_payments": len(new_request_payments),
        }
    except Exception as e:
        claim_request_step.task_id = None
        claim_request_step.save()
        raise Exception(f"Error generating claim expenses: {e}")

def _upsert_joined_payment_for_claim_invoice(
    claim_request,
    contract,
    original_invoice,
    expense_invoice,
    joined_payment_pending,
    open_status_tokens,
    payment_type_fallback=None,
):
    from billing.utils.joined_payment_service import generate_joined_payment_id, register_joined_payment_log

    payments = Payment.objects.filter(
        Q(invoice=original_invoice) |
        Q(invoice=expense_invoice) |
        Q(invoice__parent_invoice=original_invoice)
    ).distinct()
    if not payments.exists():
        return None

    original_payments = original_invoice.payments.all()
    joined_payment = None
    if original_payments.exists():
        joined_payment = JoinedPayment.objects.filter(
            payments__in=original_payments,
            status__token__in=open_status_tokens,
            claim_request=claim_request,
        ).distinct().first()

    if joined_payment:
        existing_ids = set(joined_payment.payments.values_list('id', flat=True))
        payments_to_add = [payment.id for payment in payments if payment.id not in existing_ids]
        if payments_to_add:
            joined_payment.payments.add(*payments_to_add)
            joined_payment.total_final = joined_payment.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
            joined_payment.save(update_fields=['total_final'])
        return joined_payment

    person_ins = original_invoice.person or (contract.holder if contract else None)
    customer_final = None
    customer_token_final = None
    if person_ins:
        customer_final = f"{person_ins.name} {person_ins.surname if person_ins.surname else ''}"
        customer_token_final = person_ins.token

    # payment_type = original_invoice.payment_type or payment_type_fallback
    payment_type = payment_type_fallback
    number = generate_joined_payment_id('05')
    total_final = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    due_date = timezone.now() + timedelta(days=claim_request.current_step.duration or 30)

    joined_payment = JoinedPayment.objects.create(
        token=number,
        number=number,
        status=joined_payment_pending,
        claim_request=claim_request,
        contract=contract,
        person=person_ins,
        customer_final=customer_final,
        customer_token_final=customer_token_final,
        payment_type=payment_type,
        payment_type_name=payment_type.name if payment_type else None,
        payment_type_token=payment_type.token if payment_type else None,
        total_final=total_final,
        due_date=due_date,
        user=claim_request.user,
    )
    joined_payment.payments.set(payments)
    register_joined_payment_log(
        joined_payment,
        None,
        joined_payment.status,
        _("Joined payment created"),
        claim_request.user,
    )
    return joined_payment


def claim_request_groups_payments_without_rates(claim_request):
    """
    True when a step to create groups payments and has no price rates.
    Steps with price rates are billed later by generate_claim_expenses.
    """
    return claim_request.steps.filter(
        step_template__group_payments=True,
    ).annotate(
        price_rate_count=Count('step_template__price_rates'),
    ).filter(price_rate_count=0).exists()


def create_joined_payments_for_claim_request(claim_request):
    """
    One pending JoinedPayment per contract, with every ClaimRequestPayment
    of that contract. Totals the payment amounts (e.g. 25 + 10 + 5 = 40).
    """
    from billing.utils.joined_payment_service import generate_joined_payment_id, register_joined_payment_log
    paid_payment_status_token = ConfigProject.objects.get(token='payment_status_paid_token').value

    claim_payments = ClaimRequestPayment.objects.filter(
        claim_request=claim_request,
        payment__isnull=False,
        is_excluded=False,
    ).exclude(payment__status__token=paid_payment_status_token).distinct().select_related(
        'contract',
        'contract__holder',
        'payment',
        'payment__person',
        'payment__invoice',
        'payment__invoice__person',
    )
    if not claim_payments.exists():
        return []

    payments_by_contract = {}
    contracts_by_id = {}
    for claim_payment in claim_payments:
        contract_id = claim_payment.contract_id
        contract_payments = payments_by_contract.setdefault(contract_id, {})
        contract_payments[claim_payment.payment_id] = claim_payment.payment
        contracts_by_id[contract_id] = claim_payment.contract

    joined_payment_status_expired_token = ConfigProject.objects.get(token='joined_payment_status_expired_token').value
    joined_payment_status_pending_token = ConfigProject.objects.get(token='joined_payment_status_pending_token').value
    joined_payment_pending = JoinedPaymentStatus.objects.get(token=joined_payment_status_pending_token)
    open_status_tokens = [
        joined_payment_status_pending_token,
        joined_payment_status_expired_token,
    ]
    payment_type = PaymentType.objects.get(token="BANK_PAYMENT")

    step = claim_request.current_step
    duration_days = (step.duration if step else None) or 30
    due_date = (timezone.now() + timedelta(days=duration_days)).date()

    created = []
    for contract_id, payments_by_id in payments_by_contract.items():
        payments = list(payments_by_id.values())
        if not payments:
            continue

        contract = contracts_by_id.get(contract_id)
        joined_payment = JoinedPayment.objects.filter(
            claim_request=claim_request,
            contract=contract,
            status__token__in=open_status_tokens,
        ).distinct().first()

        if joined_payment:
            existing_ids = set(joined_payment.payments.values_list('id', flat=True))
            payments_to_add = [payment.id for payment in payments if payment.id not in existing_ids]
            if payments_to_add:
                joined_payment.payments.add(*payments_to_add)
                joined_payment.total_final = joined_payment.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
                joined_payment.save(update_fields=['total_final'])
            created.append(joined_payment)
            continue

        person_ins = contract.holder if contract and contract.holder_id else None
        if not person_ins:
            for payment in payments:
                if payment.invoice and payment.invoice.person_id:
                    person_ins = payment.invoice.person
                    break
                if payment.person_id:
                    person_ins = payment.person
                    break

        customer_final = None
        customer_token_final = None
        if person_ins:
            customer_final = f"{person_ins.name} {person_ins.surname if person_ins.surname else ''}"
            customer_token_final = person_ins.token

        number = generate_joined_payment_id('05')
        total_final = sum((payment.amount or Decimal('0') for payment in payments), Decimal('0'))

        joined_payment = JoinedPayment.objects.create(
            token=number,
            number=number,
            status=joined_payment_pending,
            claim_request=claim_request,
            contract=contract,
            person=person_ins,
            customer_final=customer_final,
            customer_token_final=customer_token_final,
            payment_type=payment_type,
            payment_type_name=payment_type.name if payment_type else None,
            payment_type_token=payment_type.token if payment_type else None,
            total_final=total_final,
            due_date=due_date,
            user=claim_request.user,
        )
        joined_payment.payments.set(payments)
        register_joined_payment_log(
            joined_payment,
            None,
            joined_payment.status,
            _("Joined payment created"),
            claim_request.user,
        )
        created.append(joined_payment)

    return created


def _generate_claim_expenses_invoice(invoices, progress_recorder, contract, price_rates, confirmed_status, total_contracts, invoice=None):
        expense_invoice = generate_empty_invoice(
            contract, None, 
            contract.holder, _("Expenses"), 
            None, contract.supply_point_default.connection.exploitation, 
            None, None, price_rates, False, invoice
            )
        expense_invoice.status = confirmed_status
        confirm_invoice(expense_invoice)
        invoices.append(expense_invoice.id)
        progress_recorder.set_progress(
            int((len(invoices) / total_contracts) * 50) if total_contracts else 50,
            100,
            description=f"Generant factures de despeses ({len(invoices)}/{total_contracts})"
        )
        return invoices, progress_recorder, expense_invoice

@shared_task
def obtain_claim_request_data(payload=None):
    payload = payload or {}
    filters, payment_filters, annotation_filters, ignore_payments, return_fee_invoice_ids = _build_claim_request_filters(payload)

    contracts = Contract.objects.filter(filters).annotate(
        payments_count=Count('invoices__payments', filter=annotation_filters),
        total_amount=Sum('invoices__payments__amount', filter=annotation_filters)
    ).filter(payments_count__gt=0).distinct()

    total_contracts = contracts.count()
    total_payments = contracts.aggregate(total=Sum('payments_count'))['total'] or 0
    total_amount = contracts.aggregate(total=Sum('total_amount'))['total'] or 0

    serialized_contracts = ContractWithPaymentsSerializer(contracts, many=True, context={
        'payments_ignored': ignore_payments,
        'filters': filters,
        'payment_filters': payment_filters,
        'exclude_return_fee_invoice_ids': return_fee_invoice_ids,
    }).data
    # how many expired invoices are there in the contracts (if contract 1 has 2 expired invoices, and contract 2 has 1 expired invoice, return 3)
    total_expired_invoices = sum(contract['expired_invoices'] for contract in serialized_contracts)

    return {
        "contracts": serialized_contracts,
        "total_contracts": total_contracts,
        "total_payments": total_payments,
        "total_amount": float(total_amount) if total_amount is not None else 0,
        "total_expired_invoices": total_expired_invoices,
    }