import re
from itertools import groupby

import openpyxl
from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response

from billing.models import Invoice, InvoiceLineItem
from billing.utils.invoice_range_utils import filter_invoices_by_serie_final_range, split_serie_final
from coredata.models import ConfigProject
from statistics.utils.report_billing_service import _payoff_signed_sum
from statistics.utils.report_filters import get_multi_ids, invoice_multi_filter_q
from statistics.views.reports_views import add_row, adjust_column_widths, jump_row, save_report

# Retalla la part variable per factura d'una descripció de línia, perquè conceptes com
# "CONSUM - 1R TRAM" no s'explotin en una fila diferent per cada factura només perque el
# llindar del tram (bonificacio d'ampliacio de trams) o el consum del darrer tram varien:
#   "CONSUM - 1R TRAM; Límit: 27"                          -> "CONSUM - 1R TRAM"
#   "CONSUM - 1R TRAM; - Ampliació de tram Límit: 30"       -> "CONSUM - 1R TRAM"
#   "CONSUM - 4T TRAM (335 m3)"                             -> "CONSUM - 4T TRAM"
_TRAILING_M3_RE = re.compile(r'\s*\(\d+(\.\d+)?\s*m3\)\s*$', re.IGNORECASE)


def _canonical_description(description):
    if not description:
        return description
    base = description.split(';', 1)[0].strip()
    base = _TRAILING_M3_RE.sub('', base).strip()
    return base


def generate_general_billing_summary_report(request, black_fill, white_bold_font, task=None):
    """Genera el "Resum de la facturació general": factures del rang
    [serie_final_from, serie_final_to] agrupades per Ús i Descripció, amb
    Núm. de factures / m³ / Base IVA / Quota IVA / Total, seguint el mateix
    format que produïa l'antic sistema Kais."""
    try:
        serie_final_from = request.data.get('serie_final_from')
        serie_final_to = request.data.get('serie_final_to')
        prefix = request.data.get('prefix')
        name = request.data.get('name', _('Resum de la facturació general'))
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        # Filtre d'usuari (general-billing-summary.vue): per defecte s'exclouen les
        # factures ja marcades com a revisades perquè no es tornin a incloure en una
        # nova generació del mateix rang; l'usuari pot desmarcar-ho per incloure-les.
        # Nomes s'aplica si es demana: la pantalla de rangs sempre l'envia i la
        # pantalla d'informes no porta aquesta casella.
        exclude_reviewed = request.data.get('exclude_reviewed', False)

        if serie_final_from is None or serie_final_to is None:
            return Response({"error": "serie_final_from and serie_final_to are required."}, status=status.HTTP_400_BAD_REQUEST), None, None

        # Els numeros de factura poden portar prefix alfabetic (p.ex. "D1234567",
        # despeses d'impagats), per aixo no es validen amb int() ni s'hi passen
        # convertits: el filtre de rang necessita el prefix per acotar la serie.
        # No es pot fer servir `_` per descartar el prefix: en aquest modul `_` es
        # gettext (import de dalt), i assignar-li res converteix `_` en variable local
        # de tota la funcio, de manera que el `_('Resum de la facturacio general')` de
        # mes amunt peta amb UnboundLocalError abans d'arribar fins aqui.
        from_alpha, from_number = split_serie_final(serie_final_from)
        to_alpha, to_number = split_serie_final(serie_final_to)
        if from_number is None or to_number is None:
            return Response({"error": "serie_final_from and serie_final_to must be invoice numbers (e.g. 12345678 or D1234567)."}, status=status.HTTP_400_BAD_REQUEST), None, None

        if int(from_number) > int(to_number):
            serie_final_from, serie_final_to = serie_final_to, serie_final_from

        invoices = filter_invoices_by_serie_final_range(
            Invoice.objects.filter(is_active=True, is_excluded=False), serie_final_from, serie_final_to, prefix=prefix
        )

        if exploitation_id:
            invoices = invoices.filter(exploitation_id=exploitation_id)

        if exclude_reviewed:
            invoices = invoices.filter(reviewed=False)

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        payoff_status_token = ConfigProject.objects.get(token="invoice_status_payoff_token").value

        active_line_items = InvoiceLineItem.objects.filter(invoice__in=invoices, is_active=True)

        use_counts = {
            item['use_type_id']: item['count']
            for item in active_line_items.values(use_type_id=F('invoice__contract__use_type_id'))
            .annotate(count=Count('invoice', distinct=True))
        }

        data = list(
            active_line_items.values(
                'name',
                'product_name',
                use_type_id=F('invoice__contract__use_type_id'),
                use_type_name=F('invoice__contract__use_type__name'),
                product_position=F('product__position'),
            )
            .annotate(
                invoice_count=Count('invoice', distinct=True),
                units_sum=Sum('units'),
                base_sum=_payoff_signed_sum('price', payoff_status_token),
                tax_sum=_payoff_signed_sum('tax_price', payoff_status_token),
            )
            # Primer producte (mateix ordre que fa servir la factura, `Product.position`),
            # despres tarifa (Ús) i, dins de cada tarifa, concepte -- igual que l'antic
            # Kais ("1 Consum" / "2 Manteniment" / "3 Quota" / "5 ACA", cadascun amb les
            # seves tarifes a dins).
            .order_by('product_position', 'product_name', 'use_type_name', 'name')
        )

        tax_data = list(
            active_line_items.values('tax_percent')
            .annotate(
                count=Count('invoice', distinct=True),
                base_sum=_payoff_signed_sum('price', payoff_status_token),
                tax_sum=_payoff_signed_sum('tax_price', payoff_status_token),
            )
            .order_by('tax_percent')
        )

        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("Resum Facturació General")

        row = 0
        title = f"{_('RESUM DE LA FACTURACIÓ GENERAL')}"
        row = add_row(sheet, row, [title, "", "", "", "", "", ""])
        range_label = f"{_('Del núm. de factura')} {serie_final_from} {_('a la')} {serie_final_to}."
        if prefix:
            range_label += f" ({_('Prefix')}: {prefix})"
        row = add_row(sheet, row, [range_label, "", "", "", "", "", ""])
        row = jump_row(row)

        titles = [_("Ús"), _("Descripció"), _("Núm. de factures"), _("m³"), _("Base IVA"), _("Quota IVA"), _("Total")]
        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)

        grand_units = 0.0
        grand_base = 0.0
        grand_tax = 0.0

        for product_name_key, product_items in groupby(data, key=lambda item: item['product_name']):
            product_items = list(product_items)
            product_name = product_name_key or _("Sense producte")

            row = add_row(
                sheet, row, [f"{_('Producte')}: {product_name}", "", "", "", "", "", ""],
                fill=black_fill, font=white_bold_font,
            )

            product_units = 0.0
            product_base = 0.0
            product_tax = 0.0

            for _use_type_name, items in groupby(product_items, key=lambda item: item['use_type_name']):
                items = list(items)
                use_type_name = items[0]['use_type_name'] or _("Sense ús")
                use_type_key = items[0]['use_type_id']
                factures = use_counts.get(use_type_key, 0)

                row = add_row(sheet, row, [f"{_('Ús')}: {use_type_name}", f"{_('Factures')}: {factures}", "", "", "", "", ""])

                use_units = 0.0
                use_base = 0.0
                use_tax = 0.0

                # Reagrupem per descripció canònica (sense la part variable per factura:
                # llindar de tram / consum del darrer tram) perquè un mateix concepte no
                # surti en una fila diferent per cada factura.
                canonical_totals = {}
                canonical_order = []
                for item in items:
                    units = float(item['units_sum'] or 0)
                    base = float(item['base_sum'] or 0)
                    tax = float(item['tax_sum'] or 0)
                    use_units += units
                    use_base += base
                    use_tax += tax

                    canonical_desc = _canonical_description(item['name']) or _("Sense descripció")
                    if canonical_desc not in canonical_totals:
                        canonical_totals[canonical_desc] = {'units': 0.0, 'base': 0.0, 'tax': 0.0}
                        canonical_order.append(canonical_desc)
                    bucket = canonical_totals[canonical_desc]
                    bucket['units'] += units
                    bucket['base'] += base
                    bucket['tax'] += tax

                for canonical_desc in canonical_order:
                    bucket = canonical_totals[canonical_desc]
                    row = add_row(sheet, row, [
                        "",
                        canonical_desc,
                        "",
                        round(bucket['units'], 2),
                        round(bucket['base'], 2),
                        round(bucket['tax'], 2),
                        round(bucket['base'] + bucket['tax'], 2),
                    ])

                row = add_row(sheet, row, [
                    "", _("Subtotal"), "",
                    round(use_units, 2), round(use_base, 2), round(use_tax, 2), round(use_base + use_tax, 2),
                ], font=white_bold_font, fill=black_fill)

                product_units += use_units
                product_base += use_base
                product_tax += use_tax

            row = add_row(sheet, row, [
                f"{_('Total')} {product_name}", "", "",
                round(product_units, 2), round(product_base, 2), round(product_tax, 2), round(product_base + product_tax, 2),
            ], font=white_bold_font, fill=black_fill)

            grand_units += product_units
            grand_base += product_base
            grand_tax += product_tax

        row = add_row(sheet, row, [
            _("TOTAL"), "", invoices.count(),
            round(grand_units, 2), round(grand_base, 2), round(grand_tax, 2), round(grand_base + grand_tax, 2),
        ], font=white_bold_font, fill=black_fill)

        row = jump_row(row)

        iva_titles = [_("Base IVA"), _("% IVA"), _("Núm. de factures"), _("Import IVA"), _("Total")]
        row = add_row(sheet, row, iva_titles, fill=black_fill, font=white_bold_font)

        total_iva_base = 0.0
        total_iva_tax = 0.0
        for item in tax_data:
            base = float(item['base_sum'] or 0)
            tax = float(item['tax_sum'] or 0)
            total_iva_base += base
            total_iva_tax += tax
            row = add_row(sheet, row, [
                round(base, 2),
                f"{item['tax_percent']} %" if item['tax_percent'] is not None else "- %",
                item['count'],
                round(tax, 2),
                round(base + tax, 2),
            ])

        row = add_row(sheet, row, [
            round(total_iva_base, 2), "", "", round(total_iva_tax, 2), round(total_iva_base + total_iva_tax, 2),
        ], font=white_bold_font, fill=black_fill)

        adjust_column_widths(sheet)

        import datetime
        import os
        filename = f"general_billing_summary_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        wb.save(filename)

        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"

        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id)

        os.remove(filename)
        return response, document_id, None
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None
