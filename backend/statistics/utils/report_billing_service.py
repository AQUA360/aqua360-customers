import datetime
import math
import os
import threading
from django.core.files.base import ContentFile
from django.db.models import F, Count, Sum, Q, Max, Case, When, Value, CharField, DecimalField, Subquery
from decimal import Decimal
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.db.models import Window
from django.db.models.functions import Abs, Coalesce, RowNumber
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
import openpyxl
from io import BytesIO
from openpyxl.styles import PatternFill
from django.core.files.storage import default_storage
from rest_framework import status
from rest_framework.response import Response

from billing.utils.aca_company_service import ACACompanyError, get_records_company, resolve_aca_company, use_multiple_companies
from billing.models import Biller, Billing, Invoice, InvoiceLineItem, InvoiceStatus, Payment, PaymentRemittance, Reading
from billing.utils.invoice_service import get_invoice_status, get_totals
from billing.utils.payment_service import get_status_map
from contract.models import Contract
from coredata.models import ConfigProject, Person
from coredata.utils.address_utils import get_address_complete_without_city
from coredata.utils.other_utils import round_ceil
from coredata.utils.validators_utils import validate_nif
from pricing.models import ArticleCode, LineItemType, Product, Tax
from service.models import Company, Exploitation, SupplyPointType
from statistics.views.reports_views import add_row, adjust_column_widths, filter_pending_invoices, save_report, jump_row
from statistics.utils.report_filters import (get_billing_ids, get_multi_ids, has_serie_final_range, invoice_multi_filter_q,
                                             payment_multi_filter_q, serie_final_range_invoices, serie_final_range_period)


def _get_aca_part_tokens():
    """
    Helper to retrieve ACA part fixed/variable article tokens.
    """
    required_tokens = ("part_fixa", "part_variable")
    existing_tokens = set(ArticleCode.objects.filter(token__in=required_tokens).values_list('token', flat=True))
    missing_tokens = [token for token in required_tokens if token not in existing_tokens]
    if missing_tokens:
        raise Exception(
            "Configuració ACA incompleta: falten els codis d'article (ArticleCode) "
            f"{', '.join(missing_tokens)}. Executa 'python manage.py watchdog_fix_aca_config' "
            "i 'python manage.py fix_aca_lineitemtype_articles'."
        )
    return required_tokens


def _aca_invoices_company_ids(aca_invoice_ids):
    return Invoice.objects.filter(id__in=aca_invoice_ids).order_by().values_list('company_id', flat=True).distinct()


def _aca_as_date(value):
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    return value


def _aca_trimester_from_month(month):
    """T1=gen-mar, T2=abr-jun, T3=jul-set, T4=oct-des. Només hi ha 4 trimestres."""
    if not month:
        return 1
    return min(4, max(1, math.ceil(int(month) / 3)))


def _aca_last_included_date(start_date, end_date):
    """Últim dia inclòs: el selector envia sovint el dia 1 del mes següent (exclusiu)."""
    start = _aca_as_date(start_date)
    end = _aca_as_date(end_date)
    if not start or not end:
        return None
    if end.day == 1 and end > start:
        return end - datetime.timedelta(days=1)
    return end


def _aca_months_in_range(start_date, end_date):
    """Llista (any, mes) coberts pel rang, tenint en compte el final exclusiu."""
    start = _aca_as_date(start_date)
    last = _aca_last_included_date(start_date, end_date)
    if not start or not last or last < start:
        return []
    months = []
    year, month = start.year, start.month
    while (year, month) <= (last.year, last.month):
        months.append((year, month))
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return months


def _aca_date_range_month(start_date, end_date):
    """Mes del rang si l'usuari ha triat un sol mes de calendari."""
    months = _aca_months_in_range(start_date, end_date)
    if len(months) != 1:
        return None
    return months[0][1]


def _aca_date_range_trimester(start_date, end_date):
    """T1-T4 només si el rang és un trimestre natural complet (3 mesos).

    Decret 103/2000 art. 39.2.b: la declaració trimestral recull la facturació
    del trimestre natural anterior (gen-mar, abr-jun, jul-set, oct-des).
    Dos mesos no són un trimestre.
    """
    months = _aca_months_in_range(start_date, end_date)
    if len(months) != 3:
        return None
    years = {year for year, _month in months}
    trimesters = {_aca_trimester_from_month(month) for _year, month in months}
    if len(years) != 1 or len(trimesters) != 1:
        return None
    return trimesters.pop()


def _aca_effective_use_annotation():
    return Case(
        When(
            Q(invoice__used_aca__isnull=False) & ~Q(invoice__used_aca=''),
            then=F('invoice__used_aca'),
        ),
        default=F('invoice__contract__use_aca'),
        output_field=CharField(),
    )


def _invoice_effective_use_aca(invoice):
    if invoice.used_aca:
        return invoice.used_aca
    if invoice.contract:
        return invoice.contract.use_aca or ''
    return ''


def _split_aca_product_tokens(aca_product_token):
    if not aca_product_token:
        return []
    return [part.strip() for part in str(aca_product_token).split('|') if part.strip()]


def _aca_product_token_q(field, aca_product_token):
    tokens = _split_aca_product_tokens(aca_product_token)
    if not tokens:
        return Q(pk__in=[])
    q = Q()
    for token in tokens:
        q |= Q(**{f'{field}__contains': token})
    return q


def _product_token_matches_aca(prod_token, aca_product_token):
    if not prod_token:
        return False
    return any(token in prod_token for token in _split_aca_product_tokens(aca_product_token))


def _get_aca_invoices_data(invoices, aca_product_token, pre_invoice_token):
    """
    Helper to obtain common ACA invoice aggregation data reused across reports.
    """
    # Filter invoices that have ACA products (using distinct to avoid duplicates from JOIN)
    invoices_with_aca = invoices.filter(
        _aca_product_token_q('line_items__product__token', aca_product_token)
    ).distinct()

    print("total invoices with ACA: ", invoices_with_aca.count())

    aca_invoice_ids = invoices_with_aca.exclude(
        status__token__in=[pre_invoice_token]
    ).values_list('id', flat=True)

    aca_line_item_product_q = _aca_product_token_q('line_items__product__token', aca_product_token)
    invoices_by_exploitation = Invoice.objects.filter(
        id__in=aca_invoice_ids,
    ).values('exploitation__name').annotate(
        ine_code=F('exploitation__code'),
        company_name=F('exploitation__company__name'),
        exploitation_supply_code=F('exploitation__company__supply_code'),
        company_type=F('exploitation__company__type__name'),
        line_items_counts=Count(
            'line_items',
            filter=aca_line_item_product_q,
        ),
        count=Count('id'),
        sum=Sum('consumption'),
    ).distinct()

    print(f"invoices_by_exploitation from query: {len(invoices_by_exploitation)} exploitations")
    for invoice in invoices_by_exploitation:
        print(f"  - {invoice['exploitation__name']}: {invoice['count']} invoices, sum: {invoice['sum']}")

    line_items_totals_by_exploitation = InvoiceLineItem.objects.filter(
        _aca_product_token_q('product__token', aca_product_token),
        invoice__id__in=aca_invoice_ids,
        is_active=True,
    ).values('invoice__exploitation__name').annotate(
        total_sum=Sum('price'),
    )

    for line_item in line_items_totals_by_exploitation:
        print(line_item['invoice__exploitation__name'])
        print(line_item['total_sum'])

    totals_dict = {
        item['invoice__exploitation__name']: item['total_sum']
        for item in line_items_totals_by_exploitation
    }

    for item in invoices_by_exploitation:
        item['line_items_total_final'] = totals_dict.get(item['exploitation__name'], 0)
        print(f"{item['exploitation__name']}: {item['count']} invoices, total: {item['line_items_total_final']}")

    # Base queryset for ACA line items
    aca_line_items_qs = InvoiceLineItem.objects.filter(
        _aca_product_token_q('product__token', aca_product_token),
        invoice__in=invoices.exclude(status__token__in=[pre_invoice_token]),
        is_active=True,
    ).select_related(
        'invoice',
        'invoice__status',
        'invoice__contract',
        'invoice__contract__use_type',
        'line_item_type',
        'line_item_type__article',
        'line_item_type__quantity'
    ).prefetch_related(
        'invoice__line_items',
        'invoice__line_items__adjustments',
        'invoice__line_items__adjustments__adjustment',
        'invoice__line_items__adjustments__adjustment__conditions',
        'invoice__readings'
    )

    return aca_invoice_ids, invoices_by_exploitation, totals_dict, aca_line_items_qs


def _get_signed_invoice_consumption_total(invoices, payoff_status_token):
    """
    Compute invoice consumption with sign correction by invoice status.
    If invoice status token matches payoff token, treat consumption as negative.
    """
    if not invoices.exists():
        return 0

    total_consumption = 0
    for invoice in invoices.select_related("status").distinct():
        consumption = invoice.real_consumption or 0
        
        # print(f"invoice: {invoice.serie_final}")
        # print(f"invoice.consumption: {consumption}")
        if invoice.status and invoice.status.token == payoff_status_token: # si és una Abonament hem de restar el consum
            total_consumption -= abs(consumption)
        else:
            total_consumption += consumption
        # print(f"total consumption: {total_consumption}")
        # print("------------- 8< ------------------- end invoice --")

    
    return int(total_consumption)


def _payoff_signed_sum(field_name, payoff_status_token, tax_pct=None):
    """
    Sum `field_name` (price/tax_price) forcing a negative sign for line items
    belonging to invoices in "payoff" (abonament) status, regardless of the sign
    stored in the DB. Optionally restrict to a given tax_percent bucket.
    Shared by get_report_billing_summary and generate_billing_taxes_summary so both
    reports account for abonaments the same way.
    """
    condition = Q(invoice__status__token=payoff_status_token)
    if tax_pct is not None:
        condition &= Q(tax_percent=tax_pct)
    base_when = When(condition, then=Abs(F(field_name)) * Value(Decimal('-1')))
    default_when = F(field_name) if tax_pct is None else Value(Decimal('0'))
    if tax_pct is not None:
        return Sum(
            Case(
                base_when,
                When(tax_percent=tax_pct, then=F(field_name)),
                default=default_when,
                output_field=DecimalField(max_digits=10, decimal_places=6),
            )
        )
    return Sum(
        Case(
            base_when,
            default=default_when,
            output_field=DecimalField(max_digits=10, decimal_places=6),
        )
    )


def get_report_billing_summary(request, black_fill, white_bold_font, task=None):
    try:
        print("getting billing summary")
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        billing_ids = get_billing_ids(request.data)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)	
        
        has_serie_range = has_serie_final_range(request.data)
        if not billing_ids and not date_range and not has_serie_range:
            return Response({"error": "billing id, date range or serie_final range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        print("got id or date range")
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        billing = None
        billings = []
        start_date = None
        end_date = None
        
        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            billing = get_object_or_404(Billing, id=billing_ids[0])
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
            invoices = Invoice.objects.filter(issue_date__range=(start_date.date(), end_date.date()), type_final=invoice_type).distinct()
        elif has_serie_range:
            # Seleccio nomes pel rang de numero de factura: el rang ja identifica les
            # factures, sense lot ni periode. filter_pending_invoices hi aplica el rang
            # (apply_serie_final_range) i el periode surt de les factures resultants,
            # que es el que fan servir els titols i el nom del fitxer.
            invoices = filter_pending_invoices(serie_final_range_invoices(), request)
            start_date, end_date = serie_final_range_period(invoices)
            if start_date is None:
                return Response({"error": "the serie_final range has no invoices."}, status=status.HTTP_400_BAD_REQUEST), None, None
        else:
            raise Exception("Error obtaining invoices for report billing summary")
        
        if exploitation:
            invoices = invoices.filter(exploitation=exploitation)
        
        invoices = filter_pending_invoices(invoices, request)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        payoff_status_token = ConfigProject.objects.get(token="invoice_status_payoff_token").value

        active_line_items = InvoiceLineItem.objects.filter(invoice__in=invoices, is_active=True)
        line_items_counts = active_line_items.values('product_name', 'tax_percent') \
            .annotate(
                count=Count('invoice', distinct=True),
                sum_price=_payoff_signed_sum('price', payoff_status_token),
                sum_tax=_payoff_signed_sum('tax_price', payoff_status_token),
            ) \
            .order_by()

        total_base = 0.0
        total_tax = 0.0
        total_sum = 0.0
        
        for item in line_items_counts:
            base = float(item['sum_price'] or 0)
            tax = float(item['sum_tax'] or 0)
            total_base += base
            total_tax += tax
            total_sum += (base + tax)
        
        line_items = [
            [
                item['product_name'],
                f"{item['tax_percent']} %" if item['tax_percent'] is not None else "- %",
                item['count'],
                round(float(item['sum_price'] or 0), 2),
                round(float(item['sum_tax'] or 0), 2),
                round(float(item['sum_price'] or 0) + float(item['sum_tax'] or 0), 2),
            ] for item in line_items_counts
        ]
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("Facturació")
        
        row = 0
        
        title = _("Facturació %(date)s") % {"date": billing.created_at.strftime('%d/%m/%Y')} if billing else _("Facturacions %(start)s - %(end)s") % {"start": start_date.strftime('%d/%m/%Y'), "end": end_date.strftime('%d/%m/%Y')}
        
        main_title =[ title, "", "", "", "", ""]
        row = add_row(sheet, row, main_title)
        row = jump_row(row)
        
        titles = [_("Nom"), _("IVA %"), _(" Num. Factures"), _("Base"), _("IVA"), _("Totals")]

        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)
        for item in line_items:
            row = add_row(sheet, row, item)
            for col in (4, 5, 6):
                sheet.cell(row=row, column=col).number_format = '#,##0.00'
            
        totals = [
            _("Totals"),
            "",
            "",
            round(total_base, 2),
            round(total_tax, 2),
            round(total_sum, 2),
        ]
        
        row = add_row(sheet, row, totals, fill=black_fill, font=white_bold_font)
        for col in (4, 5, 6):
            sheet.cell(row=row, column=col).number_format = '#,##0.00'
            
        adjust_column_widths(sheet)
            
        filename = f"billing_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id, start_date=start_date, end_date=end_date)
        print("report saved")
        
        os.remove(filename)
        return response, document_id, None
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def generate_aca_summary_report(request, black_fill=None, white_bold_font=None, task=None):
    try:
        print("getting ACA summary")
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        billing_ids = get_billing_ids(request.data)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        # Amb múltiples empreses cada fitxer ACA és d'una sola empresa (veure resolve_aca_company)
        company_id = request.data.get('company_id', None)
        has_serie_range = has_serie_final_range(request.data)
        if not billing_ids and not date_range and not has_serie_range:
            return Response({"error": "billing id, date range or serie_final range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        print("got id or date range")
        billing = None
        billings = []
        start_date = None
        end_date = None
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        
        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            invoices = filter_pending_invoices(invoices, request)
            billing = get_object_or_404(Billing, id=billing_ids[0])
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
            status_cancelled_token = ConfigProject.objects.get(token="invoice_status_cancelled_token").value
            # Excloure les anul·lades NOMÉS si no tenen una refactura/abonament lligat (return_token).
            # Les anul·lades amb return_token es mantenen (mateix criteri que el detall de facturació).
            invoices = Invoice.objects.filter(
                issue_date__range=(start_date.date(), end_date.date()),
                type_final=invoice_type,
                payments__is_active=True,
                exploitation__isnull=False,
            ).exclude(
                Q(status__token__in=[status_cancelled_token])
                & (Q(return_token__isnull=True) | Q(return_token__exact=""))
            ).distinct()
            invoices = filter_pending_invoices(invoices, request)
        elif has_serie_range:
            # Seleccio nomes pel rang de numero de factura: el rang ja identifica les
            # factures, sense lot ni periode. filter_pending_invoices hi aplica el rang
            # (apply_serie_final_range) i el periode surt de les factures resultants,
            # que es el que fan servir els titols i el nom del fitxer.
            invoices = filter_pending_invoices(serie_final_range_invoices(), request)
            start_date, end_date = serie_final_range_period(invoices)
            if start_date is None:
                return Response({"error": "the serie_final range has no invoices."}, status=status.HTTP_400_BAD_REQUEST), None, None
        else:
            raise Exception("Error obtaining invoices for report aca summary")

        if exploitation:
            invoices = invoices.filter(exploitation=exploitation)
        if company_id:
            invoices = invoices.filter(company_id=company_id)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        """ unique_exploitations = invoices.values_list('exploitation__name', flat=True).distinct()
        if not unique_exploitations.exists():
            if exploitation:
                unique_exploitations = [exploitation.name]
            else:
                unique_exploitations = list(Exploitation.objects.values_list('name', flat=True).distinct()) """

        unique_exploitations = list(Exploitation.objects.order_by('name').values_list('name', flat=True).distinct())

        for exploitation_name in unique_exploitations:
            print(exploitation_name)
        
        aca_product_token = ConfigProject.objects.get(token="token_product_aca").value
        # aca_dom_price_rates_tokens = ConfigProject.objects.get(token="token_price_rate_aca_dom").value.split('|')
        pre_invoice_token = ConfigProject.objects.get(token="invoice_status_pending_token").value
        payoff_status_token = ConfigProject.objects.get(token="invoice_status_payoff_token").value
        exploitations = Exploitation.objects.all()
        contract_keeper_use_type_token = ConfigProject.objects.get(token="contract_keeper_use_type_token").value
        tarifa_social_token = ConfigProject.objects.get(token='tarifa_social').value
        
        part_fixa_token, part_variable_token = _get_aca_part_tokens()
        first_invoice = invoices.first()
        billing_date = end_date if end_date else first_invoice.issue_date if (first_invoice and id and billing) else datetime.datetime.now()
        _aca_invoice_ids, _invoices_by_exploitation, _totals_dict, aca_line_items_qs = _get_aca_invoices_data(
            invoices, aca_product_token, pre_invoice_token
        )
        # Amb múltiples empreses el codi és el de l'empresa de les factures (totes la mateixa);
        # si no, el de l'empresa de cada explotació.
        aca_company = get_records_company(_aca_invoices_company_ids(_aca_invoice_ids)) if use_multiple_companies() else None
        
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("Facturació ACA")
        serie_final_sheet = wb.create_sheet(title=_("Factures"))
        
        row = 0
        serie_final_row = 0
        
        title = _("Facturació ACA %(date)s") % {"date": billing.created_at.strftime('%d/%m/%Y')} if billing else _("Facturacions ACA %(start)s - %(end)s") % {"start": start_date.strftime('%d/%m/%Y'), "end": end_date.strftime('%d/%m/%Y')}
        serie_final_header = [_("Número de factura"), _("Estat"), _("Consum factura"), _("Consum aca variable"), _("Consum aca fixa"), _("Import factura"), _("Import aca variable"), _("Import aca fixa"), _("ACA Token")]
        
        main_title = [title]
        row = add_row(sheet, row, main_title)
        serie_final_row = add_row(serie_final_sheet, serie_final_row, serie_final_header, fill=black_fill, font=white_bold_font)
        
        # Metric titles (these will become the first column, one metric per row)
        titles = [
            _("Població/Explotació"), _("Codi ent. Subministradora"), _("Codi INE"), _("Soc. emissora"), _("Soc. propietària"), _("Règim"),
            _("Periode inicial"), _("Periode final"),
            _("Import part fixa"), _("Import part variable"), _("Import total"),
            _("Vol. consumit d'ús domèstic"), _("Vol. consumit d'ús industrial gen/esp"), _("Vol. consumit d'ús industrial només general"), _("Vol. consumit d'ús ramader"),
            _("Vol. facturat d'ús domèstic"), _("Vol. facturat d'ús industrial gen/esp"), _("Vol. facturat d'ús industrial només general"), _("Vol. facturat d'ús ramader"),
            _("Mesurament directe"), _("Exempt"), _("Ramader quota 0"),
        ]
        
        for i in range(4):
            titles.append(_("Sense tarifa social TRAM %(num)s") % {"num": i+1})
        for i in range(4):
            titles.append(_("Tarifa social 50%% TRAM %(num)s") % {"num": i+1})
        titles.append(_("Tarifa social 0"))

        # We will build a transposed table:
        # - First column: metric name (from titles)
        # - Next columns: one column per exploitation with its value for that metric
        exploitation_names = []
        exploitation_rows = []

        price_rate_dict = {}
        print("before loop")
        for exploitation in unique_exploitations:
            print(f"exploitation: {exploitation}")
            try:
                aca_line_items_ex = aca_line_items_qs.filter(invoice__exploitation__name=exploitation).distinct().annotate(
                    effective_use_aca=_aca_effective_use_annotation()
                )
                invoices_exploitation = Invoice.objects.filter(id__in=aca_line_items_ex.values_list('invoice__id', flat=True)).select_related('status', 'contract').distinct()
                """ if aca_line_items_qs.count() == 0:
                    continue """
                print(f"\n\n\naca line items qs: {aca_line_items_ex.count()}, {exploitation}")
                exploitation_instance = exploitations.get(name=exploitation)
                unique_use_aca = aca_line_items_ex.values_list('effective_use_aca', flat=True).distinct()
                print(f"unique use aca: {unique_use_aca}")

                written_invoice_ids = set()
                empty_effective_use_q = Q(effective_use_aca__isnull=True) | Q(effective_use_aca='')

                lines_no_type = aca_line_items_ex.filter(empty_effective_use_q, price_unit__range=(-0.001, 0.001)).distinct()
                if lines_no_type.exists():
                    print("no type found for invoice: ", lines_no_type.first().invoice.serie_final)
                #DOM
                dom_lines = aca_line_items_ex.filter(effective_use_aca="D").distinct()
                dom_lines_list = list(dom_lines)
                dom_lines_by_invoice = {}
                for l in dom_lines_list:
                    dom_lines_by_invoice.setdefault(l.invoice_id, []).append(l)

                dom_invoices = invoices_exploitation.filter(id__in=dom_lines.values_list('invoice__id', flat=True)).distinct()
                
                serie_final_row = _add_invoices_to_sheet(serie_final_sheet, serie_final_row, dom_invoices, dom_lines, part_fixa_token, written_invoice_ids=written_invoice_ids)
                
                print(f"total_billed {aca_line_items_ex.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                print(f"dom lines units: {dom_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                print(f"dom lines units: {dom_lines.exclude(line_item_type__article__token=part_fixa_token).distinct().aggregate(total_units=Sum('units'))['total_units'] or 0}")
                
                # ALTA
                alta_lines = aca_line_items_ex.filter(effective_use_aca="L").distinct()
                alta_invoices = invoices_exploitation.filter(id__in=alta_lines.values_list('invoice__id', flat=True)).distinct()
                
                serie_final_row = _add_invoices_to_sheet(serie_final_sheet, serie_final_row, alta_invoices, alta_lines, part_fixa_token, written_invoice_ids=written_invoice_ids)
                print(f"alta lines units: {alta_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                
                #IND
                #watch out on diff corr, currently getting by price_unit
                ind_lines = aca_line_items_ex.filter(effective_use_aca="I").exclude(
                        price_unit__range=(-0.001, 0.001)).distinct()
                ind_invoices = invoices_exploitation.filter(id__in=ind_lines.values_list('invoice__id', flat=True)).distinct()
                print(f"ind lines units: {ind_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                
                serie_final_row = _add_invoices_to_sheet(serie_final_sheet, serie_final_row, ind_invoices, ind_lines, part_fixa_token, is_industrial=True, written_invoice_ids=written_invoice_ids)

                ind_lines_free = aca_line_items_ex.filter(price_unit__range=(-0.001, 0.001)).filter(
                    Q(effective_use_aca="I") | empty_effective_use_q
                    ).exclude(invoice__contract__use_type__token=contract_keeper_use_type_token).distinct()   #not only ind
                ind_invoices_free = invoices_exploitation.filter(id__in=ind_lines_free.values_list('invoice__id', flat=True)).distinct()
                # print(f"ind lines free units: {ind_lines_free.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                serie_final_row = _add_invoices_to_sheet(serie_final_sheet, serie_final_row, ind_invoices_free, ind_lines_free, part_fixa_token, "E", is_industrial=True, written_invoice_ids=written_invoice_ids)
                #KEEPER
                # keeper_lines = aca_line_items_ex.filter(invoice__contract__use_aca="I", invoice__contract__use_type__token=contract_keeper_use_type_token).distinct()
                #KEEPER
                # print(f"contract_keeper_use_type_token: {contract_keeper_use_type_token}")
                        
                # keeper_lines = aca_line_items_ex.filter(
                #     effective_use_aca__in=["I", "Q"],
                #     invoice__contract__use_type__token=contract_keeper_use_type_token
                # ).distinct()
                # print(f"keeper lines count: {keeper_lines.count()}")
                # keeper_invoices = invoices_exploitation.filter(id__in=keeper_lines.values_list('invoice__id', flat=True)).distinct()
                # serie_final_row = _add_invoices_to_sheet(serie_final_sheet, serie_final_row, keeper_invoices, keeper_lines, part_fixa_token, is_industrial=True, written_invoice_ids=written_invoice_ids)
                # print(f"keeper lines units: {keeper_lines.aggregate(total_units=Sum('total'))['total_total'] or 0}")
                
                #MUN
                mun_lines = aca_line_items_ex.filter(effective_use_aca="A").distinct()
                mun_invoices = invoices_exploitation.filter(id__in=mun_lines.values_list('invoice__id', flat=True)).distinct()
                print(f"mun lines units: {mun_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                serie_final_row = _add_invoices_to_sheet(serie_final_sheet, serie_final_row, mun_invoices, mun_lines, part_fixa_token, written_invoice_ids=written_invoice_ids)
                #KEEPER FREE
                keeper_free_lines = aca_line_items_ex.filter(effective_use_aca="Q").distinct()
                keeper_free_invoices = invoices_exploitation.filter(id__in=keeper_free_lines.values_list('invoice__id', flat=True)).distinct()
                serie_final_row = _add_invoices_to_sheet(serie_final_sheet, serie_final_row, keeper_free_invoices, keeper_free_lines, part_fixa_token, "Q", is_industrial=True, written_invoice_ids=written_invoice_ids)
                print(f"keeper free lines units: {keeper_free_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                none_line_items = aca_line_items_ex.filter(empty_effective_use_q).distinct()
                for line in none_line_items:
                    print(f"none line item: {line.invoice.serie_final}")
                all_ind_lines = aca_line_items_ex.filter(effective_use_aca="I").distinct()
                print(f"all ind lines units: {all_ind_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                #DIRECT
                direct_free_lines = aca_line_items_ex.filter(effective_use_aca="M").distinct()
                direct_free_invoices = invoices_exploitation.filter(id__in=direct_free_lines.values_list('invoice__id', flat=True)).distinct()
                serie_final_row = _add_invoices_to_sheet(serie_final_sheet, serie_final_row, direct_free_invoices, direct_free_lines, part_fixa_token, "M", is_industrial=True, written_invoice_ids=written_invoice_ids)
                
                lines_part_fixa = aca_line_items_ex.filter(line_item_type__article__token=part_fixa_token).distinct()
                print(f"total units fixa: {lines_part_fixa.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                # lines_part_variable = aca_line_items_ex.filter(line_item_type__article__token=part_variable_token).distinct() # if not variable found but is domestic and interval trea
                # lines_no_line_item_type = aca_line_items_ex.filter(line_item_type__isnull=True) #if no line item it SHOULD be variable (error with prev 2026)
                lines_part_variable = aca_line_items_ex.exclude(line_item_type__article__token=part_fixa_token).distinct()
                
                # DOM SOCIAL
                dom_not_social = {}
                dom_social = {}
                dom_social_0 = 0
                dom_no_fixa = 0
                for i in range(4):
                    dom_not_social[i + 1] = 0
                    dom_social[i + 1] = 0

                invoice_interval_cache = {} 
                invoice_leak_cache = {}     
                dom_no_fixa = sum(l.units or 0 for l in dom_lines_list if l.line_item_type and l.line_item_type.article and l.line_item_type.article.token == part_fixa_token)

                print("-- part fixa token: ", part_fixa_token)
                dom_lines_exclude_fixa = [l for l in dom_lines_list if not (l.line_item_type and l.line_item_type.article and l.line_item_type.article.token == part_fixa_token)]
                for dom_line in dom_lines_exclude_fixa:
                    """ if dom_line.line_item_type and dom_line.line_item_type.quantity and dom_line.line_item_type.quantity.token == 'diferencia_fuita':
                        print("diferencia fuita")
                        continue """
                    if dom_line.line_item_type and dom_line.line_item_type.article:
                        print(f"------ 8< ------- \n\n\n\ndom line: {dom_line.id}, {dom_line.line_item_type.article.token}")
                    else:
                        print(f"------ 8< ------- \n\n\ndom line: {dom_line.id}, no line item type or article")

                    invoice = dom_line.invoice
                    invoice_id = dom_line.invoice_id
                    # Warn when units are not a whole number (robust for Decimal/float/str)
                    units_value = dom_line.units
                    if units_value is not None:
                        try:
                            normalized_units = Decimal(str(units_value))
                            if normalized_units != normalized_units.to_integral_value():
                                print("WARNING: dom line units has decimals: ", dom_line.units)
                        except Exception:
                            print("WARNING: could not parse dom line units for decimal check: ", dom_line.units)

                    effective_interval = dom_line.interval
                    if not effective_interval:
                        leak_total = invoice_leak_cache.get(invoice_id)
                        if leak_total is None:
                            leak_total = sum(r.leak_value or 0 for r in invoice.readings.all())
                            invoice_leak_cache[invoice_id] = leak_total

                        if (
                            dom_line.units
                            and dom_line.units > 0
                            and leak_total
                            and dom_line.units == leak_total
                        ):
                            effective_interval = 1
                        else:
                            if invoice_id not in invoice_interval_cache:
                                invoice_dom_lines = dom_lines_by_invoice.get(invoice_id, [])
                                invoice_dom_lines = sorted(invoice_dom_lines, key=lambda l: (-l.price_unit, l.id))
                                ordered_prices = []
                                for l in invoice_dom_lines:
                                    if l.price_unit not in ordered_prices:
                                        ordered_prices.append(l.price_unit)
                                price_to_interval = {
                                    price: idx + 1
                                    for idx, price in enumerate(ordered_prices)
                                }
                                invoice_interval_cache[invoice_id] = price_to_interval
                            else:
                                price_to_interval = invoice_interval_cache[invoice_id]

                            effective_interval = price_to_interval.get(dom_line.price_unit)

                    applied_adjustments = []
                    
                    if hasattr(dom_line, "adjustments") and dom_line.adjustments:
                        if dom_line.adjustments.all(): 
                            print(f"line item: {dom_line.id}, {dom_line.name}, {dom_line.token}, {dom_line.adjustments.all()}")
                        for adjustment in dom_line.adjustments.all():
                            print(f"adjustment: {adjustment.id}, {adjustment.name}, {adjustment.token}")
                        applied_adjustments.extend(dom_line.adjustments.all())

                    has_social_adjustment = False
                    for adj in applied_adjustments:
                        adjustment_obj = getattr(adj, "adjustment", None)
                        if not adjustment_obj:
                            continue
                        conditions_manager = getattr(adjustment_obj, "conditions", None)
                        if not conditions_manager:
                            continue

                        for cond in conditions_manager.all():
                            cond_quantity = getattr(cond, "quantity", None)
                            if ( not isinstance(cond_quantity, dict) ):
                                continue

                            if (
                                cond_quantity.get("value") == f"variable.{tarifa_social_token}"
                                and cond.operation != "is_null"
                            ):
                                has_social_adjustment = True
                                break
                        if has_social_adjustment:
                            break

                    if has_social_adjustment:
                        # print(f"has social adjustment: {invoice.serie_final}, {dom_line.price_unit}, {effective_interval}")
                        if dom_line.price_unit < 0.01:
                            dom_social_0 += dom_line.units
                        else:
                            if effective_interval and 1 <= effective_interval <= 4:
                                print(f"has social adjustment: {invoice.serie_final}, {dom_line.id}, {effective_interval}");
                                dom_social[effective_interval] += dom_line.units
                            else:
                                print("ERROR: no interval (social) found for invoice: ", invoice.serie_final)
                                dom_social[1] += dom_line.units
                    else:
                        if effective_interval and 1 <= effective_interval <= 4:
                            dom_not_social[effective_interval] += dom_line.units
                        else:
                            print("ERROR: no interval (not social) found for invoice: ", invoice.serie_final)
                            dom_not_social[1] += dom_line.units
                most_used_date_range = (None, None)
                invoice_issue_dates = list(
                    invoices_exploitation.values_list("issue_date", flat=True)
                )
                total_invoices_ex = len(invoice_issue_dates)
                if total_invoices_ex:
                    issue_date_counts = {}
                    for d in invoice_issue_dates:
                        if not d:
                            continue
                        issue_date_counts[d] = issue_date_counts.get(d, 0) + 1

                    target_invoices = invoices_exploitation
                    if issue_date_counts:
                        most_common_issue_date, most_common_count = max(
                            issue_date_counts.items(), key=lambda x: x[1]
                        )
                        if (most_common_count / float(total_invoices_ex)) >= 0.2:
                            target_invoices = invoices_exploitation.filter(
                                issue_date=most_common_issue_date
                            )

                    prev_ordinals = []
                    curr_ordinals = []
                    target_invoices = target_invoices.select_related("contract").prefetch_related(
                        "readings__previous_reading"
                    )
                    for inv in target_invoices:
                        readings = sorted(
                            list(inv.readings.all()),
                            key=lambda r: r.reading_date or datetime.date.min,
                            reverse=True,
                        )
                        if not readings:
                            continue
                        reading_obj = readings[0]
                        current_date = reading_obj.reading_date
                        previous_date = None
                        if reading_obj.previous_reading and reading_obj.previous_reading.reading_date:
                            previous_date = reading_obj.previous_reading.reading_date
                        elif current_date and inv.contract and inv.contract.created_at:
                            previous_date = inv.contract.created_at.date()

                        if previous_date and current_date:
                            prev_ordinals.append(previous_date.toordinal())
                            curr_ordinals.append(current_date.toordinal())

                    if prev_ordinals and curr_ordinals:
                        avg_prev = datetime.date.fromordinal(
                            round(sum(prev_ordinals) / len(prev_ordinals))
                        )
                        avg_curr = datetime.date.fromordinal(
                            round(sum(curr_ordinals) / len(curr_ordinals))
                        )
                        most_used_date_range = (avg_prev, avg_curr)

                total_dom_consumption = 0   #actually use this to avoid variations caused by decimals
                total_dom_consumption += sum(dom_not_social.values())
                total_dom_consumption += sum(dom_social.values())
                total_dom_consumption += dom_social_0
                
                fallback_start = start_date if start_date else (billing.created_at if (id and billing and billing.created_at) else billing_date)
                fallback_end = end_date if end_date else (billing.created_at if (id and billing and billing.created_at) else billing_date)

                # print(f"keeper invoices count: {keeper_invoices.count()}")

                supply_code_company = aca_company or exploitation_instance.company
                new_line = [
                    exploitation_instance.name.upper(), exploitation_instance.code, supply_code_company.supply_code if supply_code_company else None, 
                    exploitation_instance.company.name if exploitation_instance.company else '', exploitation_instance.company.name if exploitation_instance.company else '', exploitation_instance.company.type.name if exploitation_instance.company and exploitation_instance.company.type else '',
                    most_used_date_range[0].strftime('%m/%Y') if most_used_date_range[0] else fallback_start.strftime('%m/%Y'),
                    most_used_date_range[1].strftime('%m/%Y') if most_used_date_range[1] else fallback_end.strftime('%m/%Y'),
                    
                    lines_part_fixa.aggregate(total=Sum('price'))['total'] or 0,
                    lines_part_variable.aggregate(total=Sum('price'))['total'] or 0,
                    aca_line_items_ex.aggregate(total=Sum('price'))['total'] or 0,
                    
                    _get_signed_invoice_consumption_total(dom_invoices, payoff_status_token),
                    _get_signed_invoice_consumption_total(ind_invoices, payoff_status_token),
                    _get_signed_invoice_consumption_total(mun_invoices, payoff_status_token),
                    # _get_signed_invoice_consumption_total(keeper_invoices, payoff_status_token),
                    0,

                    # int(dom_lines.exclude(line_item_type__article__token=part_fixa_token).distinct().aggregate(total_units=Sum('units'))['total_units'] or 0),
                    total_dom_consumption,
                    int(ind_lines.filter(line_item_type__quantity__token='diferencia_fuita_consum').exclude(line_item_type__article__token=part_fixa_token).distinct().aggregate(total_units=Sum('units'))['total_units'] or 0),
                    int(mun_lines.exclude(line_item_type__article__token=part_fixa_token).distinct().aggregate(total_units=Sum('units'))['total_units'] or 0),
                    # int(keeper_lines.filter(line_item_type__quantity__token='diferencia_fuita_consum').exclude(line_item_type__article__token=part_fixa_token).distinct().aggregate(total_units=Sum('units'))['total_units'] or 0),
                    0,
                    # int(keeper_invoices.aggregate(total_units=Sum('consumption'))['total_units'] or 0),

                    _get_signed_invoice_consumption_total(direct_free_invoices, payoff_status_token),
                    _get_signed_invoice_consumption_total(ind_invoices_free, payoff_status_token),
                    #ind_lines_free.aggregate(total_units=Sum('units'))['total_units'] or 0,
                    _get_signed_invoice_consumption_total(keeper_free_invoices, payoff_status_token),
                    #keeper_free_lines.aggregate(total_units=Sum('units'))['total_units'] or 0,
                ]
                
                for i in range(4):
                    new_line.append((dom_not_social[i+1]))
                for i in range(4):
                    new_line.append((dom_social[i+1]))
                new_line.append((dom_social_0))
            except Exception as e:
                print(f"Error adding line for exploitation {exploitation}: {e}")
                raise e

            exploitation_names.append(exploitation_instance.name.upper())
            exploitation_rows.append(new_line)


        for idx, metric_name in enumerate(titles):
            metric_row = [metric_name]
            for exploitation_row in exploitation_rows:
                value = exploitation_row[idx] if idx < len(exploitation_row) else ""
                metric_row.append(value)
            row = add_row(sheet, row, metric_row)

        #row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)
        print("sheet done")
        adjust_column_widths(sheet)
        
        # Create second sheet with invoice serie_final values
        
        
        # Get all serie_final values from the invoices used
        """ invoices_serie_final = Invoice.objects.filter(
            id__in=aca_invoice_ids
        ).distinct()
        
        # Add each serie_final as a row
        for inv in invoices_serie_final:
            inv_aca_line_items = aca_line_items_qs.filter(invoice=inv).distinct()
            invoice_line = [
               inv.serie_final, inv.status.name, 
               inv.consumption, 
               inv_aca_line_items.aggregate(total_units=Sum('units'))['total_units'] or 0,
               inv.total_final,
               inv_aca_line_items.aggregate(total=Sum('price'))['total'] or 0,
               inv.contract.use_aca if inv.contract else '',
            ]
            serie_final_row = add_row(serie_final_sheet, serie_final_row, invoice_line) """
        
        adjust_column_widths(serie_final_sheet)
            
        filename = f"billing_aca_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        print("saving report")
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id, start_date=start_date, end_date=end_date)
        print("got document id", document_id)
        os.remove(filename)
        return response, document_id, None
    except ACACompanyError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST), None, None
    except Exception as e:
        error_response = Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return error_response, None, None

def _add_invoices_to_sheet(sheet, row, invoices, aca_lines, part_fixa_token, forced_aca = None, is_industrial = False, written_invoice_ids=None):
    print(f"adding invoices to sheet, is_industrial: {is_industrial}")
    aca_lines_list = list(aca_lines)
    lines_by_invoice = {}
    unique_invoices = {}
    for line in aca_lines_list:
        lines_by_invoice.setdefault(line.invoice_id, []).append(line)
        unique_invoices[line.invoice_id] = line.invoice
        
    for inv in unique_invoices.values():
        if written_invoice_ids is not None:
            if inv.id in written_invoice_ids:
                continue
            written_invoice_ids.add(inv.id)
        inv_lines = lines_by_invoice.get(inv.id, [])
        inv_lines_units = inv_lines
        if is_industrial:
            inv_lines_units = [l for l in inv_lines_units if l.line_item_type and l.line_item_type.quantity and l.line_item_type.quantity.token == 'diferencia_fuita_consum']
            
        units_ex_fixa = sum(l.units or 0 for l in inv_lines_units if not (l.line_item_type and l.line_item_type.article and l.line_item_type.article.token == part_fixa_token))
        units_inc_fixa = sum(l.units or 0 for l in inv_lines_units if l.line_item_type and l.line_item_type.article and l.line_item_type.article.token == part_fixa_token)
        price_ex_fixa = sum(l.price or 0 for l in inv_lines if not (l.line_item_type and l.line_item_type.article and l.line_item_type.article.token == part_fixa_token))
        price_inc_fixa = sum(l.price or 0 for l in inv_lines if l.line_item_type and l.line_item_type.article and l.line_item_type.article.token == part_fixa_token)
        
        consumption_real = inv.real_consumption or 0
        if inv.status.token == "-2" and consumption_real > 0: # payoff_status_token , si és un abonament hem de posar el consum en negatiu
            consumption_real = -consumption_real
            

        invoice_line = [
            inv.serie_final, inv.status.name, 
            consumption_real, # inv.consumption,   --> he posat consumption_bag que en veritat és el real_consumption
            units_ex_fixa,
            round_ceil(float(units_inc_fixa)),
            inv.total_final, 
            price_ex_fixa,
            price_inc_fixa,
            forced_aca if forced_aca else _invoice_effective_use_aca(inv),
        ]
        row = add_row(sheet, row, invoice_line)
    return row

def generate_aca_summary_report_second_ver(request, black_fill=None, white_bold_font=None, task=None):
    try:
        print("getting ACA summary")
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        billing_ids = get_billing_ids(request.data)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        # Amb múltiples empreses cada fitxer ACA és d'una sola empresa (veure resolve_aca_company)
        company_id = request.data.get('company_id', None)
        has_serie_range = has_serie_final_range(request.data)
        if not billing_ids and not date_range and not has_serie_range:
            return Response({"error": "billing id, date range or serie_final range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        print("got id or date range")
        billing = None
        billings = []
        start_date = None
        end_date = None
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        
        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            invoices = filter_pending_invoices(invoices, request)
            billing = get_object_or_404(Billing, id=billing_ids[0])
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
            invoices = Invoice.objects.filter(issue_date__range=(start_date.date(), end_date.date()), type_final=invoice_type, payments__is_active=True).distinct()
            invoices = filter_pending_invoices(invoices, request)
        elif has_serie_range:
            # Seleccio nomes pel rang de numero de factura: el rang ja identifica les
            # factures, sense lot ni periode. filter_pending_invoices hi aplica el rang
            # (apply_serie_final_range) i el periode surt de les factures resultants,
            # que es el que fan servir els titols i el nom del fitxer.
            invoices = filter_pending_invoices(serie_final_range_invoices(), request)
            start_date, end_date = serie_final_range_period(invoices)
            if start_date is None:
                return Response({"error": "the serie_final range has no invoices."}, status=status.HTTP_400_BAD_REQUEST), None, None
        else:
            raise Exception("Error obtaining invoices for report aca summary")

        if exploitation:
            invoices = invoices.filter(exploitation=exploitation)
        if company_id:
            invoices = invoices.filter(company_id=company_id)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        """ unique_exploitations = invoices.values_list('exploitation__name', flat=True).distinct()
        if not unique_exploitations.exists():
            if exploitation:
                unique_exploitations = [exploitation.name]
            else:
                unique_exploitations = list(Exploitation.objects.values_list('name', flat=True).distinct()) """
        unique_exploitations = list(Exploitation.objects.values_list('name', flat=True).distinct())
        if not unique_exploitations:
            return Response({"error": "No hi ha cap explotació per generar la declaració."}, status=status.HTTP_400_BAD_REQUEST), None, None
        for exploitation_name in unique_exploitations:
            print(exploitation_name)
        
        aca_product_token = ConfigProject.objects.get(token="token_product_aca").value
        pre_invoice_token = ConfigProject.objects.get(token="invoice_status_pending_token").value
        payoff_status_token = ConfigProject.objects.get(token="invoice_status_payoff_token").value
        exploitations = Exploitation.objects.all()
        contract_keeper_use_type_token = ConfigProject.objects.get(token="contract_keeper_use_type_token").value
        tarifa_social_token = ConfigProject.objects.get(token='tarifa_social').value
        main_company_token = ConfigProject.objects.get(token='main_company_token').value
        
        part_fixa_token, part_variable_token = _get_aca_part_tokens()
        _aca_invoice_ids, _invoices_by_exploitation, _totals_dict, aca_line_items_qs = _get_aca_invoices_data(
            invoices, aca_product_token, pre_invoice_token
        )
        # Empresa declarant: codi d'entitat subministradora i NIF de tot el fitxer.
        company = resolve_aca_company(
            _aca_invoices_company_ids(_aca_invoice_ids),
            Company.objects.filter(vat=main_company_token).first(),
        )
        
        exploitation_names = []
        exploitation_rows = []
        
        price_rate_dict = {}
        
        # FIRST TRY UNIQUE, IF NOT, TRY +1 FILE FOR EACH EXPLOTATION AND RETURN ZIP
        title_doc_id = "000" # +1 for each exploitation if done
        supply_type = "ES"   # 'AP' SI PRESENTA UNA ENTITAT QUE ACTUA COM A APODERA, 'ES' SI ÉS ENTITAT SUBMINISTRADORA
        aca_code = company.supply_code
        doc_date = datetime.datetime.now()
        first_invoice = invoices.first()
        billing_date = end_date if end_date else first_invoice.issue_date if (first_invoice and id and billing) else datetime.datetime.now()
        unique_billing_months = invoices.values_list('issue_date__month', flat=True).distinct()
        selected_month = _aca_date_range_month(start_date, end_date)
        invoices_are_monthly = first_invoice and all(
            invoice.billing_period_days is not None and invoice.billing_period_days <= 31
            for invoice in invoices
        ) and len(unique_billing_months) == 1
        if selected_month:
            billing_period = f"{selected_month:02d}"
        elif invoices_are_monthly:
            billing_period = f"{first_invoice.issue_date.month:02d}"
        else:
            selected_trimester = _aca_date_range_trimester(start_date, end_date)
            if selected_trimester:
                trimester = selected_trimester
            elif start_date and end_date:
                return Response(
                    {
                        "warning": _(
                            "El període de la declaració ACA ha de ser un mes o un "
                            "trimestre natural complet (T1 gen-mar, T2 abr-jun, "
                            "T3 jul-set, T4 oct-des). El rang seleccionat no ho és."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                ), None, None
            else:
                invoice_with_period = invoices.filter(billing_period_days__isnull=False).first()
                p_month = invoice_with_period.billing_period_month if invoice_with_period else (
                    first_invoice.issue_date.month if first_invoice else billing_date.month
                )
                trimester = _aca_trimester_from_month(p_month)
            billing_period = f"T{trimester}"
        
        title = f"DMC{supply_type}{aca_code}{str(billing_date.year)}{str(billing_period)}{title_doc_id}"
        main_title = [title]
        # row = add_row(sheet, row, main_title)
        print("added title")
        
        header_line = [
            "10",supply_type,
            aca_code,
            company.vat,
            doc_date.strftime('%Y%m%d'),
            "DMC",
            str(billing_date.year),
            str(billing_period)
        ]
         #TODO LATER, SEPARATE INVOICES BY ISSUE DATE YEAR IN DIFF DOCUMENTS

        for exploitation in unique_exploitations:
            try:
                # SEPARAR CADA CAMP PER |
                # SI VALOR DE CAMP CHAR NO TÉ CONTINGUT, EL VALOR SERÀ 'NULL', SI ÉS NUMERIC SERÀ 0
                aca_line_items_ex = aca_line_items_qs.filter(invoice__exploitation__name=exploitation).distinct().annotate(
                    effective_use_aca=_aca_effective_use_annotation()
                )
                invoices_exploitation = Invoice.objects.filter(id__in=aca_line_items_ex.values_list('invoice__id', flat=True)).select_related('status', 'contract').distinct()
                # UNCOMMENT ONCE DONE
                """ if aca_line_items_qs.count() == 0:
                    continue """
                print(f"\n\n\naca line items qs: {aca_line_items_ex.count()}, {exploitation}")
                exploitation_instance = exploitations.get(name=exploitation)
                unique_use_aca = aca_line_items_ex.values_list('effective_use_aca', flat=True).distinct()
                print(f"unique use aca: {unique_use_aca}")

                empty_effective_use_q = Q(effective_use_aca__isnull=True) | Q(effective_use_aca='')

                lines_no_type = aca_line_items_ex.filter(empty_effective_use_q, price_unit__range=(-0.001, 0.001)).distinct()
                if lines_no_type.exists():
                    print("no type found for invoice: ", lines_no_type.first().invoice.serie_final)
                #DOM
                dom_lines = aca_line_items_ex.filter(effective_use_aca="D").distinct()
                dom_lines_list = list(dom_lines)
                dom_lines_by_invoice = {}
                for l in dom_lines_list:
                    dom_lines_by_invoice.setdefault(l.invoice_id, []).append(l)

                dom_invoices = invoices_exploitation.filter(id__in=dom_lines.values_list('invoice__id', flat=True)).distinct()
                
                print(f"total_billed {aca_line_items_ex.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                print(f"dom lines units: {dom_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                #IND
                #watch out on diff corr, currently getting by price_unit
                ind_lines = aca_line_items_ex.filter(effective_use_aca="I").exclude(
                    invoice__contract__use_type__token=contract_keeper_use_type_token).exclude(
                        price_unit__range=(-0.001, 0.001)).distinct()
                ind_invoices = invoices_exploitation.filter(id__in=ind_lines.values_list('invoice__id', flat=True)).distinct()
                print(f"ind lines units: {ind_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")

                ind_lines_free = aca_line_items_ex.filter(price_unit__range=(-0.001, 0.001)).filter(
                    Q(effective_use_aca="I") | empty_effective_use_q
                    ).exclude(invoice__contract__use_type__token=contract_keeper_use_type_token).distinct()   #not only ind
                ind_invoices_free = invoices_exploitation.filter(id__in=ind_lines_free.values_list('invoice__id', flat=True)).distinct()
                print(f"ind lines free units: {ind_lines_free.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                #KEEPER
                keeper_lines = aca_line_items_ex.filter(
                    effective_use_aca__in=["I", "Q"],
                    invoice__contract__use_type__token=contract_keeper_use_type_token
                ).distinct()
           
                print(f"keeper lines: {keeper_lines.count()}")

                keeper_invoices = invoices_exploitation.filter(id__in=keeper_lines.values_list('invoice__id', flat=True)).distinct()
                print(f"keeper lines units: {keeper_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                #MUN
                mun_lines = aca_line_items_ex.filter(effective_use_aca="A").distinct()
                mun_invoices = invoices_exploitation.filter(id__in=mun_lines.values_list('invoice__id', flat=True)).distinct()
                print(f"mun lines units: {mun_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                #KEEPER FREE
                keeper_free_lines = aca_line_items_ex.filter(effective_use_aca="Q").distinct()
                print(f"keeper free lines: {keeper_free_lines.count()}")
                
                keeper_free_invoices = invoices_exploitation.filter(id__in=keeper_free_lines.values_list('invoice__id', flat=True)).distinct()
                print(f"keeper free lines units: {keeper_free_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                none_line_items = aca_line_items_ex.filter(empty_effective_use_q).distinct()
                for line in none_line_items:
                    print(f"none line item: {line.invoice.serie_final}")
                all_ind_lines = aca_line_items_ex.filter(effective_use_aca="I").distinct()
                print(f"all ind lines units: {all_ind_lines.aggregate(total_units=Sum('units'))['total_units'] or 0}")
                #DIRECT
                direct_free_lines = aca_line_items_ex.filter(effective_use_aca="M").distinct()
                direct_free_invoices = invoices_exploitation.filter(id__in=direct_free_lines.values_list('invoice__id', flat=True)).distinct()
                
                lines_part_fixa = aca_line_items_ex.filter(line_item_type__article__token=part_fixa_token).distinct()
                # lines_part_variable = aca_line_items_ex.filter(line_item_type__article__token=part_variable_token).distinct() # if not variable found but is domestic and interval trea
                # lines_no_line_item_type = aca_line_items_ex.filter(line_item_type__isnull=True) #if no line item it SHOULD be variable (error with prev 2026)
                lines_part_variable = aca_line_items_ex.exclude(line_item_type__article__token=part_fixa_token).distinct()
                
                # DOM SOCIAL
                dom_not_social = {}
                dom_social = {}
                dom_social_0 = 0
                dom_no_fixa = 0
                for i in range(4):
                    dom_not_social[i + 1] = 0
                    dom_social[i + 1] = 0

                invoice_interval_cache = {} 
                invoice_leak_cache = {}     
                dom_no_fixa = sum(l.units or 0 for l in dom_lines_list if l.line_item_type and l.line_item_type.article and l.line_item_type.article.token == part_fixa_token)

                dom_lines_exclude_fixa = [l for l in dom_lines_list if not (l.line_item_type and l.line_item_type.article and l.line_item_type.article.token == part_fixa_token)]
                for dom_line in dom_lines_exclude_fixa:
                    """ if dom_line.line_item_type and dom_line.line_item_type.quantity and dom_line.line_item_type.quantity.token == 'diferencia_fuita':
                        print("diferencia fuita")
                        continue """
                    invoice = dom_line.invoice
                    invoice_id = dom_line.invoice_id
                    # Warn when units are not a whole number (robust for Decimal/float/str)
                    units_value = dom_line.units
                    if units_value is not None:
                        try:
                            normalized_units = Decimal(str(units_value))
                            if normalized_units != normalized_units.to_integral_value():
                                print("WARNING: dom line units has decimals: ", dom_line.units)
                        except Exception:
                            print("WARNING: could not parse dom line units for decimal check: ", dom_line.units)

                    effective_interval = dom_line.interval
                    if not effective_interval:
                        leak_total = invoice_leak_cache.get(invoice_id)
                        if leak_total is None:
                            leak_total = sum(r.leak_value or 0 for r in invoice.readings.all())
                            invoice_leak_cache[invoice_id] = leak_total

                        if (
                            dom_line.units
                            and dom_line.units > 0
                            and leak_total
                            and dom_line.units == leak_total
                        ):
                            effective_interval = 1
                        else:
                            if invoice_id not in invoice_interval_cache:
                                invoice_dom_lines = dom_lines_by_invoice.get(invoice_id, [])
                                invoice_dom_lines = sorted(invoice_dom_lines, key=lambda l: (-l.price_unit, l.id))
                                ordered_prices = []
                                for l in invoice_dom_lines:
                                    if l.price_unit not in ordered_prices:
                                        ordered_prices.append(l.price_unit)
                                price_to_interval = {
                                    price: idx + 1
                                    for idx, price in enumerate(ordered_prices)
                                }
                                invoice_interval_cache[invoice_id] = price_to_interval
                            else:
                                price_to_interval = invoice_interval_cache[invoice_id]

                            effective_interval = price_to_interval.get(dom_line.price_unit)

                    applied_adjustments = []
                    
                    if hasattr(dom_line, "adjustments") and dom_line.adjustments:
                        applied_adjustments.extend(dom_line.adjustments.all())
                        
                    has_social_adjustment = False
                    for adj in applied_adjustments:
                        adjustment_obj = getattr(adj, "adjustment", None)
                        if not adjustment_obj:
                            continue
                        conditions_manager = getattr(adjustment_obj, "conditions", None)
                        if not conditions_manager:
                            continue

                        for cond in conditions_manager.all():
                            cond_quantity = getattr(cond, "quantity", None)
                            if ( not isinstance(cond_quantity, dict) ):
                                continue

                            if (
                                cond_quantity.get("value") == f"variable.{tarifa_social_token}"
                                and cond.operation != "is_null" # pot tenir la variable per "negar-la", per validar que és null
                            ):
                                has_social_adjustment = True
                                break
                        if has_social_adjustment:
                            break

                    if has_social_adjustment:
                        if dom_line.price_unit < 0.01:
                            dom_social_0 += dom_line.units
                        else:
                            if effective_interval and 1 <= effective_interval <= 4:
                                dom_social[effective_interval] += dom_line.units
                            else:
                                print("ERROR: no interval (social) found for invoice: ", invoice.serie_final)
                                dom_social[1] += dom_line.units
                    else:
                        if effective_interval and 1 <= effective_interval <= 4:
                            dom_not_social[effective_interval] += dom_line.units
                        else:
                            print("ERROR: no interval (not social) found for invoice: ", invoice.serie_final)
                            dom_not_social[1] += dom_line.units

                most_used_date_range = (None, None)
                invoice_issue_dates = list(
                    invoices_exploitation.values_list("issue_date", flat=True)
                )
                total_invoices_ex = len(invoice_issue_dates)
                if total_invoices_ex:
                    issue_date_counts = {}
                    for d in invoice_issue_dates:
                        if not d:
                            continue
                        issue_date_counts[d] = issue_date_counts.get(d, 0) + 1

                    target_invoices = invoices_exploitation
                    if issue_date_counts:
                        most_common_issue_date, most_common_count = max(
                            issue_date_counts.items(), key=lambda x: x[1]
                        )
                        if (most_common_count / float(total_invoices_ex)) >= 0.2:
                            target_invoices = invoices_exploitation.filter(
                                issue_date=most_common_issue_date
                            )

                    prev_ordinals = []
                    curr_ordinals = []
                    target_invoices = target_invoices.select_related("contract").prefetch_related(
                        "readings__previous_reading"
                    )
                    for inv in target_invoices:
                        readings = sorted(
                            list(inv.readings.all()),
                            key=lambda r: r.reading_date or datetime.date.min,
                            reverse=True,
                        )
                        if not readings:
                            continue
                        reading_obj = readings[0]
                        current_date = reading_obj.reading_date
                        previous_date = None
                        if reading_obj.previous_reading and reading_obj.previous_reading.reading_date:
                            previous_date = reading_obj.previous_reading.reading_date
                        elif current_date and inv.contract and inv.contract.created_at:
                            previous_date = inv.contract.created_at.date()

                        if previous_date and current_date:
                            prev_ordinals.append(previous_date.toordinal())
                            curr_ordinals.append(current_date.toordinal())

                    if prev_ordinals and curr_ordinals:
                        avg_prev = datetime.date.fromordinal(
                            round(sum(prev_ordinals) / len(prev_ordinals))
                        )
                        avg_curr = datetime.date.fromordinal(
                            round(sum(curr_ordinals) / len(curr_ordinals))
                        )
                        most_used_date_range = (avg_prev, avg_curr)
                
                
                fallback_start = start_date if start_date else (billing.created_at if (id and billing and billing.created_at) else billing_date)
                fallback_end = end_date if end_date else (billing.created_at if (id and billing and billing.created_at) else billing_date)
                
                new_line = [
                    "20",
                    company.supply_code,
                    exploitation_instance.code,
                    
                    
                    
                    most_used_date_range[0].strftime('%m%Y') if most_used_date_range[0] else fallback_start.strftime('%m%Y'),
                    most_used_date_range[1].strftime('%m%Y') if most_used_date_range[1] else fallback_end.strftime('%m%Y'),
                    
                    (f"{(round_ceil(lines_part_fixa.aggregate(total=Sum('price'))['total'] or 0)):.2f}").replace(".", ","),
                    (f"{(round_ceil(lines_part_variable.aggregate(total=Sum('price'))['total'] or 0)):.2f}").replace(".", ","),
                    "0,00",   #IMPAGATS, AL ALTRE SI SURT PER DECLARAR, QUEDA EN BLANC
                    str(_get_signed_invoice_consumption_total(dom_invoices, payoff_status_token)),
                    str(_get_signed_invoice_consumption_total(ind_invoices, payoff_status_token)),
                    
                    str(int(ind_lines.filter(line_item_type__quantity__token='diferencia_fuita_consum').exclude(line_item_type__article__token=part_fixa_token).distinct().aggregate(total_units=Sum('units'))['total_units'] or 0)),
                    str(_get_signed_invoice_consumption_total(mun_invoices, payoff_status_token)),
                    str(int(mun_lines.exclude(line_item_type__article__token=part_fixa_token).distinct().aggregate(total_units=Sum('units'))['total_units'] or 0)),
                    
                    str(_get_signed_invoice_consumption_total(keeper_invoices, payoff_status_token)),
                    str(int(keeper_lines.filter(line_item_type__quantity__token='diferencia_fuita_consum').exclude(line_item_type__article__token=part_fixa_token).distinct().aggregate(total_units=Sum('units'))['total_units'] or 0)),
                    
                    str(_get_signed_invoice_consumption_total(direct_free_invoices, payoff_status_token)),
                    str(_get_signed_invoice_consumption_total(ind_invoices_free, payoff_status_token)),
                    str(_get_signed_invoice_consumption_total(keeper_free_invoices, payoff_status_token)),
                ]
                
                for i in range(4):
                    new_line.append(str(int(dom_not_social[i+1])))
                for i in range(4):
                    new_line.append(str(int(dom_social[i+1])))
                new_line.append(str(int(dom_social_0)))
            except Exception as e:
                print(f"Error adding line for exploitation {exploitation}: {e}")
                raise e

            exploitation_names.append(exploitation_instance.name.upper())
            line_str = "|".join(new_line)
            exploitation_rows.append(line_str)
        
        lines = []
        lines.append("|".join(header_line))
        lines.extend(exploitation_rows)
        csv_content = "\n".join(lines) + "\n"

        filename = f"{title}.csv"

        # Send the CSV file as a response
        response = HttpResponse(csv_content, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        
        document_id = save_report(
            content=csv_content,
            filename=filename,
            name=title,
            type_id=type_id,
            start_date=start_date,
            end_date=end_date,
        )
        
        return response, document_id, filename
    except ACACompanyError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST), None, None
    except Exception as e:
        error_response = Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return error_response, None, None



def generate_detailed_billing_summary(request, black_fill=None, white_bold_font=None, task=None):
    try:
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        billing_ids = get_billing_ids(request.data)
        name = request.data.get('name', '')
        ids = request.data.get('product_ids', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        
        has_serie_range = has_serie_final_range(request.data)
        if not billing_ids and not date_range and not has_serie_range:
            return Response({"error": "billing id, date range or serie_final range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        
        billing = None
        billings = []
        start_date = None
        end_date = None
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        
        if ids:
            product_ids = [int(i) for i in ids.split(',')]
            
        products = Product.objects.filter(id__in=product_ids).distinct() if ids else []
        
        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            invoices = filter_pending_invoices(invoices, request)
            billing = get_object_or_404(Billing, id=billing_ids[0])
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            # billings = Billing.objects.filter(created_at__range=(start_date.date(), end_date.date()))
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
            status_cancelled_token = ConfigProject.objects.get(token="invoice_status_cancelled_token").value
            # Excloure les anul·lades NOMÉS si no tenen una refactura/abonament lligat (return_token).
            # Les anul·lades amb return_token es mantenen perquè apareguin al detall (igual que a l'informe ACA).
            invoices = Invoice.objects.filter(
                issue_date__range=(start_date.date(), end_date.date()),
                type_final=invoice_type,
            ).exclude(
                Q(status__token__in=[status_cancelled_token])
                & (Q(return_token__isnull=True) | Q(return_token__exact=""))
            ).distinct()
            invoices = filter_pending_invoices(invoices, request)
        elif has_serie_range:
            # Seleccio nomes pel rang de numero de factura: el rang ja identifica les
            # factures, sense lot ni periode. filter_pending_invoices hi aplica el rang
            # (apply_serie_final_range) i el periode surt de les factures resultants,
            # que es el que fan servir els titols i el nom del fitxer.
            invoices = filter_pending_invoices(serie_final_range_invoices(), request)
            start_date, end_date = serie_final_range_period(invoices)
            if start_date is None:
                return Response({"error": "the serie_final range has no invoices."}, status=status.HTTP_400_BAD_REQUEST), None, None
        else:
            raise Exception("Error obtaining invoices for report billing summary")

        if exploitation:
            invoices = invoices.filter(exploitation=exploitation)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("Facturació")

        row = 0
        titles = [_("Explotació"), _("Factura"), _("Abonat"), _("Dies")]
        
        totals_sum = []
        for product in products:
            titles.append(f"{product.name} €")
            titles.append(_("%(name)s IVA %%") % {"name": product.name})
            
            totals_sum.append(0)
            totals_sum.append(0)
        titles.append(_("Total"))
        totals_sum.append(0)
        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)
        
        
        # Optimize by prefetching relations and line items
        invoices = invoices.select_related(
            'exploitation', 'payment_bank__person'
        ).prefetch_related('line_items')

        total_invoices_progress = invoices.count()
        for idx_invoice, i in enumerate(invoices, start=1):
            if task and idx_invoice % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx_invoice,
                        'total': total_invoices_progress,
                        'percent': round((idx_invoice / total_invoices_progress) * 100, 2) if total_invoices_progress else 0.0
                    }
                )
            index = 0
            person_id = i.payment_bank.person.token if (i.payment_bank and i.payment_bank.person) else " - "
            i_data = [i.exploitation.name if i.exploitation else "", i.serie_final or "", person_id, i.consumption_days if i.consumption_days else 0]
            
            # Group line items by product for this invoice in memory
            invoice_line_items = list(i.line_items.all())
            line_items_by_product = {}
            for li in invoice_line_items:
                if li.product_id not in line_items_by_product:
                    line_items_by_product[li.product_id] = []
                line_items_by_product[li.product_id].append(li)

            for product in products:
                items = line_items_by_product.get(product.id, [])
                
                price_sum = sum(li.price or 0 for li in items)
                tax_price_sum = sum(li.tax_price or 0 for li in items)

                i_data.append(price_sum)
                i_data.append(tax_price_sum)
                
                totals_sum[index] += price_sum
                totals_sum[index + 1] += tax_price_sum
                index += 2
            
            i_data.append(i.total_final)
            totals_sum[index] += i.total_final
            
            colored =  [i for i in range(0, len(i_data) + 1) if i % 2 == 0]
            
            row = add_row(sheet, row, i_data, colored=colored)
        totals = [_("Totals"), invoices.count(), "", ""]
        totals.extend(totals_sum)
        
        row = add_row(sheet, row, totals, fill=black_fill, font=white_bold_font)
        adjust_column_widths(sheet)
        
        filename = f"billing_detailed_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id, start_date=start_date, end_date=end_date)
        
        os.remove(filename)
        return response, document_id, None
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def generate_billing_summary_by_supply_type(request, black_fill=None, white_bold_font=None, task=None):
    try:
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        billing_ids = get_billing_ids(request.data)
        name = request.data.get('name', '')
        ids = request.data.get('product_ids', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        
        has_serie_range = has_serie_final_range(request.data)
        if not billing_ids and not date_range and not has_serie_range:
            return Response({"error": "billing id, date range or serie_final range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        
        billing = None
        billings = []
        start_date = None
        end_date = None
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        
        if ids:
            product_ids = [int(i) for i in ids.split(',')]
        products = Product.objects.filter(id__in=product_ids).distinct() if ids else []
        
        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            invoices = filter_pending_invoices(invoices, request)
            billing = get_object_or_404(Billing, id=billing_ids[0])
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
            invoices = Invoice.objects.filter(issue_date__range=(start_date.date(), end_date.date()), type_final=invoice_type).distinct()
            invoices = filter_pending_invoices(invoices, request)
        elif has_serie_range:
            # Seleccio nomes pel rang de numero de factura: el rang ja identifica les
            # factures, sense lot ni periode. filter_pending_invoices hi aplica el rang
            # (apply_serie_final_range) i el periode surt de les factures resultants,
            # que es el que fan servir els titols i el nom del fitxer.
            invoices = filter_pending_invoices(serie_final_range_invoices(), request)
            start_date, end_date = serie_final_range_period(invoices)
            if start_date is None:
                return Response({"error": "the serie_final range has no invoices."}, status=status.HTTP_400_BAD_REQUEST), None, None
        else:
            raise Exception("Error obtaining invoices for report billing summary by supply type")

        if exploitation:
            invoices = invoices.filter(exploitation=exploitation)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        supply_types = SupplyPointType.objects.all()

        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("Facturació")
        
        row = 0
        titles = [_("Tipus"), _("Factures"), _("usuaris reals"), _("m3 facturats")]
        
        totals_products = []
        for product in products:
            titles.append(_("Import %(name)s") % {"name": product.name})
            totals_products.append(0)
        
        titles.append(_("Total"))
        
        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)
        
        total_persons = 0
        total_consumption = 0
        total_price = 0
        
        # Pre-fetch all necessary data
        invoices = invoices.select_related(
            'contract__supply_point_default__type',
            'contract__holder'
        ).prefetch_related('line_items')
        
        # Group invoices by supply type in memory
        invoices_by_supply_type = {}
        total_invoices_progress = invoices.count()
        for idx_invoice, inv in enumerate(invoices, start=1):
            if task and idx_invoice % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx_invoice,
                        'total': total_invoices_progress,
                        'percent': round((idx_invoice / total_invoices_progress) * 100, 2) if total_invoices_progress else 0.0
                    }
                )
            st = inv.contract.supply_point_default.type if (inv.contract and inv.contract.supply_point_default) else None
            st_id = st.id if st else None
            if st_id not in invoices_by_supply_type:
                invoices_by_supply_type[st_id] = []
            invoices_by_supply_type[st_id].append(inv)

        total_price = 0
        
        # Process known supply types
        for supply_type in supply_types:
            index = 0
            type_invoices = invoices_by_supply_type.get(supply_type.id, [])
            
            if not type_invoices:
                supply_type_data = [supply_type.name, 0, 0, 0]
                for product in products:
                    supply_type_data.append(0)
                supply_type_data.append(0)
                row = add_row(sheet, row, supply_type_data)
                continue
            
            # Basic stats
            num_invoices = len(type_invoices)
            holders = set(inv.contract.holder_id for inv in type_invoices if inv.contract and inv.contract.holder_id)
            num_persons = len(holders) # Approximate, using holder tokens/ids as proxy if Person model is complex
            
            # If we need exact person count from the Person model:
            # num_persons = Person.objects.filter(contracts_holder__id__in=[inv.contract_id for inv in type_invoices if inv.contract_id]).distinct().count()
            # But let's stick to holders set for performance unless strict person merging is needed.
            
            consumption = sum(inv.consumption or 0 for inv in type_invoices)
            total_persons += num_persons
            total_consumption += consumption
            
            supply_type_data = [supply_type.name, num_invoices, num_persons, consumption]
            
            for product in products:
                price_sum = 0
                for inv in type_invoices:
                    price_sum += sum(li.total or 0 for li in inv.line_items.all() if li.product_id == product.id)
                
                supply_type_data.append(price_sum)
                totals_products[index] += price_sum
                index += 1
            
            type_total_final = sum(inv.total_final or 0 for inv in type_invoices)
            supply_type_data.append(type_total_final)
            total_price += type_total_final
            row = add_row(sheet, row, supply_type_data)
        
        # Handle Unknown supply type
        unknown_invoices = invoices_by_supply_type.get(None, [])
        if unknown_invoices:
            index = 0
            num_invoices = len(unknown_invoices)
            holders = set(inv.contract.holder_id for inv in unknown_invoices if inv.contract and inv.contract.holder_id)
            num_persons = len(holders)
            consumption = sum(inv.consumption or 0 for inv in unknown_invoices)
            total_persons += num_persons
            total_consumption += consumption
            
            supply_type_data = [_("Unknown"), num_invoices, num_persons, consumption]
            
            for product in products:
                price_sum = 0
                for inv in unknown_invoices:
                    price_sum += sum(li.total or 0 for li in inv.line_items.all() if li.product_id == product.id)
                
                supply_type_data.append(price_sum)
                totals_products[index] += price_sum
                index += 1
            
            type_total_final = sum(inv.total_final or 0 for inv in unknown_invoices)
            supply_type_data.append(type_total_final)
            total_price += type_total_final
            row = add_row(sheet, row, supply_type_data)
        else:
            supply_type_data = [_("Unknown"), 0, 0, 0]
            for product in products:
                supply_type_data.append(0)
            supply_type_data.append(0)
            row = add_row(sheet, row, supply_type_data)
        
        
        totals = [_("Totals"), invoices.count(), total_persons, total_consumption]
        totals.extend(totals_products)
        totals.append(total_price)
        row = add_row(sheet, row, totals, fill=black_fill, font=white_bold_font)
        
        adjust_column_widths(sheet)
        
        filename = f"billing_by_supply_type_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id, start_date=start_date, end_date=end_date)
        print("report saved")
        
        os.remove(filename)
        return response, document_id, None
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def generate_billing_summary_by_rates(request, black_fill=None, white_bold_font=None, task=None):
    try:
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        billing_ids = get_billing_ids(request.data)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        has_serie_range = has_serie_final_range(request.data)
        if not billing_ids and not date_range and not has_serie_range:
            return Response({"error": "billing id, date range or serie_final range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None

        billing = None
        billings = []
        start_date = None
        end_date = None
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        
        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            invoices = filter_pending_invoices(invoices, request)
            billing = get_object_or_404(Billing, id=billing_ids[0])
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
            invoices = Invoice.objects.filter(issue_date__range=(start_date.date(), end_date.date()), type_final=invoice_type).distinct()
            invoices = filter_pending_invoices(invoices, request)
        elif has_serie_range:
            # Seleccio nomes pel rang de numero de factura: el rang ja identifica les
            # factures, sense lot ni periode. filter_pending_invoices hi aplica el rang
            # (apply_serie_final_range) i el periode surt de les factures resultants,
            # que es el que fan servir els titols i el nom del fitxer.
            invoices = filter_pending_invoices(serie_final_range_invoices(), request)
            start_date, end_date = serie_final_range_period(invoices)
            if start_date is None:
                return Response({"error": "the serie_final range has no invoices."}, status=status.HTTP_400_BAD_REQUEST), None, None
        else:
            raise Exception("Error obtaining invoices for report billing summary")

        if exploitation:
            invoices = invoices.filter(exploitation=exploitation)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        # Filter products based on the invoices we have, not by billing (which may be None)
        products = Product.objects.filter(line_items__invoice__in=invoices).distinct()
        
        wb = openpyxl.Workbook()
        # Remove the default sheet created automatically (optional)
        default_sheet = wb.active
        wb.remove(default_sheet)

        # Ensure at least one sheet exists (Excel requires at least one sheet)
        if not products.exists():
            # Create a default sheet if no products found
            sheet = wb.create_sheet(title=_("Sense dades"))
            row = add_row(sheet, 0, [_("No s'han trobat productes per a aquest període")], fill=black_fill, font=white_bold_font)
        else:
            for product in products:
                row = 0
                # Create a sheet named after the product (keep it <= 31 characters and avoid special chars)
                sheet_title = str(product.name)[:31]  # Excel has a 31-char limit for sheet names
                sheet = wb.create_sheet(title=sheet_title)

                # Example headers
                row = add_row(sheet, row, [_("Tarifa"), _("Contractes"), _("Abonats")], fill=black_fill, font=white_bold_font)

                # Get relevant line items for this product
                line_item_types = LineItemType.objects.filter(line_items__product=product).distinct()
                
                for line_item_type in line_item_types:
                    print(line_item_type)
                    filtered_invoices = invoices.filter(line_items__line_item_type=line_item_type)
                    print(filtered_invoices.count())
                    
                    contracts = [invoice.contract for invoice in filtered_invoices]
                    num_persons = Person.objects.filter(
                        contracts_holder__in=contracts
                    ).distinct().count()
                    
                    info_row = [
                        line_item_type.name,
                        filtered_invoices.count(),
                        num_persons
                    ]
                    row = add_row(sheet, row, info_row)

                adjust_column_widths(sheet)

        filename = f"billing_by_rates_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(filename)

        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id, start_date=start_date, end_date=end_date)
        print("report saved")
        
        os.remove(filename)
        return response, document_id, None
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def generate_billing_taxes_summary(request, black_fill=None, white_bold_font=None, task=None):
    try:
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        billing_ids = get_billing_ids(request.data)
        title_name = request.data.get('name', '')
        ids = request.data.get('taxes_ids', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        
        has_serie_range = has_serie_final_range(request.data)
        if not billing_ids and not date_range and not has_serie_range:
            return Response({"error": "billing id, date range or serie_final range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        
        if ids:
            product_ids = [int(i) for i in ids.split(',')]
        products = Product.objects.filter(id__in=product_ids).distinct() if ids else []
        print("taxes")
        billing = None
        billings = []
        start_date = None
        end_date = None
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        
        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            invoices = filter_pending_invoices(invoices, request)
            billing = get_object_or_404(Billing, id=billing_ids[0])
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
            invoices = Invoice.objects.filter(issue_date__range=(start_date.date(), end_date.date()), type_final=invoice_type).distinct()
            invoices = filter_pending_invoices(invoices, request)
        elif has_serie_range:
            # Seleccio nomes pel rang de numero de factura: el rang ja identifica les
            # factures, sense lot ni periode. filter_pending_invoices hi aplica el rang
            # (apply_serie_final_range) i el periode surt de les factures resultants,
            # que es el que fan servir els titols i el nom del fitxer.
            invoices = filter_pending_invoices(serie_final_range_invoices(), request)
            start_date, end_date = serie_final_range_period(invoices)
            if start_date is None:
                return Response({"error": "the serie_final range has no invoices."}, status=status.HTTP_400_BAD_REQUEST), None, None
        else:
            raise Exception("Error obtaining invoices for report billing summary")

        if exploitation:
            invoices = invoices.filter(exploitation=exploitation)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        # Els abonaments (estat payoff) s'han de comptabilitzar en negatiu (base i IVA).
        # Criteri compartit amb get_report_billing_summary via _payoff_signed_sum.
        payoff_status_token = ConfigProject.objects.get(token="invoice_status_payoff_token").value

        def _signed_tax_sum(tax_pct, field_name):
            return _payoff_signed_sum(field_name, payoff_status_token, tax_pct=tax_pct)

        # Optimize: Use database aggregation instead of Python loops
        # Get all line items from invoices in one query
        invoice_ids = invoices.values_list('id', flat=True)
        
        # Aggregate line items by product_name, price_rate_name, and line_item_name
        # Use Case/When to sum tax_price by tax_percent

        
        line_items_aggregated = InvoiceLineItem.objects.filter(
            invoice_id__in=invoice_ids,
            is_active=True
        ).annotate(
            # Use line_item_type name if exists, otherwise use line_item name
            final_line_item_name=Case(
                When(line_item_type__isnull=False, then=F('line_item_type__name')),
                default=F('name'),
                output_field=CharField()
            ),
            # Determine if custom (SI if no line_item_type, NO if has line_item_type)
            is_custom_value=Case(
                When(line_item_type__isnull=True, then=Value('SI')),
                default=Value('NO'),
                output_field=CharField()
            )
        ).values(
            'product_name',
            'price_rate_name',
            'final_line_item_name',
            'is_custom_value'
        ).annotate(
            iva0=_signed_tax_sum(0, 'price'),
            iva10=_signed_tax_sum(10, 'price'),
            iva21=_signed_tax_sum(21, 'price')
        ).order_by('is_custom_value', 'product_name', 'price_rate_name', 'final_line_item_name')

        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("RESUM IVA")

        row = 0
        titles = [_("PRODUCTE"), _("TARIFA"), _("CONCEPTE"), _("ÉS PERSONALITZADA"), _("IVA0"), _("IVA10"), _("IVA21")]

        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)
        
        # Add each aggregated line item row to the sheet
        total_iva0 = 0
        total_iva10 = 0
        total_iva21 = 0
        for item in line_items_aggregated:
            iva0 = float(item['iva0'] or 0)
            iva10 = float(item['iva10'] or 0)
            iva21 = float(item['iva21'] or 0)
            total_iva0 += iva0
            total_iva10 += iva10
            total_iva21 += iva21
            
            row_data = [
                item['product_name'] or "",
                item['price_rate_name'] or "",
                item['final_line_item_name'] or "",
                item['is_custom_value'] or "",
                iva0,
                iva10,
                iva21
            ]
            row = add_row(sheet, row, row_data)
        
        totals = [_("TOTAL"), "", "", "", total_iva0, total_iva10, total_iva21]
        
        row = add_row(sheet, row, totals, fill=black_fill, font=white_bold_font)
        
        adjust_column_widths(sheet)
        
        # Create second sheet with invoice details
        invoices_sheet = wb.create_sheet(title=_("FACTURES"))
        invoices_row = 0
        
        # Add headers
        invoices_titles = [
            _("CODI FACTURA"), _("CONTRACTE"), _("TIPUS FACTURA"), _("SUBTOTAL"),
            _("BASE IMPOSABLE 0"), _("IVA 0"), _("TOTAL IVA 0"),
            _("BASE IMPOSABLE 10"), _("IVA 10"), _("TOTAL IVA 10"),
            _("BASE IMPOSABLE 21"), _("IVA 21"), _("TOTAL IVA 21"), _("TOTAL")
        ]
        invoices_row = add_row(invoices_sheet, invoices_row, invoices_titles, fill=black_fill, font=white_bold_font)
        
        # Calculate IVA 10 and IVA 21 for each invoice using aggregation
        invoice_ids = invoices.values_list('id', flat=True)
        
        invoice_taxes = InvoiceLineItem.objects.filter(
            invoice_id__in=invoice_ids,
            is_active=True
        ).values('invoice_id').annotate(
            iva0_base=_signed_tax_sum(0, 'price'),
            iva0_tax=_signed_tax_sum(0, 'tax_price'),
            iva10_base=_signed_tax_sum(10, 'price'),
            iva10_tax=_signed_tax_sum(10, 'tax_price'),
            iva21_base=_signed_tax_sum(21, 'price'),
            iva21_tax=_signed_tax_sum(21, 'tax_price')
        )
        
        # Create a dictionary mapping invoice_id to tax sums
        taxes_dict = {
            item['invoice_id']: {
                'iva0_base': float(item['iva0_base'] or 0),
                'iva0_tax': float(item['iva0_tax'] or 0),
                'iva10_base': float(item['iva10_base'] or 0),
                'iva10_tax': float(item['iva10_tax'] or 0),
                'iva21_base': float(item['iva21_base'] or 0),
                'iva21_tax': float(item['iva21_tax'] or 0)
            }
            for item in invoice_taxes
        }
        
        # Add invoice data rows
        # Optimize: Use select_related to fetch contract and origin in one query
        # Use only() to fetch only the fields we need
        invoices_with_relations = invoices.select_related(
            'contract',
            'origin'
        ).only(
            'id',
            'serie_final',
            'subtotal_final',
            'total_final',
            'contract__token',
            'origin__name'
        ).order_by('serie_final')
        
        for invoice in invoices_with_relations:
            # Get contract token - contract is already fetched via select_related
            contract_token = invoice.contract.token if invoice.contract else ""
            origin_name = invoice.origin.name if invoice.origin else ""
            
            # Get tax data from the aggregated dictionary
            invoice_taxes_data = taxes_dict.get(invoice.id, {
                'iva0_base': 0, 'iva0_tax': 0,
                'iva10_base': 0, 'iva10_tax': 0,
                'iva21_base': 0, 'iva21_tax': 0
            })
            invoice_row = [
                invoice.serie_final or "",
                contract_token,
                origin_name,
                invoice.subtotal_final or 0,
                invoice_taxes_data['iva0_base'],
                abs(invoice_taxes_data['iva0_tax']) if invoice_taxes_data['iva0_base'] > 0 else -abs(invoice_taxes_data['iva0_tax']),
                invoice_taxes_data['iva0_base'] + (abs(invoice_taxes_data['iva0_tax']) if invoice_taxes_data['iva0_base'] > 0 else -abs(invoice_taxes_data['iva0_tax'])),
                invoice_taxes_data['iva10_base'],
                abs(invoice_taxes_data['iva10_tax']) if invoice_taxes_data['iva10_base'] > 0 else -abs(invoice_taxes_data['iva10_tax']),
                invoice_taxes_data['iva10_base'] + (abs(invoice_taxes_data['iva10_tax']) if invoice_taxes_data['iva10_base'] > 0 else -abs(invoice_taxes_data['iva10_tax'])),
                invoice_taxes_data['iva21_base'],
                abs(invoice_taxes_data['iva21_tax']) if invoice_taxes_data['iva21_base'] > 0 else -abs(invoice_taxes_data['iva21_tax']),
                invoice_taxes_data['iva21_base'] + (abs(invoice_taxes_data['iva21_tax']) if invoice_taxes_data['iva21_base'] > 0 else -abs(invoice_taxes_data['iva21_tax'])),
                invoice.total_final or 0
            ]
            invoices_row = add_row(invoices_sheet, invoices_row, invoice_row)
        
        adjust_column_widths(invoices_sheet)
        
        filename = f"billing_taxes_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        
        document_id = save_report(content=wb, filename=filename, name=title_name, type_id=type_id, start_date=start_date, end_date=end_date)
        
        os.remove(filename)
        return response, document_id, None
    except Exception as e:
        print("ERROR: ", e)
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

#NAVISION MURCIA
def generate_billing_taxes_detailed_summary(request, black_fill=None, white_bold_font=None, task=None):
    try:
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        billing_ids = get_billing_ids(request.data)
        title_name = request.data.get('name', '')
        ids = request.data.get('taxes_ids', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        
        has_serie_range = has_serie_final_range(request.data)
        if not billing_ids and not date_range and not has_serie_range:
            return Response({"error": "billing id, date range or serie_final range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        
        if ids:
            product_ids = [int(i) for i in ids.split(',')]
        products = Product.objects.filter(id__in=product_ids).distinct() if ids else []
        
        billing = None
        billings = []
        start_date = None
        end_date = None
        
        main_company_token = ConfigProject.objects.get(token='main_company_token').value
        default_company = Company.objects.get(vat=main_company_token)
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)

        invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value

        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            invoices = filter_pending_invoices(invoices, request)
            billing = get_object_or_404(Billing, id=billing_ids[0])
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            #billings = Billing.objects.filter(created_at__range=(start_date.date(), end_date.date()))
            invoices = Invoice.objects.filter(issue_date__range=(start_date.date(), end_date.date()), type_final=invoice_type)
            invoices = filter_pending_invoices(invoices, request)
        elif has_serie_range:
            # Seleccio nomes pel rang de numero de factura: el rang ja identifica les
            # factures, sense lot ni periode. filter_pending_invoices hi aplica el rang
            # (apply_serie_final_range) i el periode surt de les factures resultants,
            # que es el que fan servir els titols i el nom del fitxer.
            invoices = filter_pending_invoices(serie_final_range_invoices(), request)
            start_date, end_date = serie_final_range_period(invoices)
            if start_date is None:
                return Response({"error": "the serie_final range has no invoices."}, status=status.HTTP_400_BAD_REQUEST), None, None
        else:
            raise Exception("Error obtaining invoices for report billing summary")

        if exploitation:
            invoices = invoices.filter(exploitation=exploitation)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        invoices = invoices.select_related('exploitation', 'company', 'exploitation__company').prefetch_related(
            'line_items',
            'line_items__company',
            'line_items__product',
            'line_items__line_item_type'
        )
        invoices = list(invoices)

        # Cache returned invoices by their token (for returned_invoice check)
        returned_tokens = [inv.token for inv in invoices if inv.token]
        returned_invoices_by_token = {}
        if returned_tokens:
            for ri in Invoice.objects.filter(return_token__in=returned_tokens).only('serie_final', 'return_token'):
                returned_invoices_by_token[ri.return_token] = ri

        # Cache LineItemTypes per product to avoid querying in loop
        product_line_item_types = {}
        for product in products:
            product_line_item_types[product.id] = list(LineItemType.objects.filter(
                is_active=True, billing_range__price_rate__product=product
            ).distinct())

        direct_debit_token = ConfigProject.objects.get(token="direct_debit_token").value
        bank_transfer_token = ConfigProject.objects.get(token="bank_transfer_token").value
        
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("Facturació")

        row = 0
        titles = [
                    _("Explotación"), _("Emisora"), _("Tipo Factura"), _("Nº Factura"),
                    _("Nº Factura corregida"), _("Fecha factura"), _("CIF"),
                    _("Razón Social"), _("Dirección"),
                    _("Población"), _("Provincia"), _("Código Postal"),
                    _("País"), _("Nº Proyecto"), _("Forma de pago"),
                    _("Base factura"), _("Importe total factura"),
                    ]
        # Initialize totals_sum with 2 elements for "Base factura" and "Importe total factura"
        totals_sum = [0, 0]
        
        for product in products:
            line_item_types = product_line_item_types.get(product.id, [])
            for line_item_type in line_item_types:
                titles.append(f"{product.name} {line_item_type.name}")
                titles.append(_("IVA %(product)s %(line_item)s") % {"product": product.name, "line_item": line_item_type.name})
                titles.append(_("CIF %(product)s %(line_item)s") % {"product": product.name, "line_item": line_item_type.name})
                totals_sum.append(0)
                totals_sum.append(0)
                totals_sum.append(0)
                
        line_items_without_type = InvoiceLineItem.objects.filter(invoice__in=invoices, line_item_type__isnull=True).distinct()
        
        custom_line_titles = []
        for line_item in line_items_without_type:
            line_label = line_item.name or line_item.product_name or _("Línea personalizada")
            if f"{line_label}*" not in titles:
                print("Adding custom line title: ", line_label)
                titles.append(f"{line_label}*")
                titles.append(_("IVA %(line)s") % {"line": line_label})
                titles.append(_("CIF %(line)s") % {"line": line_label})
                custom_line_titles.append(f"{line_label}")
                totals_sum.append(0)
                totals_sum.append(0)
                totals_sum.append(0)

        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)
        
        total_invoices_progress = len(invoices)
        for idx_invoice, i in enumerate(invoices, start=1):
            if task and idx_invoice % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx_invoice,
                        'total': total_invoices_progress,
                        'percent': round((idx_invoice / total_invoices_progress) * 100, 2) if total_invoices_progress else 0.0
                    }
                )
            index = 0
            name = i.customer_final
            returned_invoice = None
            returned_invoice_serie = ""
            
            if i.is_suppressed or i.total_final < 0:
                type_name = _("ABONO")
                if i.is_suppressed:
                    returned_invoice = returned_invoices_by_token.get(i.token)
                    returned_invoice_serie = returned_invoice.serie_final.upper() if returned_invoice else ""
            else:
                type_name = _("FACTURA")
                
            
            i_data = [
                i.exploitation.id if i.exploitation else "",
                i.company.alias if i.company else default_company.alias, type_name.upper() if type_name else "", i.serie_final.upper() if i.serie_final else "", 
                returned_invoice_serie, i.issue_date, i.customer_token_final.upper() if i.customer_token_final else "",
                i.customer_final.upper() if i.customer_final else "", i.address_final.upper() if i.address_final else "",
                i.city_final.upper() if i.city_final else "", i.province_final.upper() if i.province_final else "", i.postal_code_final.upper() if i.postal_code_final else "",
                i.country_final.upper() if i.country_final else "", 
                "", 
                "REMESA" if i.payment_type_token_final == direct_debit_token else "BANCO" if i.payment_type_token_final == bank_transfer_token else "EFECTIVO",
                i.subtotal_final, i.total_final
                ]
            totals_sum[index] += i.subtotal_final
            index+=1
            totals_sum[index] += i.total_final
            index+=1

            all_lines = list(i.line_items.all())

            for product in products:
                line_items = [line for line in all_lines if line.product_id == product.id]
                line_item_types = product_line_item_types.get(product.id, [])
                for line_item_type in line_item_types:
                    current_line_item = [line for line in line_items if line.line_item_type_id == line_item_type.id]
                    if not current_line_item:
                        price_sum = 0
                        tax_price_sum = 0
                    else:
                        price_sum = current_line_item[0].price or 0
                        tax_price_sum = current_line_item[0].tax_price or 0
                    i_data.append(price_sum)
                    i_data.append(tax_price_sum)
                    i_data.append(line_items[0].company.vat if line_items and line_items[0].company else "")
                    
                    totals_sum[index] += price_sum
                    totals_sum[index + 1] += tax_price_sum
                    totals_sum[index + 2] = ""
                    index += 3
            
            for custom_line_title in custom_line_titles:
                name_to_match = custom_line_title.split("*")[0]
                custom_lines = [line for line in all_lines if line.line_item_type_id is None and line.name == name_to_match]
                if custom_lines:
                    price_sum = sum(line.price or 0 for line in custom_lines)
                    tax_price_sum = sum(line.tax_price or 0 for line in custom_lines)
                    company_vat = custom_lines[0].company.vat if custom_lines[0].company else ""
                    i_data.append(price_sum)
                    i_data.append(tax_price_sum)
                    i_data.append(company_vat)
                    
                    totals_sum[index] += price_sum
                    totals_sum[index + 1] += tax_price_sum
                    totals_sum[index + 2] = ""
                else:
                    i_data.append(0)
                    i_data.append(0)
                    i_data.append("")
                index += 3
            
            row = add_row(sheet, row, i_data)
        
        totals = [_("Totals"), "", len(invoices), "","","","","","","","","","","",""]
        totals.extend(totals_sum)
        
        row = add_row(sheet, row, totals, fill=black_fill, font=white_bold_font)
        
        adjust_column_widths(sheet)

        # ── Tab 2: Pagaments rebuts (per data de cobrament) ─────────────────────
        # Independent queryset: all paid payments received in the date range
        # (or linked to the billing), regardless of invoice issue date.
        payments_received_qs = Payment.objects.filter(
            is_active=True,
            status__token='0',
        ).filter(
            Q(invoice__isnull=True) |
            Q(invoice__type_final=invoice_type, invoice__is_excluded=False)
        ).select_related(
            'invoice',
            'invoice__company',
            'invoice__exploitation',
            'invoice__contract',
            'status',
            'contract',
        )

        if date_range:
            payments_received_qs = payments_received_qs.filter(
                payment_date__range=(start_date.date(), end_date.date())
            )
        elif billing:
            payments_received_qs = payments_received_qs.filter(invoice__billing=billing)

        if exploitation:
            payments_received_qs = payments_received_qs.filter(
                Q(invoice__exploitation=exploitation) | Q(invoice__isnull=True)
            )

        payments_received = list(payments_received_qs.order_by('payment_date', 'token'))

        sheet_payments = wb.create_sheet(title=_("Pagaments rebuts"))
        row_payments = 0
        payment_headers = [
            _("Data cobrament"),
            _("Token cobrament"),
            _("Import cobrat (€)"),
            _("Forma de pagament"),
            _("Estat"),
            _("Nº Factura"),
            _("Data factura"),
            _("CIF"),
            _("Raó social"),
            _("Emisora"),
            _("Explotació"),
            _("Contracte"),
        ]
        row_payments = add_row(sheet_payments, row_payments, payment_headers, fill=black_fill, font=white_bold_font)

        total_received = Decimal('0')
        for pay in payments_received:
            inv = pay.invoice
            pay_type_token = pay.payment_type_token or (inv.payment_type_token_final if inv else None)
            pay_method = (
                _("REMESA") if pay_type_token == direct_debit_token
                else _("BANCO") if pay_type_token == bank_transfer_token
                else _("EFECTIVO")
            )
            amount = pay.amount or Decimal('0')
            total_received += amount
            row_payments = add_row(sheet_payments, row_payments, [
                pay.payment_date or pay.paid_at or "",
                pay.token or "",
                round(float(amount), 2),
                pay_method,
                pay.status.name if pay.status else "",
                inv.serie_final.upper() if inv and inv.serie_final else "",
                inv.issue_date if inv else "",
                (pay.customer_token_final or (inv.customer_token_final if inv else "") or "").upper(),
                (pay.customer_final or (inv.customer_final if inv else "") or "").upper(),
                inv.company.alias if inv and inv.company else (default_company.alias if inv else ""),
                inv.exploitation.id if inv and inv.exploitation else "",
                pay.contract.token if pay.contract else (inv.contract.token if inv and inv.contract else ""),
            ])
            sheet_payments.cell(row=row_payments, column=3).number_format = '#,##0.00'

        row_payments = jump_row(row_payments)
        row_payments = add_row(
            sheet_payments,
            row_payments,
            [_("TOTAL"), len(payments_received), round(float(total_received), 2), "", "", "", "", "", "", "", "", ""],
            fill=black_fill,
            font=white_bold_font,
        )
        sheet_payments.cell(row=row_payments, column=3).number_format = '#,##0.00'
        adjust_column_widths(sheet_payments)
        # ── end Pagaments rebuts ─────────────────────────────────────────────────

        # ── Tab 3: Cobros (disabled) ────────────────────────────────────────────
        # sheet_cobros = wb.create_sheet(title=_("Cobros"))
        # row_cobros = 0
        # totals_sum_cobros = [0] * len(totals_sum)
        # row_cobros = add_row(sheet_cobros, row_cobros, titles, fill=black_fill, font=white_bold_font)
        # cobros_payments_qs = Payment.objects.filter(
        #     invoice__in=invoices, is_active=True, status__token='0',
        # ).select_related('invoice', 'invoice__exploitation', 'invoice__company').prefetch_related(
        #     'invoice__line_items', 'invoice__line_items__company',
        #     'invoice__line_items__product', 'invoice__line_items__line_item_type',
        # )
        # cobros_payments_list = list(cobros_payments_qs)
        # ... prorated payment rows per invoice (see git history)

        # ── Tab 3: Resum per Empresa (Facturat / Cobrat) ───────────────────────
        # Facturat from tab-1 invoices; Cobrat aggregated from tab-2 payments_received.
        ws_company = wb.create_sheet(title=_("Resum per Empresa"))

        company_facturat = {}
        company_names = {}
        for inv in invoices:
            comp = inv.company or (inv.exploitation.company if inv.exploitation else None)
            c_id = comp.id if comp else 0
            c_name = (comp.name or comp.alias or f"Empresa ID {comp.id}") if comp else _("Sense Empresa")
            company_facturat[c_id] = company_facturat.get(c_id, Decimal('0')) + (inv.total_final or Decimal('0'))
            company_names[c_id] = c_name

        company_cobrat = {}
        for pay in payments_received:
            inv = pay.invoice
            if inv is None:
                c_id = 2
                if c_id not in company_names:
                    fallback_comp = Company.objects.filter(id=c_id).first()
                    company_names[c_id] = (
                        fallback_comp.name or fallback_comp.alias or f"Empresa ID {c_id}"
                    ) if fallback_comp else f"Empresa ID {c_id}"
            else:
                comp = inv.company or (inv.exploitation.company if inv.exploitation else None)
                c_id = comp.id if comp else 0
                if c_id not in company_names:
                    company_names[c_id] = (
                        comp.name or comp.alias or f"Empresa ID {comp.id}"
                    ) if comp else _("Sense Empresa")
            company_cobrat[c_id] = company_cobrat.get(c_id, Decimal('0')) + (pay.amount or Decimal('0'))

        # Write tab
        headers_company = [_("Empresa"), _("Facturat (€)"), _("Cobrat (€)")]
        current_row = add_row(ws_company, 0, headers_company, fill=black_fill, font=white_bold_font)

        total_facturat = Decimal('0')
        total_cobrat = Decimal('0')

        for c_id, c_name in sorted(company_names.items(), key=lambda x: x[1]):
            facturat = company_facturat.get(c_id, Decimal('0'))
            cobrat = company_cobrat.get(c_id, Decimal('0'))
            current_row = add_row(ws_company, current_row, [c_name, round(float(facturat), 2), round(float(cobrat), 2)])
            ws_company.cell(row=current_row, column=2).number_format = '#,##0.00'
            ws_company.cell(row=current_row, column=3).number_format = '#,##0.00'
            total_facturat += facturat
            total_cobrat += cobrat

        current_row += 1  # blank separator
        footer = [_("TOTAL"), round(float(total_facturat), 2), round(float(total_cobrat), 2)]
        add_row(ws_company, current_row, footer, fill=black_fill, font=white_bold_font)
        ws_company.cell(row=current_row + 1, column=2).number_format = '#,##0.00'
        ws_company.cell(row=current_row + 1, column=3).number_format = '#,##0.00'
        adjust_column_widths(ws_company)
        # ── end Resum per Empresa ───────────────────────────────────────────────

        filename = f"billing_taxes_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        
        document_id = save_report(content=wb, filename=filename, name=title_name, type_id=type_id, start_date=start_date, end_date=end_date)
        print("report saved")
        
        os.remove(filename)
        return response, document_id, None
    except Exception as e:
        print("ERROR: ", e)
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None


def generate_billing_detailed_consumption_summary(request, black_fill=None, white_bold_font=None, task=None):
    try:
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        billing_ids = get_billing_ids(request.data)
        title_name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        
        start_date = None
        end_date = None
        
        has_serie_range = has_serie_final_range(request.data)
        if not billing_ids and not date_range and not has_serie_range:
            return Response({"error": "billing id, date range or serie_final range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
            
        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            invoices = filter_pending_invoices(invoices, request)
            billing = get_object_or_404(Billing, id=billing_ids[0])
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            # billings = Billing.objects.filter(created_at__range=(start_date.date(), end_date.date()))
            origin_reading_token = ConfigProject.objects.get(token="origin_reading_token").value
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
            invoices = Invoice.objects.filter(
                issue_date__range=(start_date.date(), end_date.date()),
                origin__token=origin_reading_token,
                type_final=invoice_type
            ).distinct()
            invoices = filter_pending_invoices(invoices, request)
        elif has_serie_range:
            # Seleccio nomes pel rang de numero de factura: el rang ja identifica les
            # factures, sense lot ni periode. filter_pending_invoices hi aplica el rang
            # (apply_serie_final_range) i el periode surt de les factures resultants,
            # que es el que fan servir els titols i el nom del fitxer.
            invoices = filter_pending_invoices(serie_final_range_invoices(), request)
            start_date, end_date = serie_final_range_period(invoices)
            if start_date is None:
                return Response({"error": "the serie_final range has no invoices."}, status=status.HTTP_400_BAD_REQUEST), None, None
        else:
            raise Exception("Error obtaining invoices for report billing summary")
        if exploitation_id:
            invoices = invoices.filter(exploitation__id=exploitation_id)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        # Optimize contract and related data loading to avoid per-invoice queries
        invoices = invoices.select_related(
            'exploitation',
            'contract',
            'contract__supply_point_default',
            'contract__supply_point_default__meter',
            'contract__supply_point_default__meter__caliber',
            'contract__supply_point_default__placement',
            'contract__supply_point_default__cluster_nozzle__cluster',
            'contract__use_type',
            'contract_termination__contract',
            'contract_request',
        ).prefetch_related(
            'readings',
        )
        print("invoices: ", invoices.count())
        # Get line items and products that match conditions in a single, efficient query
        line_items_qs = InvoiceLineItem.objects.filter(
            invoice__in=invoices,
            line_item_type__isnull=False,
        ).filter(
            (Q(line_item_type__price_interval__isnull=False) |
             Q(line_item_type__price_variable__isnull=False)) &
            (Q(line_item_type__price_variable__units='m3') |
             Q(line_item_type__price_interval__units='m3'))
        )
        product_ids = list(
            line_items_qs.values_list('product_id', flat=True).distinct()
        )
        products = Product.objects.filter(id__in=product_ids).distinct()
        
        print("products: ", products.count())
        
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("Facturació")

        row = 0
        titles = [
            _("Explotació"), _("Factura"), _("Ident."), _("Abonat"), _("Adreça"), _("Nº comptador"),
            _("Calibre"), _("Bateria"), _("Ubicació"), _("Tipus de subministrament"),
            _("Dies"), _("Valor lectura"), _("Data lectura"), _("Tipus lectura"), _("Tipus telelectura")
        ]
        
        totals_sum = []
        
        # Precompute max number of line items per (product, invoice) using the same filtered queryset
        product_stretches = {}
        line_items_counts = (
            line_items_qs
            .values('product_id', 'invoice_id')
            .annotate(item_count=Count('id'))
        )
        for li in line_items_counts:
            product_id = li['product_id']
            count = li['item_count'] or 0
            current_max = product_stretches.get(product_id, 0)
            if count > current_max:
                product_stretches[product_id] = count
        
        for product in products:
            max_line_items = product_stretches.get(product.id, 0)
            product_stretches[product.id] = max_line_items
            for i in range(max_line_items):
                titles.append(f"m3 {product.name if product else ''} {i+1} - {product.exploitation.name if product.exploitation else ''}")
                totals_sum.append(0)
        
        titles.append(_("Total m3 facturats"))
        totals_sum.append(0)
        
        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)

        total_invoices_progress = invoices.count()
        print("invoices: ", total_invoices_progress)
        counter = 0
        for i in invoices:
            counter += 1
            if counter % 100 == 0:
                print("counter: ", counter)
            if task and counter % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': counter,
                        'total': total_invoices_progress,
                        'percent': round((counter / total_invoices_progress) * 100, 2) if total_invoices_progress else 0.0
                    }
                )
            colored = []
            index = 0
            name = i.customer_final
            # Use already select_related / prefetched relations to avoid extra queries
            contract = i.contract
            if not contract and i.contract_termination:
                contract = i.contract_termination.contract
            if not contract and i.contract_request:
                # Prefer the contract linked via Contract.contract_request (reverse FK)
                contract = getattr(i.contract_request, 'contract', None) or Contract.objects.filter(contract_request=i.contract_request).first()
            reading = i.readings.first() if i.readings.exists() else None
            
            i_data = [
                i.exploitation.name,
                i.serie_final,
                i.customer_token_final,
                name,
                i.address_final,
                contract.supply_point_default.meter.code if contract and contract.supply_point_default and contract.supply_point_default.meter else "desconegut",
                contract.supply_point_default.meter.caliber.name if contract and contract.supply_point_default and contract.supply_point_default.meter and contract.supply_point_default.meter.caliber else "desconegut",
                contract.supply_point_default.cluster_nozzle.cluster.token if contract and contract.supply_point_default and contract.supply_point_default.cluster_nozzle and contract.supply_point_default.cluster_nozzle.cluster else "-",
                contract.supply_point_default.placement.name if contract and contract.supply_point_default and contract.supply_point_default.placement else "desconegut",
                contract.use_type.name if contract and contract.use_type else "desconegut",
                i.consumption_days,
                reading.reading_value if reading else "",
                reading.reading_date if reading else "",
                reading.origin if reading else "",
                contract.supply_point_default.meter.comm_technology if contract and contract.supply_point_default and contract.supply_point_default.meter else ""]
            for even_product, product in enumerate(products):
                # Use the same filtered queryset used to compute product_stretches,
                # restricted to the current invoice and product, to keep counts aligned.
                line_items = line_items_qs.filter(invoice=i, product=product)

                entries = product_stretches[product.id]
                for item in line_items:
                    i_data.append(item.units)
                    totals_sum[index] += item.units
                    if even_product % 2 == 0:
                        colored.append(len(i_data) - 1)
                    index += 1
                    entries -= 1
                if entries > 0:
                    for j in range(entries):
                        i_data.append("")
                        if even_product % 2 == 0:
                            colored.append(len(i_data) - 1)
                        index += 1
            i_data.append(i.consumption)
            totals_sum[index] += i.consumption
            
            row = add_row(sheet, row, i_data, colored=colored)
        
        totals = [_("Totals"), invoices.count(), "","", "", "", "","", "", "", "", "","", "", ""]
        totals.extend(totals_sum)
        
        row = add_row(sheet, row, totals, fill=black_fill, font=white_bold_font)
        
        adjust_column_widths(sheet)
        
        filename = f"billing_detailed_consumption_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        document_id = save_report(content=wb, filename=filename, name=title_name, type_id=type_id, start_date=start_date, end_date=end_date)
        
        os.remove(filename)
        return response, document_id, None
    except Exception as e:
        print("ERROR: ", e)
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def generate_report_billing_total_by_person(request, black_fill=None, white_bold_font=None, task=None):
    
    try:
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        billing_ids = get_billing_ids(request.data)
        title_name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        
        start_date = None
        end_date = None
        
        has_serie_range = has_serie_final_range(request.data)
        if not billing_ids and not date_range and not has_serie_range:
            return Response({"error": "billing id, date range or serie_final range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
            
        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            invoices = filter_pending_invoices(invoices, request)
            billing = get_object_or_404(Billing, id=billing_ids[0])
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            # billings = Billing.objects.filter(created_at__range=(start_date.date(), end_date.date()))
            print("start_date: ", start_date)
            print("end_date: ", end_date)
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
            invoices = Invoice.objects.filter(issue_date__range=(start_date.date(), end_date.date()), type_final=invoice_type).distinct()
            invoices = filter_pending_invoices(invoices, request)
        elif has_serie_range:
            # Seleccio nomes pel rang de numero de factura: el rang ja identifica les
            # factures, sense lot ni periode. filter_pending_invoices hi aplica el rang
            # (apply_serie_final_range) i el periode surt de les factures resultants,
            # que es el que fan servir els titols i el nom del fitxer.
            invoices = filter_pending_invoices(serie_final_range_invoices(), request)
            start_date, end_date = serie_final_range_period(invoices)
            if start_date is None:
                return Response({"error": "the serie_final range has no invoices."}, status=status.HTTP_400_BAD_REQUEST), None, None
        else:
            raise Exception("Error obtaining invoices for report billing summary")
        if exploitation_id:
            invoices = invoices.filter(exploitation__id=exploitation_id)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        print("invoices: ", invoices.count())
        invoice_paid_status_token = ConfigProject.objects.get(token="invoice_status_paid_token").value
        invioce_cancelled_status_token = ConfigProject.objects.get(token="invoice_status_cancelled_token").value
        invoice_status_payoff_token = ConfigProject.objects.get(token="invoice_status_payoff_token").value

        invoices_no_payer = invoices.filter(payer_token_final__isnull=True).distinct()
        invoices_payer = invoices.filter(payer_token_final__isnull=False).distinct()

        # Conditional sum for pending (exclude paid and cancelled)
        pending_expr = Sum(
            Case(
                When(
                    ~Q(status__token__in=[invoice_paid_status_token, invioce_cancelled_status_token, invoice_status_payoff_token]),
                    then=F("total_final"),
                ),
                default=Value(Decimal("0")),
                output_field=DecimalField(),
            )
        )
        payer_invoice_ids = invoices_payer.values_list("id", flat=True).distinct()
        no_payer_invoice_ids = invoices_no_payer.values_list("id", flat=True).distinct()

        # Aggregate by (payer_token_final, payer_final) so same token with different names = separate rows
        payer_agg = (
            Invoice.objects.filter(id__in=Subquery(payer_invoice_ids))
            .values("payer_token_final", "payer_final")
            .annotate(
                total=Sum("total_final"),
                subtotal=Sum("subtotal_final"),
                pending=pending_expr,
            )
            .filter(payer_token_final__isnull=False)
        )
        customer_agg = (
            Invoice.objects.filter(id__in=Subquery(no_payer_invoice_ids))
            .values("customer_token_final", "customer_final")
            .annotate(
                total=Sum("total_final"),
                subtotal=Sum("subtotal_final"),
                pending=pending_expr,
            )
            .filter(customer_token_final__isnull=False)
        )
        
        def _norm_name(name):
            return (name or "").strip()

        totals_by_token_name = {}
        for row in payer_agg:
            t = row["payer_token_final"]
            name = _norm_name(row.get("payer_final"))
            key = (t, name)
            if key not in totals_by_token_name:
                totals_by_token_name[key] = {"total": Decimal("0"), "subtotal": Decimal("0"), "pending": Decimal("0")}
            totals_by_token_name[key]["total"] += row["total"] or Decimal("0")
            totals_by_token_name[key]["subtotal"] += row["subtotal"] or Decimal("0")
            totals_by_token_name[key]["pending"] += row["pending"] or Decimal("0")
        for row in customer_agg:
            t = row["customer_token_final"]
            name = _norm_name(row.get("customer_final"))
            key = (t, name)
            if key not in totals_by_token_name:
                totals_by_token_name[key] = {"total": Decimal("0"), "subtotal": Decimal("0"), "pending": Decimal("0")}
            totals_by_token_name[key]["total"] += row["total"] or Decimal("0")
            totals_by_token_name[key]["subtotal"] += row["subtotal"] or Decimal("0")
            totals_by_token_name[key]["pending"] += row["pending"] or Decimal("0")

        # Sort by token then name for stable output
        rows_data = sorted(totals_by_token_name.items(), key=lambda x: (x[0][0], x[0][1]))

        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("Informe import total")

        row = 0
        titles = [_("NIF Client"), _("Nom Client"), _("Import facturat"), _("Import base"), _("Import IVA"), _("Total pendent")]

        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)

        for (token, name), data in rows_data:
            total_invoices = data["total"]
            subtotal_invoices = data["subtotal"]
            total_iva_invoices = total_invoices - subtotal_invoices
            total_invoices_pending = data["pending"]
            new_line = [
                token,
                name or "",
                total_invoices,
                subtotal_invoices,
                total_iva_invoices,
                total_invoices_pending,
            ]
            row = add_row(sheet, row, new_line)
        
        totals = [_("Totals"), "", "", "", "", "", "", ""]
        
        row = add_row(sheet, row, totals, fill=black_fill, font=white_bold_font)
        
        adjust_column_widths(sheet)
        
        filename = f"billing_detailed_consumption_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        document_id = save_report(content=wb, filename=filename, name=title_name, type_id=type_id, start_date=start_date, end_date=end_date)
        
        os.remove(filename)
        return response, document_id, None
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def generate_report_billing_347(request, black_fill=None, white_bold_font=None, task=None):
    try:
        year = request.data.get('year', None)
        include_tax_free_lines = request.data.get('include_tax_free_lines', False)

        print("Include tax free lines: ", include_tax_free_lines)
        print("Year: ", year)

        if not year:
            raise ValueError("year is required.")

        if  include_tax_free_lines:
            taxable_filter = (
                Q(line_items__is_active=True)
            )
        else:
            taxable_filter = (
                Q(line_items__tax_percent__isnull=False)
                & ~Q(line_items__tax_percent=0)
                & Q(line_items__is_active=True)
            )

        invoice_status_cancelled_token = ConfigProject.objects.get(token='invoice_status_cancelled_token').value
        status_cancelled = InvoiceStatus.objects.get(token=invoice_status_cancelled_token)

        ov_pdf_from_date = None
        ov_pdf_from_config = ConfigProject.objects.filter(token='ov_pdf_from').first()
        if ov_pdf_from_config and ov_pdf_from_config.value:
            ov_pdf_from_date = parse_date(ov_pdf_from_config.value)

        # Effective company: invoice.company if set, else invoice.exploitation.company
        # Companies that have invoices in the year (one sheet per company)
        companies_qs = (
            Invoice.objects.filter(issue_date__year=year)
            .exclude(type_final='P')
            .exclude(status=status_cancelled)
        )
        if ov_pdf_from_date is not None:
            companies_qs = companies_qs.filter(issue_date__gte=ov_pdf_from_date)
        companies_qs = (
            companies_qs
            .annotate(
                effective_company_id=Coalesce(F('company_id'), F('exploitation__company_id')),
                effective_company_alias=Case(
                    When(company_id__isnull=False, then=F('company__alias')),
                    default=F('exploitation__company__alias'),
                    output_field=CharField(),
                ),
            )
            .filter(effective_company_id__isnull=False)
            .values('effective_company_id', 'effective_company_alias')
            .distinct()
            .order_by('effective_company_alias')
        )
        companies = list(companies_qs)

        title_name = request.data.get('name', f'Informe 347 {year}')
        type_id = request.data.get('type_id')
        start_date = datetime.datetime(int(year), 1, 1)
        end_date = datetime.datetime(int(year), 12, 31)

        wb = openpyxl.Workbook()
        # Excel sheet names: max 31 chars, no \ / ? * [ ]
        def _sheet_title(name):
            if not name:
                return _("Sense nom")
            s = str(name).replace("\\", " ").replace("/", " ").replace("?", " ").replace("*", " ").replace("[", " ").replace("]", " ")[:31]
            return s.strip() or "Sheet"

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))

        first = True
        for comp in companies:
            company_id = comp['effective_company_id']
            company_name = comp.get('effective_company_alias') or f"Company {company_id}"
            # Invoices that belong to this company (direct or via exploitation)
            company_invoice_filter = (
                Q(company_id=company_id)
                | Q(company_id__isnull=True, exploitation__company_id=company_id)
            )
            # Per company: customers with taxable total >= 3000 with this company only
            rows_data = (
                Invoice.objects.filter(
                    issue_date__year=year,
                    customer_token_final__isnull=False,
                    status__isnull=False,
                    is_active=True,
                )
                .exclude(status=status_cancelled)
                .exclude(type_final='P')
            )
            if ov_pdf_from_date is not None:
                rows_data = rows_data.filter(issue_date__gte=ov_pdf_from_date)
            rows_data = rows_data.filter(company_invoice_filter)
            if multi_q:
                rows_data = rows_data.filter(multi_q).distinct()
            rows_data = (
                rows_data
                .values('customer_token_final', 'customer_final')
                .annotate(
                    total=Sum(
                        'line_items__total',
                        filter=taxable_filter,
                    ),
                    num_documents=Count('id'),
                    t1=Sum(
                        'line_items__total',
                        filter=Q(issue_date__month__in=[1, 2, 3]) & taxable_filter,
                    ),
                    t2=Sum(
                        'line_items__total',
                        filter=Q(issue_date__month__in=[4, 5, 6]) & taxable_filter,
                    ),
                    t3=Sum(
                        'line_items__total',
                        filter=Q(issue_date__month__in=[7, 8, 9]) & taxable_filter,
                    ),
                    t4=Sum(
                        'line_items__total',
                        filter=Q(issue_date__month__in=[10, 11, 12]) & taxable_filter,
                    ),
                )
                .filter(total__gte=3000)
                .order_by('customer_token_final', 'customer_final')
            )
            title = _sheet_title(company_name)
            if first:
                sheet = wb.active
                sheet.title = title
                first = False
            else:
                sheet = wb.create_sheet(title=title)
            row = 0
            titles = [_("CLIENT"), _("CIF"), _("DOCS"), _("T1"), _("T2"), _("T3"), _("T4"), _("TOTAL")]
            row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)
            for item in rows_data:
                row = add_row(sheet, row, [
                    item.get('customer_final') or '',
                    item.get('customer_token_final') or '',
                    item.get('num_documents') or 0,
                    item.get('t1') or 0,
                    item.get('t2') or 0,
                    item.get('t3') or 0,
                    item.get('t4') or 0,
                    item.get('total') or 0,
                ])
            adjust_column_widths(sheet)

        filename = f"report_billing_347_{year}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(filename)


        print("filename: ", filename)

        response = None
        with open(filename, "rb") as f:
            response = HttpResponse(
                f.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f"attachment; filename={filename}"

        document_id = save_report(
            content=wb,
            filename=filename,
            name=title_name,
            type_id=type_id,
            start_date=start_date,
            end_date=end_date,
        )

        os.remove(filename)
        return response, document_id, filename
    except Exception as e:
        print("error: ", e)
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def generate_cobraments_report(request, black_fill=None, white_bold_font=None, task=None):
    """
    Generates a report of collections and returns between two dates.
    Calculates prorated costs for partial payments and shows returns as negatives.
    """
    from billing.models import PaymentMovement
    
    name = request.data.get('name', 'Informe de Cobraments')
    date_range = request.data.get('date_range', None)
    type_id = request.data.get('type_id', None)
    exploitation_id = request.data.get('exploitation_id', None)

    if not date_range:
        return Response({"error": "date_range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None

    # Handle both ISO strings and date strings
    try:
        if 'T' in date_range[0]:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ').date()
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ').date()
        else:
            start_date = parse_date(date_range[0])
            end_date = parse_date(date_range[1])
    except Exception as e:
        return Response({"error": f"Invalid date format: {e}"}, status=status.HTTP_400_BAD_REQUEST), None, None

    # Query movements within range
    movements_qs = PaymentMovement.objects.filter(
        movement_date__range=(start_date, end_date)
    ).select_related(
        'payment', 'payment__invoice', 'payment__invoice__contract', 
        'payment__invoice__contract__holder', 'payment_type',
        'payment__commitment_deposit', 'payment__commitment_deposit__contract',
        'payment__commitment_deposit__contract__holder'
    ).prefetch_related(
        'payment__invoice__line_items', 'payment__invoice__line_items__product', 
        'payment__invoice__line_items__product__origin',
        'payment__commitment_deposit__invoices',
        'payment__commitment_deposit__invoices__line_items',
        'payment__commitment_deposit__invoices__line_items__product',
        'payment__commitment_deposit__invoices__line_items__product__origin'
    )

    if exploitation_id:
        movements_qs = movements_qs.filter(
            Q(payment__invoice__exploitation_id=exploitation_id) |
            Q(payment__commitment_deposit__invoices__exploitation_id=exploitation_id)
        ).distinct()

    multi_ids = get_multi_ids(request.data)
    multi_q = None
    if multi_ids['billing_ids']:
        multi_q = Q(payment__invoice__billing_id__in=multi_ids['billing_ids'])
    if multi_ids['contract_ids']:
        clause = Q(payment__invoice__contract_id__in=multi_ids['contract_ids'])
        multi_q = clause if multi_q is None else multi_q & clause
    if multi_ids['person_ids']:
        clause = (
            Q(payment__invoice__contract__owner_id__in=multi_ids['person_ids']) |
            Q(payment__invoice__contract__tenant_id__in=multi_ids['person_ids']) |
            Q(payment__invoice__contract__holder_id__in=multi_ids['person_ids'])
        )
        multi_q = clause if multi_q is None else multi_q & clause
    if multi_ids['remittance_ids']:
        clause = Q(payment__remittances__id__in=multi_ids['remittance_ids'])
        multi_q = clause if multi_q is None else multi_q & clause
    if multi_q:
        movements_qs = movements_qs.filter(multi_q).distinct()

    # Config tokens for categorization
    try:
        aca_product_token = ConfigProject.objects.get(token="token_product_aca").value
    except:
        aca_product_token = "ACA"
    
    try:
        clav_prod_token = ConfigProject.objects.get(token='report_clavegueram_product_token').value
    except:
        clav_prod_token = "CLAV"

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = _("Cobraments")

    headers = [
        _("N. Factura"), _("Data Factura"), _("Data Cobrament"), _("Periode"), _("C. Client"), _("Nif"), _("Nom"), 
        _("Quota servei (€)"), _("IVA QUOTA SERVEI AIGUA (€) 10%"),
        _("Aigua (€)"), _("IVA AIGUA (€) 10%"),
        _("Clavegueram (€)"), _("IVA CLAVEGUERAM (€) 10%"),
        _("Canon (€)"), 
        _("Ensobrat (€)"), _("IVA ENSOBRAT (€) 21%"), 
        _("IVA Aigua (€)"), _("Subtotal sense IVA (€)"), _("Total Factura"), _("Total Cobrat"), _("forma de pagament"), _("origen de pagament")
    ]
    
    # We use add_row from statistics.views.reports_views (imported at top)
    current_row = add_row(ws, 0, headers, fill=black_fill, font=white_bold_font)

    total_movements_progress = movements_qs.count()
    for idx_mov, mov in enumerate(movements_qs, start=1):
        if task and idx_mov % 50 == 0:
            task.update_state(
                state='PROGRESS',
                meta={
                    'current': idx_mov,
                    'total': total_movements_progress,
                    'percent': round((idx_mov / total_movements_progress) * 100, 2) if total_movements_progress else 0.0
                }
            )
        payment = mov.payment
        if not payment:
            continue
            
        invoice = payment.invoice
        commitment = payment.commitment_deposit
        
        if not invoice and not commitment:
            continue
            
        # is_positive determines if it's a collection (1) or a return (-1)
        multiplier = 1.0 if mov.is_positive else -1.0
        payment_amount = float(payment.amount if payment.amount else 0)
        
        if invoice:
            quota_servei_total = 0.0
            quota_servei_iva = 0.0
            aigua_total = 0.0
            aigua_iva = 0.0
            clavegueram_total = 0.0
            clavegueram_iva = 0.0
            canon_total = 0.0
            ensobrat_total = 0.0
            ensobrat_iva = 0.0
            iva_aigua_total = 0.0
            total_prorated = 0.0
            
            total_invoice = float(invoice.total_final if invoice.total_final else 0)
            factor = 1.0 * multiplier
            total_factura = total_invoice * multiplier
            
            for line in invoice.line_items.all():
                if not line.is_active:
                    continue
                    
                line_price = float(line.price if line.price is not None else 0)
                line_tax = float(line.tax_price if line.tax_price is not None else 0)
                
                # Ensure line_tax has the same sign as line_price
                if line_price < 0 and line_tax > 0:
                    line_tax = -line_tax
                elif line_price > 0 and line_tax < 0:
                    line_tax = -line_tax
                    
                line_total = line_price + line_tax
                
                prorated_price = line_price * factor
                prorated_tax = line_tax * factor
                prorated_total = line_total * factor
                
                prod = line.product
                prod_token = prod.token or "" if prod else ""
                prod_name = (line.product_name or (prod.name if prod else "")).upper()
                rate_name = (line.price_rate_name or (line.price_rate.name if line.price_rate else "") or "").upper()
                line_name = (line.name or "").upper()
                clav_base = clav_prod_token.split('_')[0]
                
                is_canon = _product_token_matches_aca(prod_token, aca_product_token) or 'CANON' in prod_name or 'CÀNON' in prod_name or 'CANON' in rate_name or 'CÀNON' in rate_name or 'CANON' in line_name or 'CÀNON' in line_name
                is_sewer = (clav_base and prod_token.startswith(clav_base)) or 'CLAVEGUERAM' in prod_name or 'CLAVEGUERAM' in rate_name or 'CLAVEGUERAM' in line_name
                is_ensobrat = prod_token == 'ENSOBRAT' or 'ENSOBRAT' in prod_name or 'ENSOBRAT' in rate_name or 'ENSOBRAT' in line_name
                is_quota_servei = prod_token == 'QUO-SER-AIGUA' or \
                                  any(kw in prod_name for kw in ['QUOTA', 'CUOTA', 'FIXA', 'FIJA']) or \
                                  any(kw in rate_name for kw in ['QUOTA', 'CUOTA', 'FIXA', 'FIJA']) or \
                                  any(kw in line_name for kw in ['QUOTA', 'CUOTA', 'FIXA', 'FIJA'])
                is_water = (prod and prod.origin and prod.origin.token == 'aigua') or 'AIGUA' in prod_name or 'AIGUA' in rate_name or 'AIGUA' in line_name
                
                if is_canon:
                    canon_total += prorated_price
                elif is_sewer:
                    clavegueram_total += prorated_price
                    clavegueram_iva += prorated_tax
                elif is_ensobrat:
                    ensobrat_total += prorated_price
                    ensobrat_iva += prorated_tax
                elif is_quota_servei:
                    quota_servei_total += prorated_price
                    quota_servei_iva += prorated_tax
                elif is_water:
                    aigua_total += prorated_price
                    aigua_iva += prorated_tax
                
                # Base IVA: only sum lines where VAT is applicable (tax percent > 0)
                if (line.tax and line.tax.percent and line.tax.percent > 0) or (line.tax_percent and float(line.tax_percent) > 0):
                    pass
                    
                # IVA Aigua: VAT for water category (excluding sewer and canon)
                if is_water and not is_canon and not is_sewer:
                    iva_aigua_total += prorated_tax
                    
                total_prorated += prorated_price
                
            n_factura = invoice.serie_final or invoice.number or ""
            data_factura = invoice.issue_date
            
            p_year = invoice.billing_period_year
            p_month = invoice.billing_period_month
            if not p_year or not p_month:
                if invoice.issue_date:
                    p_year = invoice.issue_date.year
                    p_month = invoice.issue_date.month
            periode_str = ""
            if p_year and p_month:
                if p_month in [1,2,3]: t = "1T"
                elif p_month in [4,5,6]: t = "2T"
                elif p_month in [7,8,9]: t = "3T"
                else: t = "4T"
                periode_str = f"{t} {p_year}"
                
            contract = invoice.contract
            c_contracte = ""
            nif_client = ""
            nom_client = ""
            if contract:
                c_contracte = contract.token or ""
                holder = contract.holder
                if holder:
                    nif_client = holder.token or ""
                    nom_client = f"{holder.name} {holder.surname if holder.surname else ''}".strip()
            if not nom_client:
                nom_client = invoice.customer_final or ""
                nif_client = invoice.customer_token_final or ""
                
            forma_pagament = mov.payment_type.name if mov.payment_type else (invoice.payment_type_final or "")
            
            row_data = [
                n_factura,
                data_factura.strftime("%d/%m/%Y") if data_factura else "",
                mov.movement_date.strftime("%d/%m/%Y") if mov.movement_date else "",
                periode_str,
                c_contracte,
                nif_client,
                nom_client,
                round(quota_servei_total, 2),
                round(quota_servei_iva, 2),
                round(aigua_total, 2),
                round(aigua_iva, 2),
                round(clavegueram_total, 2),
                round(clavegueram_iva, 2),
                round(canon_total, 2),
                round(ensobrat_total, 2),
                round(ensobrat_iva, 2),
                round(iva_aigua_total, 2),
                round(total_prorated, 2),
                round(total_factura, 2),
                round(payment_amount * multiplier, 2),
                forma_pagament,
                mov.get_payment_origin_display() or ""
            ]
            current_row = add_row(ws, current_row, row_data)
            
        elif commitment:
            linked_invoices = list(commitment.invoices.all())
            if linked_invoices:
                total_invoices = sum(float(inv.total_final if inv.total_final else 0) for inv in linked_invoices)
                factor = 1.0 * multiplier
                
                for inv in linked_invoices:
                    quota_servei_total = 0.0
                    quota_servei_iva = 0.0
                    aigua_total = 0.0
                    aigua_iva = 0.0
                    clavegueram_total = 0.0
                    clavegueram_iva = 0.0
                    canon_total = 0.0
                    ensobrat_total = 0.0
                    ensobrat_iva = 0.0
                    iva_aigua_total = 0.0
                    total_prorated = 0.0
                    
                    inv_total = float(inv.total_final if inv.total_final else 0)
                    inv_weight = (inv_total / total_invoices) if total_invoices != 0 else 0
                    inv_payment_amount = payment_amount * inv_weight
                    total_factura = inv_total * multiplier
                    
                    for line in inv.line_items.all():
                        if not line.is_active:
                            continue
                            
                        line_price = float(line.price if line.price is not None else 0)
                        line_tax = float(line.tax_price if line.tax_price is not None else 0)
                        
                        # Ensure line_tax has the same sign as line_price
                        if line_price < 0 and line_tax > 0:
                            line_tax = -line_tax
                        elif line_price > 0 and line_tax < 0:
                            line_tax = -line_tax
                            
                        line_total = line_price + line_tax
                        
                        prorated_price = line_price * factor
                        prorated_tax = line_tax * factor
                        prorated_total = line_total * factor
                        
                        prod = line.product
                        prod_token = prod.token or "" if prod else ""
                        prod_name = (line.product_name or (prod.name if prod else "")).upper()
                        rate_name = (line.price_rate_name or (line.price_rate.name if line.price_rate else "") or "").upper()
                        line_name = (line.name or "").upper()
                        clav_base = clav_prod_token.split('_')[0]
                        
                        is_canon = _product_token_matches_aca(prod_token, aca_product_token) or 'CANON' in prod_name or 'CÀNON' in prod_name or 'CANON' in rate_name or 'CÀNON' in rate_name or 'CANON' in line_name or 'CÀNON' in line_name
                        is_sewer = (clav_base and prod_token.startswith(clav_base)) or 'CLAVEGUERAM' in prod_name or 'CLAVEGUERAM' in rate_name or 'CLAVEGUERAM' in line_name
                        is_ensobrat = prod_token == 'ENSOBRAT' or 'ENSOBRAT' in prod_name or 'ENSOBRAT' in rate_name or 'ENSOBRAT' in line_name
                        is_quota_servei = prod_token == 'QUO-SER-AIGUA' or \
                                          any(kw in prod_name for kw in ['QUOTA', 'CUOTA', 'FIXA', 'FIJA']) or \
                                          any(kw in rate_name for kw in ['QUOTA', 'CUOTA', 'FIXA', 'FIJA']) or \
                                          any(kw in line_name for kw in ['QUOTA', 'CUOTA', 'FIXA', 'FIJA'])
                        is_water = (prod and prod.origin and prod.origin.token == 'aigua') or 'AIGUA' in prod_name or 'AIGUA' in rate_name or 'AIGUA' in line_name
                        
                        if is_canon:
                            canon_total += prorated_price
                        elif is_sewer:
                            clavegueram_total += prorated_price
                            clavegueram_iva += prorated_tax
                        elif is_ensobrat:
                            ensobrat_total += prorated_price
                            ensobrat_iva += prorated_tax
                        elif is_quota_servei:
                            quota_servei_total += prorated_price
                            quota_servei_iva += prorated_tax
                        elif is_water:
                            aigua_total += prorated_price
                            aigua_iva += prorated_tax
                            
                        # IVA Aigua: VAT for water category (excluding sewer and canon)
                        if is_water and not is_canon and not is_sewer:
                            iva_aigua_total += prorated_tax
                            
                        total_prorated += prorated_price
                        
                    n_factura = inv.serie_final or inv.number or ""
                    data_factura = inv.issue_date
                    
                    p_year = inv.billing_period_year
                    p_month = inv.billing_period_month
                    if not p_year or not p_month:
                        if data_factura:
                            p_year = data_factura.year
                            p_month = data_factura.month
                    periode_str = ""
                    if p_year and p_month:
                        if p_month in [1,2,3]: t = "1T"
                        elif p_month in [4,5,6]: t = "2T"
                        elif p_month in [7,8,9]: t = "3T"
                        else: t = "4T"
                        periode_str = f"{t} {p_year}"
                        
                    inv_contract = inv.contract
                    c_contracte = ""
                    nif_client = ""
                    nom_client = ""
                    if inv_contract:
                        c_contracte = inv_contract.token or ""
                        holder = inv_contract.holder
                        if holder:
                            nif_client = holder.token or ""
                            nom_client = f"{holder.name} {holder.surname if holder.surname else ''}".strip()
                    if not nom_client:
                        nom_client = inv.customer_final or commitment.customer_final or ""
                        nif_client = inv.customer_token_final or commitment.customer_token_final or ""
                        
                    inv_forma = mov.payment_type.name if mov.payment_type else (inv.payment_type_final or "")
                    
                    row_data = [
                        n_factura,
                        data_factura.strftime("%d/%m/%Y") if data_factura else "",
                        mov.movement_date.strftime("%d/%m/%Y") if mov.movement_date else "",
                        periode_str,
                        c_contracte,
                        nif_client,
                        nom_client,
                        round(quota_servei_total, 2),
                        round(quota_servei_iva, 2),
                        round(aigua_total, 2),
                        round(aigua_iva, 2),
                        round(clavegueram_total, 2),
                        round(clavegueram_iva, 2),
                        round(canon_total, 2),
                        round(ensobrat_total, 2),
                        round(ensobrat_iva, 2),
                        round(iva_aigua_total, 2),
                        round(total_prorated, 2),
                        round(total_factura, 2),
                        round(inv_payment_amount * multiplier, 2),
                        inv_forma,
                        mov.get_payment_origin_display() or ""
                    ]
                    current_row = add_row(ws, current_row, row_data)
            else:
                quota_servei_total = 0.0
                quota_servei_iva = 0.0
                aigua_total = 0.0
                aigua_iva = 0.0
                clavegueram_total = 0.0
                clavegueram_iva = 0.0
                canon_total = 0.0
                ensobrat_total = 0.0
                ensobrat_iva = 0.0
                iva_aigua_total = 0.0
                total_prorated = payment_amount * multiplier
                total_factura = payment_amount * multiplier
                
                n_factura = f"Compromís: {commitment.token or ''}"
                data_factura = commitment.created_at.date() if commitment.created_at else None
                periode_str = ""
                contract = commitment.contract
                c_contracte = ""
                nif_client = ""
                nom_client = ""
                if contract:
                    c_contracte = contract.token or ""
                    holder = contract.holder
                    if holder:
                        nif_client = holder.token or ""
                        nom_client = f"{holder.name} {holder.surname if holder.surname else ''}".strip()
                if not nom_client:
                    nom_client = commitment.customer_final or ""
                    nif_client = commitment.customer_token_final or ""
                    
                forma_pagament = mov.payment_type.name if mov.payment_type else ""
                
                row_data = [
                    n_factura,
                    data_factura.strftime("%d/%m/%Y") if data_factura else "",
                    mov.movement_date.strftime("%d/%m/%Y") if mov.movement_date else "",
                    periode_str,
                    c_contracte,
                    nif_client,
                    nom_client,
                    round(quota_servei_total, 2),
                    round(quota_servei_iva, 2),
                    round(aigua_total, 2),
                    round(aigua_iva, 2),
                    round(clavegueram_total, 2),
                    round(clavegueram_iva, 2),
                    round(canon_total, 2),
                    round(ensobrat_total, 2),
                    round(ensobrat_iva, 2),
                    round(iva_aigua_total, 2),
                    round(total_prorated, 2),
                    round(total_factura, 2),
                    round(payment_amount * multiplier, 2),
                    forma_pagament,
                    mov.get_payment_origin_display() or ""
                ]
                current_row = add_row(ws, current_row, row_data)

    from openpyxl.utils import get_column_letter
    vat_col_indices = [9, 11, 13, 16, 17]
    for col_idx in vat_col_indices:
        has_non_zero = False
        for r in range(2, ws.max_row + 1):
            val = ws.cell(row=r, column=col_idx).value
            if val is not None:
                try:
                    if float(val) != 0.0:
                        has_non_zero = True
                        break
                except (ValueError, TypeError):
                    pass
        if not has_non_zero:
            col_letter = get_column_letter(col_idx)
            ws.column_dimensions[col_letter].hidden = True

    adjust_column_widths(ws)
    
    filename = f"informe_cobraments_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(filename)

    # Convert Workbook to Response and Save as Document
    with open(filename, "rb") as f:
        content = f.read()
        response = HttpResponse(content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f"attachment; filename={filename}"

    document_id = save_report(
        content=wb,
        filename=filename,
        name=name,
        type_id=type_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    if os.path.exists(filename):
        os.remove(filename)
        
    return response, document_id, filename


def generate_recaptacio_conceptes_excel(request, black_fill=None, white_bold_font=None, task=None):
    """
    Informe de Recaptació per Conceptes (Productes).
    Basat en l'informe de clavegueram però ampliat a tots els productes,
    mostrant només la part recaptada (prorratejada) per cada categoria.
    """
    from billing.models import PaymentMovement, Invoice, InvoiceLineItem, Payment
    from pricing.models import Product
    import openpyxl
    import datetime
    from django.http import HttpResponse
    from rest_framework import status
    from rest_framework.response import Response
    import os
    from django.utils.translation import gettext as _
    from django.db.models import Q, F
    from django.db.models.functions import Coalesce

    try:
        date_range = request.data.get('date_range')
        exploitation_id = request.data.get('exploitation_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        if date_range:
            if not start_date: start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ').date()
            if not end_date: end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ').date()
        
        if isinstance(start_date, str):
            start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()

        name = request.data.get('name', _('Informe de Recaptació per Conceptes'))
        type_id = request.data.get('type_id', None)

        # Query movements within range
        movements_qs = PaymentMovement.objects.filter(
            movement_date__range=(start_date, end_date),
            is_active=True
        ).select_related(
            'payment', 'payment__invoice', 'payment__invoice__contract', 
            'payment__invoice__contract__holder', 'payment_type',
            'payment__commitment_deposit', 'payment__commitment_deposit__contract',
            'payment__commitment_deposit__contract__holder',
            'payment__invoice__contract__use_type',
            'current_status'
        ).prefetch_related(
            'payment__invoice__line_items', 
            'payment__invoice__line_items__product',
            'payment__invoice__line_items__price_rate',
            'payment__invoice__line_items__price_rate__product',
            'payment__commitment_deposit__invoices',
            'payment__commitment_deposit__invoices__line_items',
            'payment__commitment_deposit__invoices__line_items__product',
            'payment__commitment_deposit__invoices__line_items__price_rate',
            'payment__commitment_deposit__invoices__line_items__price_rate__product',
            'payment__invoice__contract__variables'
        )

        if exploitation_id and exploitation_id != 'all':
            movements_qs = movements_qs.filter(
                Q(payment__invoice__exploitation_id=exploitation_id) |
                Q(payment__commitment_deposit__invoices__exploitation_id=exploitation_id)
            ).distinct()

        # Identifiquem tots els productes que apareixen en aquestes factures per crear les columnes
        product_ids = set()
        has_custom_concepts = False
        movements_data = []

        total_movements_progress = movements_qs.count()
        for idx_mov, mov in enumerate(movements_qs, start=1):
            if task and idx_mov % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx_mov,
                        'total': total_movements_progress,
                        'percent': round((idx_mov / total_movements_progress) * 50, 2) if total_movements_progress else 0.0
                    }
                )
            payment = mov.payment
            if not payment: continue
            
            invoice = payment.invoice
            commitment = payment.commitment_deposit
            if not invoice and not commitment: continue
            
            movements_data.append(mov)
            
            invoices_to_check = []
            if invoice: invoices_to_check.append(invoice)
            elif commitment: invoices_to_check.extend(list(commitment.invoices.all()))
            
            for inv in invoices_to_check:
                for line in inv.line_items.all():
                    if line.is_active:
                        prod = line.product or (line.price_rate.product if line.price_rate else None)
                        if prod:
                            product_ids.add(prod.id)
                        else:
                            has_custom_concepts = True
        
        products = list(Product.objects.filter(id__in=product_ids).order_by('name'))
        
        if has_custom_concepts:
            class CustomConceptPlaceholder:
                def __init__(self):
                    self.id = 'custom_concepts'
                    self.name = _("Conceptes personalitzats")
            products.append(CustomConceptPlaceholder())
        
        wb = openpyxl.Workbook()
        ws_summary = wb.active
        ws_summary.title = _("Resum per Productes")
        
        ws_detail = wb.create_sheet(title=_("Detall Moviments"))

        # Headers Detail
        headers_detail = [
            _("Contracte"), _("Titular"), _("NIF"), _("Adreça Subministrament"),
            _("Número Factura"), _("Data Factura"), _("Data Cobrament"), _("Tipus Moviment"), 
            _("Periode Liquidat"), _("Consum anual"), _("Tipologia de client")
        ]
        for p in products:
            headers_detail.append(f"{p.name} (€)")
        
        headers_detail.extend([_("Base IVA (€)"), _("IVA (€)"), _("Total Recaptat (€)"), _("Forma Pagament"), _("Origen Pagament")])
        
        current_row_detail = add_row(ws_detail, 0, headers_detail, fill=black_fill, font=white_bold_font)
        
        # Diccionari per als totals del resum
        summary_totals = {p.id: 0.0 for p in products}
        total_base_global = 0.0
        total_tax_global = 0.0

        total_movements_data_progress = len(movements_data)
        for idx_mov_data, mov in enumerate(movements_data, start=1):
            if task and idx_mov_data % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx_mov_data,
                        'total': total_movements_data_progress,
                        'percent': 50 + round((idx_mov_data / total_movements_data_progress) * 50, 2) if total_movements_data_progress else 50.0
                    }
                )
            payment = mov.payment
            multiplier = 1.0 if mov.is_positive else -1.0
            payment_amount = float(payment.amount or 0)
            
            # Tipus de moviment
            tipo_mov = _("Cobrament") if mov.is_positive else _("Devolució/Anul·lació")
            if mov.current_status:
                tipo_mov = f"{tipo_mov} ({mov.current_status.name})"

            invoice = payment.invoice
            commitment = payment.commitment_deposit
            
            invoices_to_process = []
            if invoice:
                invoices_to_process.append((invoice, 1.0)) # (invoice, weight)
            elif commitment:
                linked_invoices = list(commitment.invoices.all())
                total_invoices_amount = sum(float(inv.total_final or 0) for inv in linked_invoices)
                for inv in linked_invoices:
                    weight = (float(inv.total_final or 0) / total_invoices_amount) if total_invoices_amount > 0 else 0
                    invoices_to_process.append((inv, weight))

            for inv, weight in invoices_to_process:
                inv_total = float(inv.total_final or 0)
                # El factor de prorrateig respecte al que s'ha pagat realment en aquest moviment
                factor = (payment_amount / inv_total) * multiplier * weight if inv_total != 0 else 0
                
                prod_values = {p.id: 0.0 for p in products}
                base_iva_total = 0.0
                tax_total = 0.0
                
                for line in inv.line_items.all():
                    if not line.is_active: continue
                    
                    line_price = float(line.price or 0)
                    line_tax = float(line.tax_price or 0)
                    
                    # Ensure line_tax has the same sign as line_price
                    if line_price < 0 and line_tax > 0:
                        line_tax = -line_tax
                    elif line_price > 0 and line_tax < 0:
                        line_tax = -line_tax
                    
                    line_total = line_price + line_tax
                    
                    prorated_total = line_total * factor
                    prorated_base = line_price * factor
                    prorated_tax = line_tax * factor
                    
                    prod = line.product or (line.price_rate.product if line.price_rate else None)
                    prod_id = prod.id if prod else 'custom_concepts'
                    
                    if prod_id and prod_id in prod_values:
                        prod_values[prod_id] += prorated_total
                    
                    base_iva_total += prorated_base
                    tax_total += prorated_tax
                
                # Ensure base_iva_total and tax_total signs are consistent at the row level
                if base_iva_total > 0 and tax_total < 0:
                    tax_total = -tax_total
                elif base_iva_total < 0 and tax_total > 0:
                    tax_total = -tax_total
                
                total_base_global += base_iva_total
                total_tax_global += tax_total

                # Dades de la fila
                n_factura = inv.serie_final or inv.number or ""
                data_factura = inv.issue_date
                
                # Període trimestral vinculat a la data del moviment de cartera
                periode_str = ""
                if mov.movement_date:
                    m = mov.movement_date.month
                    y = mov.movement_date.year
                    t = (m + 2) // 3
                    periode_str = f"{t}T {y}"
                
                c_contracte = inv.contract.token if inv.contract else ""
                nif_client = inv.customer_token_final or inv.payer_token_final or ""
                nom_client = inv.customer_final or ""
                forma_pagament = mov.payment_type.name if mov.payment_type else (inv.payment_type_final or "")
                
                address_parts = list(filter(bool, [inv.address_final, inv.postal_code_final, inv.city_final]))
                client_type = inv.contract.use_type.name if inv.contract and inv.contract.use_type else _("Desconegut")
                
                # Consum anual variable
                consum_anual = ""
                if inv.contract:
                    ca_vars = [v for v in inv.contract.variables.all() if 'Consum anual' in (v.name or '')]
                    if ca_vars:
                        ca_vars.sort(key=lambda x: x.name or '', reverse=True)
                        consum_anual = ca_vars[0].value or ""

                row_data = [
                    c_contracte,
                    nom_client,
                    nif_client,
                    ", ".join(address_parts),
                    n_factura,
                    data_factura.strftime("%d/%m/%Y") if data_factura else "",
                    mov.movement_date.strftime("%d/%m/%Y") if mov.movement_date else "",
                    tipo_mov,
                    periode_str,
                    consum_anual,
                    client_type
                ]
                # Round product values for the row
                rounded_prod_values = {p_id: round(val, 2) for p_id, val in prod_values.items()}
                
                # Accumulate the rounded values to summary_totals
                for p_id, val in rounded_prod_values.items():
                    summary_totals[p_id] += val

                row_data = [
                    c_contracte,
                    nom_client,
                    nif_client,
                    ", ".join(address_parts),
                    n_factura,
                    data_factura.strftime("%d/%m/%Y") if data_factura else "",
                    mov.movement_date.strftime("%d/%m/%Y") if mov.movement_date else "",
                    tipo_mov,
                    periode_str,
                    consum_anual,
                    client_type
                ]
                for p in products:
                    row_data.append(rounded_prod_values[p.id])
                
                total_recaptat_calc = sum(rounded_prod_values.values())
                
                row_data.extend([
                    round(base_iva_total, 2),
                    round(tax_total, 2),
                    round(total_recaptat_calc, 2),
                    forma_pagament,
                    mov.get_payment_origin_display() or ""
                ])
                current_row_detail = add_row(ws_detail, current_row_detail, row_data)

        # Fill Summary Tab
        headers_summary = [_("Producte"), _("Total Recaptat (€)")]
        current_row_summary = add_row(ws_summary, 0, headers_summary, fill=black_fill, font=white_bold_font)
        
        for p in products:
            row_summary = [p.name, round(summary_totals[p.id], 2)]
            current_row_summary = add_row(ws_summary, current_row_summary, row_summary)
            ws_summary.cell(row=current_row_summary, column=2).number_format = '#,##0.00'
        
        current_row_summary = jump_row(current_row_summary)
        total_global = sum(summary_totals.values())
        footer_summary = [_("TOTAL RECAPTAT"), round(total_global, 2)]
        add_row(ws_summary, current_row_summary, footer_summary, fill=black_fill, font=white_bold_font)
        ws_summary.cell(row=current_row_summary + 1, column=2).number_format = '#,##0.00'

        adjust_column_widths(ws_summary)
        adjust_column_widths(ws_detail)

        # Creació de la pestanya de Resum per Empresa (Facturat, Cobrat, Pendent)
        ws_company = wb.create_sheet(title=_("Resum per Empresa"))
        
        # Obtenir les factures emeses en el rang de dates i explotació (mateixa lògica que generate_billing_taxes_detailed_summary)
        invoice_type_token = ConfigProject.objects.get(token="invoice_type_invoice_token").value
        invoices_for_company = Invoice.objects.filter(
            issue_date__range=(start_date, end_date),
            type_final=invoice_type_token
        ).distinct()
        
        if exploitation_id and exploitation_id != 'all':
            invoices_for_company = invoices_for_company.filter(
                Q(exploitation_id=exploitation_id) | Q(exploitation__isnull=True)
            )

        invoices_for_company = filter_pending_invoices(invoices_for_company, request)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices_for_company = invoices_for_company.filter(multi_q).distinct()

        # Cobrat: sum of payment.amount grouped by company, calculated from movements_data to match exactly
        cobrat_by_company = {}
        for mov in movements_data:
            payment = mov.payment
            if not payment:
                continue
            multiplier = Decimal('1.0') if mov.is_positive else Decimal('-1.0')
            payment_amount = payment.amount or Decimal('0.0')
            
            invoice = payment.invoice
            commitment = payment.commitment_deposit
            
            invoices_for_mov = []
            if invoice:
                invoices_for_mov.append(invoice)
            elif commitment:
                invoices_for_mov.extend(list(commitment.invoices.all()))
                
            if not invoices_for_mov:
                c_id = 2
                cobrat_by_company[c_id] = cobrat_by_company.get(c_id, Decimal('0.0')) + payment_amount * multiplier
            else:
                total_invoices_amount = sum(Decimal(str(inv.total_final or 0)) for inv in invoices_for_mov)
                for inv in invoices_for_mov:
                    weight = (Decimal(str(inv.total_final or 0)) / total_invoices_amount) if total_invoices_amount > 0 else Decimal('0.0')
                    comp = inv.company or (inv.exploitation.company if inv.exploitation else None)
                    c_id = comp.id if comp else 0
                    prorated_payment = payment_amount * multiplier * weight
                    cobrat_by_company[c_id] = cobrat_by_company.get(c_id, Decimal('0.0')) + prorated_payment

        # Obtenir els tokens d'estats pagats
        try:
            paid_status_token = ConfigProject.objects.get(token="invoice_status_paid_token").value
        except ConfigProject.DoesNotExist:
            paid_status_token = "0"
        try:
            payoff_status_token = ConfigProject.objects.get(token="invoice_status_payoff_token").value
        except ConfigProject.DoesNotExist:
            payoff_status_token = "4"

        company_data = {}
        invoices_for_company = invoices_for_company.select_related('company', 'exploitation__company', 'status')

        for inv in invoices_for_company:
            comp = inv.company or (inv.exploitation.company if inv.exploitation else None)
            if comp:
                comp_id = comp.id
                comp_name = comp.name or comp.alias or f"Empresa ID {comp.id}"
            else:
                comp_id = 0
                comp_name = _("Sense Empresa")

            if comp_id not in company_data:
                company_data[comp_id] = {
                    'name': comp_name,
                    'facturat': Decimal('0.0'),
                    'pendent': Decimal('0.0')
                }

            tf = inv.total_final or Decimal('0.0')
            if inv.status and inv.status.token in [paid_status_token, payoff_status_token]:
                ltp = Decimal('0.0')
            else:
                ltp = inv.left_to_pay or Decimal('0.0')
                if ltp < 0:
                    ltp = Decimal('0.0')
                if ltp > tf:
                    ltp = tf

            company_data[comp_id]['facturat'] += tf
            company_data[comp_id]['pendent'] += ltp

        # Ensure all companies with collections (Cobrat) are in company_data
        from service.models import Company
        for c_id in cobrat_by_company.keys():
            if c_id not in company_data:
                if c_id == 2:
                    comp_name = _("Empresa ID 2")
                elif c_id == 0:
                    comp_name = _("Sense Empresa")
                else:
                    try:
                        comp = Company.objects.get(id=c_id)
                        comp_name = comp.name or comp.alias or f"Empresa ID {comp.id}"
                    except Company.DoesNotExist:
                        comp_name = f"Empresa ID {c_id}"
                company_data[c_id] = {
                    'name': comp_name,
                    'facturat': Decimal('0.0'),
                    'pendent': Decimal('0.0')
                }

        headers_company = [_("Empresa"), _("Facturat (€)"), _("Cobrat (€)"), _("Pendent (€)")]
        current_row_company = add_row(ws_company, 0, headers_company, fill=black_fill, font=white_bold_font)

        total_facturat_global = Decimal('0.0')
        total_cobrat_global = Decimal('0.0')
        total_pendent_global = Decimal('0.0')

        for comp_id, data in sorted(company_data.items(), key=lambda x: x[1]['name']):
            facturat = data['facturat']
            pendent = data['pendent']
            cobrat = cobrat_by_company.get(comp_id, Decimal('0.0'))
            
            row_company = [
                data['name'],
                round(float(facturat), 2),
                round(float(cobrat), 2),
                round(float(pendent), 2)
            ]
            current_row_company = add_row(ws_company, current_row_company, row_company)
            ws_company.cell(row=current_row_company, column=2).number_format = '#,##0.00'
            ws_company.cell(row=current_row_company, column=3).number_format = '#,##0.00'
            ws_company.cell(row=current_row_company, column=4).number_format = '#,##0.00'
            
            total_facturat_global += facturat
            total_cobrat_global += cobrat
            total_pendent_global += pendent
            
        current_row_company = jump_row(current_row_company)
        footer_company = [
            _("TOTAL"),
            round(float(total_facturat_global), 2),
            round(float(total_cobrat_global), 2),
            round(float(total_pendent_global), 2)
        ]
        add_row(ws_company, current_row_company, footer_company, fill=black_fill, font=white_bold_font)
        ws_company.cell(row=current_row_company + 1, column=2).number_format = '#,##0.00'
        ws_company.cell(row=current_row_company + 1, column=3).number_format = '#,##0.00'
        ws_company.cell(row=current_row_company + 1, column=4).number_format = '#,##0.00'
        
        adjust_column_widths(ws_company)
        
        filename = f"{_('collection_by_concepts')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(filename)

        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"

        document_id = save_report(
            content=wb,
            filename=filename,
            name=name,
            type_id=type_id,
            start_date=start_date,
            end_date=end_date,
        )
        os.remove(filename)
        return response, document_id, filename

    except Exception as e:
        import traceback
        print("Error in generate_recaptacio_conceptes_excel: ", e)
        traceback.print_exc()
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None




def generate_clavegueram_invoices_excel(request, black_fill=None, white_bold_font=None, task=None):
    """
    Informe de clavegueram facturat.
    Queries Invoice directly and matches the layout and behavior of collection reports.
    """
    from billing.models import Invoice
    from pricing.models import Product
    from coredata.models import ConfigProject
    from service.models import Exploitation
    import openpyxl
    import datetime
    from django.http import HttpResponse
    from rest_framework import status
    from rest_framework.response import Response
    import os
    from django.utils.translation import gettext as _
    from statistics.views.reports_views import add_row, adjust_column_widths, filter_pending_invoices, save_report, jump_row

    try:
        date_range = request.data.get('date_range')
        exploitation_id = request.data.get('exploitation_id')
        start_date = request.data.get('start_date')
        end_date = request.data.get('end_date')
        
        if date_range:
            if not start_date: start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ').date()
            if not end_date: end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ').date()
        
        if isinstance(start_date, str):
            start_date = datetime.datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.datetime.strptime(end_date, '%Y-%m-%d').date()

        name = request.data.get('name', _('Informe de clavegueram facturat'))
        type_id = request.data.get('type_id', None)

        try:
            clav_prod_token = ConfigProject.objects.get(token='report_clavegueram_product_token').value
        except ConfigProject.DoesNotExist:
            clav_prod_token = "CLAV"

        try:
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
        except ConfigProject.DoesNotExist:
            invoice_type = "INVOICE"

        try:
            status_cancelled_token = ConfigProject.objects.get(token="invoice_status_cancelled_token").value
        except ConfigProject.DoesNotExist:
            status_cancelled_token = None

        invoices_qs = Invoice.objects.filter(
            issue_date__range=(start_date, end_date),
            type_final=invoice_type,
            line_items__product__token=clav_prod_token
        )
        if status_cancelled_token:
            invoices_qs = invoices_qs.exclude(status__token=status_cancelled_token)

        invoices_qs = filter_pending_invoices(invoices_qs, request).distinct()

        if exploitation_id and exploitation_id != 'all':
            invoices_qs = invoices_qs.filter(exploitation_id=exploitation_id)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices_qs = invoices_qs.filter(multi_q).distinct()

        invoices_qs = invoices_qs.select_related(
            'contract', 'contract__use_type', 'contract__holder', 'status'
        ).prefetch_related(
            'line_items', 'line_items__line_item_type', 'line_items__tax', 'line_items__product',
            'contract__variables'
        ).order_by('issue_date', 'number')


        wb = openpyxl.Workbook()
        ws_summary = wb.active
        ws_summary.title = _("Resum")

        ws_detail = wb.create_sheet(title=_("Detall Factures"))

        # Headers Detail
        headers_detail = [
            _("Contracte"),
            _("Titular"),
            _("NIF"),
            _("Adreça Subministrament"),
            _("Número Factura"),
            _("Data Factura"),
            _("període liquidat (1T, 2T, 3T, 4T)"),
            _("consum m3 utilitzat per al càlcul (Valor Variable)"),
            _("tipologia de client (industrial/domèstic)"),
            _("Quota Fixa"),
            _("Quota Variable")
        ]

        current_row_detail = add_row(ws_detail, 0, headers_detail, fill=black_fill, font=white_bold_font)

        total_fixed_sum = 0.0
        total_variable_sum = 0.0
        total_consum_sum = 0.0

        total_invoices_progress = invoices_qs.count()
        for idx_invoice, invoice in enumerate(invoices_qs, start=1):
            if task and idx_invoice % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx_invoice,
                        'total': total_invoices_progress,
                        'percent': round((idx_invoice / total_invoices_progress) * 100, 2) if total_invoices_progress else 0.0
                    }
                )
            clavegueram_lines = []
            for line in invoice.line_items.all():
                if not line.is_active:
                    continue
                prod = line.product or (line.price_rate.product if line.price_rate else None)
                if prod and prod.token == clav_prod_token:
                    clavegueram_lines.append(line)

            quota_fixa = 0.0
            quota_variable = 0.0

            for line in clavegueram_lines:
                # Classificació per nom del line_item_type (o de la línia si no n'hi ha).
                # En clavegueram, els LIT s'anomenen "QUOTA FIXA" i "QUOTA VARIABLE",
                # i no tenen price_variable_id ni price_interval_id.
                lit = line.line_item_type
                lit_name = (lit.name or '') if lit else ''
                line_name = (line.name or '')
                check_name = (lit_name or line_name).lower()
                if 'variable' in check_name:
                    is_variable = True
                elif 'fix' in check_name or 'fixa' in check_name:
                    is_variable = False
                elif lit is not None:
                    # Fallback estructural: Variable si té price_variable o price_interval
                    is_variable = bool(lit.price_variable_id or lit.price_interval_id)
                else:
                    # Últim recurs: si té unitats significatives, considerem variable
                    is_variable = bool(line.units and float(line.units) != 0)

                line_price = float(line.price if line.price is not None else 0)
                line_tax = float(line.tax_price if line.tax_price is not None else 0)

                # Ensure line_tax has the same sign as line_price
                if line_price < 0 and line_tax > 0:
                    line_tax = -line_tax
                elif line_price > 0 and line_tax < 0:
                    line_tax = -line_tax

                line_total = line_price + line_tax

                if is_variable:
                    quota_variable += line_total
                else:
                    quota_fixa += line_total

            # Consum anual from contract variables
            consum_m3 = ""
            if invoice.contract:
                ca_vars = [v for v in invoice.contract.variables.all() if 'Consum anual' in (v.name or '')]
                if ca_vars:
                    ca_vars.sort(key=lambda x: x.name or '', reverse=True)
                    consum_m3 = ca_vars[0].value or ""

            total_fixed_sum += quota_fixa
            total_variable_sum += quota_variable
            try:
                total_consum_sum += float(consum_m3)
            except (ValueError, TypeError):
                pass

            # Address parts
            address_parts = list(filter(bool, [invoice.address_final, invoice.postal_code_final, invoice.city_final]))
            address_str = ", ".join(address_parts)

            # Period computation from issue_date
            periode_str = ""
            if invoice.issue_date:
                m = invoice.issue_date.month
                y = invoice.issue_date.year
                t = (m + 2) // 3
                periode_str = f"{t}T {y}"

            c_contracte = invoice.contract.token if invoice.contract else ""
            nif_client = invoice.customer_token_final or invoice.payer_token_final or ""
            nom_client = invoice.customer_final or ""
            client_type = invoice.contract.use_type.name if invoice.contract and invoice.contract.use_type else _("Desconegut")

            row_data = [
                c_contracte,
                nom_client,
                nif_client,
                address_str,
                invoice.serie_final or invoice.number or "",
                invoice.issue_date.strftime("%d/%m/%Y") if invoice.issue_date else "",
                periode_str,
                consum_m3,
                client_type,
                round(quota_fixa, 2),
                round(quota_variable, 2)
            ]
            current_row_detail = add_row(ws_detail, current_row_detail, row_data)

            # Format Quota cells as decimal numbers
            ws_detail.cell(row=current_row_detail, column=10).number_format = '#,##0.00'
            ws_detail.cell(row=current_row_detail, column=11).number_format = '#,##0.00'

        # Append totals row at the bottom of the Detail tab
        current_row_detail = jump_row(current_row_detail)
        total_row = [
            _("TOTAL"),
            "",
            "",
            "",
            "",
            "",
            "",
            round(total_consum_sum, 4),
            "",
            round(total_fixed_sum, 2),
            round(total_variable_sum, 2)
        ]
        add_row(ws_detail, current_row_detail, total_row, fill=black_fill, font=white_bold_font)
        ws_detail.cell(row=current_row_detail + 1, column=10).number_format = '#,##0.00'
        ws_detail.cell(row=current_row_detail + 1, column=11).number_format = '#,##0.00'

        # Fill Summary tab
        headers_summary = [_("Tipus Quota"), _("Total Facturat (€)")]
        current_row_summary = add_row(ws_summary, 0, headers_summary, fill=black_fill, font=white_bold_font)

        current_row_summary = add_row(ws_summary, current_row_summary, [_("Quota Fixa"), round(total_fixed_sum, 2)])
        ws_summary.cell(row=current_row_summary, column=2).number_format = '#,##0.00'

        current_row_summary = add_row(ws_summary, current_row_summary, [_("Quota Variable"), round(total_variable_sum, 2)])
        ws_summary.cell(row=current_row_summary, column=2).number_format = '#,##0.00'

        current_row_summary = jump_row(current_row_summary)
        add_row(
            ws_summary,
            current_row_summary,
            [_("TOTAL CLAVEGUERAM"), round(total_fixed_sum + total_variable_sum, 2)],
            fill=black_fill,
            font=white_bold_font
        )
        ws_summary.cell(row=current_row_summary + 1, column=2).number_format = '#,##0.00'

        adjust_column_widths(ws_summary)
        adjust_column_widths(ws_detail)

        filename = f"informe_clavegueram_factures_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(filename)

        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"

        document_id = save_report(
            content=wb,
            filename=filename,
            name=name,
            type_id=type_id,
            start_date=start_date,
            end_date=end_date,
        )
        os.remove(filename)
        return response, document_id, filename

    except Exception as e:
        import traceback
        print("Error in generate_clavegueram_invoices_excel: ", e)
        traceback.print_exc()
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def generate_no_register_aca_contracts_report(request, black_fill=None, white_bold_font=None, task=None):
    try:
        # DE MOMENT NOMÉS ES CRIDA DES DE FACTURACIÓ
        token_product_aca = ConfigProject.objects.get(token="token_product_aca").value
        
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        billing_ids = get_billing_ids(request.data)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)	
        generate_object = request.data.get('generate_object', True)
        
        if not generate_object:
            request.data['include_preinvoices'] = True
        
        has_serie_range = has_serie_final_range(request.data)
        if not billing_ids and not date_range and not has_serie_range:
            return Response({"error": "billing id, date range or serie_final range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        billing = None
        billings = []
        start_date = None
        end_date = None
        
        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            billing = get_object_or_404(Billing, id=billing_ids[0])
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
            invoices = Invoice.objects.filter(issue_date__range=(start_date.date(), end_date.date()), type_final=invoice_type).distinct()
        elif has_serie_range:
            # Seleccio nomes pel rang de numero de factura: el rang ja identifica les
            # factures, sense lot ni periode. filter_pending_invoices hi aplica el rang
            # (apply_serie_final_range) i el periode surt de les factures resultants,
            # que es el que fan servir els titols i el nom del fitxer.
            invoices = filter_pending_invoices(serie_final_range_invoices(), request)
            start_date, end_date = serie_final_range_period(invoices)
            if start_date is None:
                return Response({"error": "the serie_final range has no invoices."}, status=status.HTTP_400_BAD_REQUEST), None, None
        else:
            raise Exception("Error obtaining invoices for report billing summary")
        
        if exploitation:
            invoices = invoices.filter(exploitation=exploitation)
        
        invoices = filter_pending_invoices(invoices, request).exclude(contract__price_rates__price_rate__product__token=token_product_aca).distinct()

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()
            
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("Facturació")
        
        row = 0
        title = _("Facturació sense ACA %(date)s") % {"date": billing.created_at.strftime('%d/%m/%Y')} if billing else _("Facturacions sense ACA %(start)s - %(end)s") % {"start": start_date.strftime('%d/%m/%Y'), "end": end_date.strftime('%d/%m/%Y')}
        
        main_title =[ title, "", "", "", "", ""]
        row = add_row(sheet, row, main_title)
        row = jump_row(row)
        
        titles = [
            _("Adreça Subministrament"),
            _("Contracte"),
            _("Titular"),
            _("Import"),
            _("Consum registrat"),
            _("Altres consums"),
            _("Consum facturat"),
            ]
        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)
        
        for invoice in invoices:
            row_data = [
                str(invoice.contract.supply_point_default.address) if invoice.contract and invoice.contract.supply_point_default and invoice.contract.supply_point_default.address else "",
                invoice.contract.token if invoice.contract else "",
                invoice.customer_final if invoice.customer_final else "",
                invoice.total_final,
                invoice.readings.filter(is_estimated=False).aggregate(total_consumption=Sum('real_consumption'))['total_consumption'] or 0,
                invoice.readings.filter(is_estimated=True).aggregate(total_consumption=Sum('calculated_value'))['total_consumption'] or 0,
                invoice.real_consumption
            ]
            row = add_row(sheet, row, row_data)

        adjust_column_widths(sheet)

        filename = f"informe_facturacio_sense_aca_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(filename)

        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"

        document_id = save_report(
            content=wb,
            filename=filename,
            name=name,
            type_id=type_id,
            start_date=start_date,
            end_date=end_date,
        )
        os.remove(filename)
        return response, document_id, filename

    except Exception as e:
        import traceback
        print("Error in generate_no_register_aca_contracts_report: ", e)
        traceback.print_exc()
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

# Permet personalitzar els reports per client: si existeix report_billing_service_personalized,
# s'usen les seves funcions en lloc de les d'aquest mòdul.
try:
    from statistics.utils import report_billing_service_personalized
    for _attr in dir(report_billing_service_personalized):
        if not _attr.startswith("_"):
            globals()[_attr] = getattr(report_billing_service_personalized, _attr)
except ImportError:
    pass