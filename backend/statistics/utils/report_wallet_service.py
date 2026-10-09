# FOR WALLET REPORTS EXPORTATION
import datetime
import os
from django.db.models import Q, OuterRef, Subquery
from django.http import HttpResponse, JsonResponse
import openpyxl
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils import get_column_letter
from rest_framework.response import Response
from django.core.files.storage import default_storage
from rest_framework import status
from django.utils.translation import gettext as _

from billing.models import Biller, Invoice, InvoiceLineItem, Payment, PaymentRemittance, Reading
from billing.utils.invoice_service import get_invoice_status, get_totals
from billing.utils.payment_service import get_status_map
from billing.utils.sgt_txt_service import generate_sgt_txt_content
from contract.models import Contract, PaymentType
from coredata.models import Bank, ConfigProject, Person
from coredata.utils.address_utils import get_address_complete_without_city
from coredata.utils.iban_validator_utils import get_spanish_bank_code_candidates
from coredata.utils.validators_utils import validate_nif
from service.models import Exploitation
from statistics.views.reports_views import add_row, adjust_column_widths, filter_pending_invoices, jump_row, save_report
from statistics.utils.report_filters import (contract_multi_filter_q, get_billing_ids, get_multi_ids, has_serie_final_range,
                                             invoice_multi_filter_q, payment_multi_filter_q, serie_final_range_invoices,
                                             serie_final_range_period)

def generate_wallet_summary(request, black_fill=None, white_bold_font=None, task=None):
    try:
        print("getting wallet summary")
        #id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        ids = request.data.get('payment_type_ids', None)
        exploitation_id = request.data.get('exploitation_id', None)
        type_id = request.data.get('type_id', None)
        
        if not date_range:
            return Response({"error": "date range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        print("got id or date range")
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        
        if ids:
            payment_type_ids = [int(i) for i in ids.split(',')]
        payment_types_instances = PaymentType.objects.filter(id__in=payment_type_ids) if ids else []
        payment_type_tokens = [payment_type.token for payment_type in payment_types_instances]
        
        paid_status_token = ConfigProject.objects.get(token="payment_status_paid_token").value
        
        start_date = None
        end_date = None
        
        if date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            payments = Payment.objects.filter( 
                                              status__token=paid_status_token, payment_type_token__in=payment_type_tokens
                                              ).filter(
                                                  Q(invoice__issue_date__range=(start_date.date(), end_date.date())) |
                                                  Q(commitment_deposit__invoices__issue_date__range=(start_date.date(), end_date.date())) |
                                                  Q(created_at__range=(start_date.date(), end_date.date()), invoice__isnull=True, commitment_deposit__isnull=True)
                                              )
            if exploitation:
                payment_invoices = payments.filter(invoice__exploitation=exploitation)
                payment_commitment_deposits = payments.filter(commitment_deposit__invoices__exploitation=exploitation)
                payments_none = payments.filter(invoice__isnull=True, commitment_deposit__isnull=True)
                payments = payment_invoices | payment_commitment_deposits | payments_none
            else:
                payments = payments.filter(invoice__exploitation=exploitation)
            multi_q = payment_multi_filter_q(**get_multi_ids(request.data))
            if multi_q:
                payments = payments.filter(multi_q).distinct()
            payments = sorted(payments, key=lambda x: x.payment_date if x.payment_date else datetime.date.max)
        else:
            raise Exception("Error obtaining payments for report wallet summary")


        total_sum = 0
        
        for payment in payments:
            total_sum += float(payment.amount)
        
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("Cartera")
        
        row = 0
        
        title = _("Rebuts %(start)s - %(end)s") % {
            "start": start_date.strftime('%d/%m/%Y'),
            "end": end_date.strftime('%d/%m/%Y'),
        }
        
        main_title = [title]
        row = add_row(sheet, row, main_title)
        sheet.merge_cells(f'A{row}:F{row}')  
        
        row = jump_row(row)
        
        titles = [_("POBLE"), _("REBUT"), _("ABONAT"), _("NOM ABONAT"), _("IMPORT"), _("DATA COBR."), _("DATA F."), _("PAGAMENT")]

        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)
        
        #TODO: ADD LATER TOWN / OFFICE NAME/TOKEN
        total_payments_progress = len(payments)
        for idx_payment, payment in enumerate(payments, start=1):
            if task and idx_payment % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx_payment,
                        'total': total_payments_progress,
                        'percent': round((idx_payment / total_payments_progress) * 100, 2) if total_payments_progress else 0.0
                    }
                )
            print("got payment")
            customer_final = ""
            customer_final_token = ""
            if payment.invoice:
                customer_final = payment.invoice.customer_final
                customer_final_token = payment.invoice.customer_token_final
            elif payment.commitment_deposit:
                customer_final = payment.commitment_deposit.customer_final
                customer_final_token = payment.commitment_deposit.customer_token_final
            payment_row = [
                "00",
                payment.token,
                customer_final_token,
                customer_final,
                payment.amount or 0,
                payment.payment_date.strftime('%d/%m/%Y') if payment.payment_date else "",
                payment.created_at.strftime('%d/%m/%Y') if payment.created_at else "",
                payment.payment_type,
            ]
            row = add_row(sheet, row, payment_row)
        
        totals = [
            _("TOTAL"),
            "",
            f"{len(payments)}",
            "",
            f"{round(total_sum,2)} €",
            "",
            "",
            ""
        ]
        
        row = add_row(sheet, row, totals, fill=black_fill, font=white_bold_font)
        
        total_customers = len(set([payment.invoice.customer_final for payment in payments if payment.invoice]))
        total_customers_row = ["", "", "", "", "", "", _("Total abonats: %(count)s") % {"count": total_customers}, ""]
        row = add_row(sheet, row, total_customers_row)
        sheet.merge_cells(f'G{row}:H{row}')
        for col in range(1, 9):
            cell = sheet.cell(row=row, column=col)
            cell.alignment = Alignment(horizontal='right')
        
        row = jump_row(row)
        row = jump_row(row)
        
        second_title = [_("TOTALS S/ TIPUS DE PAGAMENT")]
        row = add_row(sheet, row, second_title)
        
        payment_types = {}
        payment_type_totals = {}
        payment_type_names = {}
        
        for payment in payments:
            payment_type = payment.payment_type_token
            if payment_type not in payment_types:
                payment_types[payment_type] = 1
                payment_type_totals[payment_type] = float(payment.amount)
                payment_type_names[payment_type] = payment.payment_type
            else:
                payment_types[payment_type] += 1
                payment_type_totals[payment_type] += float(payment.amount)
        
        for payment_type, count in payment_types.items():
            payment_type_row = [
                payment_type_names[payment_type] or _("Altres"),
                _("%(count)s Rebuts") % {"count": count},
                f"{round(payment_type_totals[payment_type],2)} €",
                "",
                "",
                "",
                "",
                ""
            ]
            row = add_row(sheet, row, payment_type_row)
        
        row = jump_row(row)
        
        # Adjust column widths based on content
        adjust_column_widths(sheet)
        
        filename = f"wallet_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id, start_date=start_date, end_date=end_date)
        print("report saved")
        
        os.remove(filename)
        return response, document_id, filename
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def generate_wallet_bank_list(request, black_fill=None, white_bold_font=None, task=None):
    try:
        print("getting wallet bank list summary")
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        
        if not date_range:
            return Response({"error": "date range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        print("got id or date range")
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        
        paid_status_token = ConfigProject.objects.get(token="payment_status_paid_token").value
        payment_type_debit = ConfigProject.objects.get(token="direct_debit_token").value
        
        start_date = None
        end_date = None
        
        if date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            payments = Payment.objects.filter(
                                            status__token=paid_status_token, 
                                            payment_type_token=payment_type_debit
                                            ).filter(
                                                Q(invoice__issue_date__range=(start_date.date(), end_date.date())) |
                                                Q(commitment_deposit__invoices__issue_date__range=(start_date.date(), end_date.date())) |
                                                Q(created_at__range=(start_date.date(), end_date.date()), invoice__isnull=True, commitment_deposit__isnull=True)
                                            )
            if exploitation:
                payment_invoices = payments.filter(invoice__exploitation=exploitation)
                payment_commitment_deposits = payments.filter(commitment_deposit__invoices__exploitation=exploitation)
                payments_none = payments.filter(invoice__isnull=True, commitment_deposit__isnull=True)
                payments = payment_invoices | payment_commitment_deposits | payments_none

            multi_q = payment_multi_filter_q(**get_multi_ids(request.data))
            if multi_q:
                payments = payments.filter(multi_q).distinct()
            payments = sorted(payments, key=lambda x: x.payment_date if x.payment_date else datetime.date.max)
        else:
            raise Exception("Error obtaining payments for report wallet summary")

        # Group payments by bank
        bank_groups = {}
        total_payments_progress = len(payments)
        for idx_payment, payment in enumerate(payments, start=1):
            if task and idx_payment % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx_payment,
                        'total': total_payments_progress,
                        'percent': round((idx_payment / total_payments_progress) * 100, 2) if total_payments_progress else 0.0
                    }
                )
            bank_token = None
            if payment.payment_bank and len(payment.payment_bank) >= 8:
                # Extract bank token (4 digits after country code)
                bank_token = payment.payment_bank[4:8]
            
            if bank_token not in bank_groups:
                bank_groups[bank_token] = {
                    'payments': [],
                    'total': 0,
                    'count': 0,
                    'bank_name': None
                }
                # Try to get bank name from Bank model
                try:
                    bank = Bank.objects.get(token=bank_token)
                    bank_groups[bank_token]['bank_name'] = bank.name
                except Bank.DoesNotExist:
                    pass
            
            bank_groups[bank_token]['payments'].append(payment)
            bank_groups[bank_token]['total'] += float(payment.amount)
            bank_groups[bank_token]['count'] += 1
        
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        
        grand_total = 0
        total_payments = 0
        
        # Create a sheet for each bank
        for bank_token, group_data in bank_groups.items():
            sheet_name = bank_token if bank_token else _("SENSE_BANC")
            sheet = wb.create_sheet(title=sheet_name[:31]) 
            
            row = 0
            
            bank_header = _("BANC: %(bank_token)s") % {"bank_token": bank_token}
            if group_data['bank_name']:
                bank_header += f" - {group_data['bank_name']}"
            
            header = [bank_header]
            row = add_row(sheet, row, header)
            sheet.merge_cells(f'A{row}:F{row}')
            
            row = jump_row(row)
            
            # Add column headers
            titles = [_("REBUT"), _("ABONAT"), _("NOM ABONAT"), _("DOMICILI"), _("COMPTE DOMICILIADA"), _("IMPORT")]
            row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)
            
            # Add payments
            for payment in group_data['payments']:
                address = ""
                if payment.invoice:
                    address = payment.invoice.address_final or ""
                elif payment.commitment_deposit:
                    address = payment.commitment_deposit.address_final or ""
                
                customer_name = ""
                customer_id = ""
                if payment.invoice:
                    customer_name = payment.invoice.customer_final
                    customer_id = payment.invoice.customer_token_final
                elif payment.commitment_deposit:
                    customer_name = payment.commitment_deposit.customer_final
                    customer_id = payment.commitment_deposit.customer_token_final
                
                payment_row = [
                    payment.token,  
                    customer_id,  
                    customer_name,  
                    address,  
                    payment.payment_bank,  
                    payment.amount  
                ]
                row = add_row(sheet, row, payment_row)
            
            # Add bank totals
            row = jump_row(row)
            totals = [
                "",
                "",
                "",
                "",
                _("TOTAL REBUTS: %(count)s") % {"count": group_data['count']},
                _("TOTAL EUROS: %(amount)s €") % {"amount": round(group_data['total'], 2)}
            ]
            row = add_row(sheet, row, totals, fill=black_fill, font=white_bold_font)
            
            # Adjust column widths
            adjust_column_widths(sheet)
            
            grand_total += group_data['total']
            total_payments += group_data['count']
        
        # Create summary sheet
        summary = wb.create_sheet(title=_('RESUM'), index=0)
        row = 0
        
        title = _("Rebuts %(start)s - %(end)s") % {
            "start": start_date.strftime('%d/%m/%Y'),
            "end": end_date.strftime('%d/%m/%Y'),
        }
        row = add_row(summary, row, [title])
        summary.merge_cells(f'A{row}:D{row}')
        
        row = jump_row(row)
        
        # Add summary headers
        headers = [_("BANC"), _("NOM"), _("REBUTS"), _("IMPORT")]
        row = add_row(summary, row, headers, fill=black_fill, font=white_bold_font)
        
        # Add bank summaries
        for bank_token, group_data in bank_groups.items():
            bank_row = [
                bank_token,
                group_data['bank_name'] or "",
                str(group_data['count']),
                f"{round(group_data['total'], 2)} €"
            ]
            row = add_row(summary, row, bank_row)
        
        # Add grand totals
        row = jump_row(row)
        grand_totals = [
            _("TOTALS"),
            "",
            str(total_payments),
            f"{round(grand_total, 2)} €"
        ]
        row = add_row(summary, row, grand_totals, fill=black_fill, font=white_bold_font)
        summary.merge_cells(f'E{row}:F{row}')  
        # Adjust summary column widths
        adjust_column_widths(summary)
        
        filename = f"wallet_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id, start_date=start_date, end_date=end_date)
        print("report saved")
        
        os.remove(filename)
        return response, document_id, filename
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None


def generate_wallet_bank_summary(request, black_fill=None, white_bold_font=None, task=None):
    try:
        print("getting wallet bank summary summary")
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        if not date_range:
            return Response({"error": "date range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        print("got id or date range")
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        
        paid_status_token = ConfigProject.objects.get(token="payment_status_paid_token").value
        payment_type_debit = ConfigProject.objects.get(token="direct_debit_token").value
        print("check")
        start_date = None
        end_date = None
        
        if date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            payments = Payment.objects.filter(
                                            #status__token=paid_status_token, 
                                            payment_type_token=payment_type_debit
                                            ).filter(
                                                Q(invoice__issue_date__range=(start_date.date(), end_date.date())) |
                                                Q(commitment_deposit__invoices__issue_date__range=(start_date.date(), end_date.date())) |
                                                Q(created_at__range=(start_date.date(), end_date.date()), invoice__isnull=True, commitment_deposit__isnull=True)
                                            )
            print("check 2")
            print(payments)
            if exploitation:
                payments = payments.filter(
                    Q(invoice__exploitation=exploitation) | 
                    Q(commitment_deposit__invoices__exploitation=exploitation) |
                    Q(invoice__isnull=True, commitment_deposit__isnull=True)
                    )
            multi_q = payment_multi_filter_q(**get_multi_ids(request.data))
            if multi_q:
                payments = payments.filter(multi_q).distinct()
            print("payments before sorting", payments)
            payments = sorted(payments, key=lambda x: x.payment_date if x.payment_date else datetime.date.max)
            print("check 3")
        else:
            raise Exception("Error obtaining payments for report wallet summary")
        print("got payments")
        print(payments)
        bank_groups = {}
        #TODO: LATER ADD DIFFERENT CHECK DEPENDING ON COUNTRY (IF NOT ES, CODE COULD BE MORE/LESS THAN 4 DIGITS)
        total_payments_progress = len(payments)
        for idx_payment, payment in enumerate(payments, start=1):
            if task and idx_payment % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx_payment,
                        'total': total_payments_progress,
                        'percent': round((idx_payment / total_payments_progress) * 100, 2) if total_payments_progress else 0.0
                    }
                )
            bank_token = None
            if payment.payment_bank and len(payment.payment_bank) >= 8:
                bank_token = payment.payment_bank[4:8]
            
            if bank_token not in bank_groups:
                bank_groups[bank_token] = {
                    'payments': [],
                    'total': 0,
                    'count': 0,
                    'bank_name': None
                }
                try:
                    bank = Bank.objects.get(token=bank_token)
                    bank_groups[bank_token]['bank_name'] = bank.name
                except Bank.DoesNotExist:
                    pass
            
            bank_groups[bank_token]['payments'].append(payment)
            bank_groups[bank_token]['total'] += float(payment.amount)
            bank_groups[bank_token]['count'] += 1
        
        wb = openpyxl.Workbook()
        summary = wb.active
        summary.title = _("Resum rebuts")
        
        grand_total = 0
        total_payments = 0
        row = 0
        
        title = _("Rebuts %(start)s - %(end)s") % {
            "start": start_date.strftime('%d/%m/%Y'),
            "end": end_date.strftime('%d/%m/%Y'),
        }
        row = add_row(summary, row, [title])
        summary.merge_cells(f'A{row}:D{row}')
        
        row = jump_row(row)
        
        headers = [_("BANC"), _("NOM"), _("REBUTS"), _("IMPORT")]
        row = add_row(summary, row, headers, fill=black_fill, font=white_bold_font)
        
        for bank_token, group_data in bank_groups.items():
            bank_row = [
                bank_token,
                group_data['bank_name'] or "",
                str(group_data['count']),
                f"{round(group_data['total'], 2)} €"
            ]
            row = add_row(summary, row, bank_row)
        
        row = jump_row(row)
        grand_totals = [
            _("TOTALS"),
            "",
            str(total_payments),
            f"{round(grand_total, 2)} €"
        ]
        row = add_row(summary, row, grand_totals, fill=black_fill, font=white_bold_font)
        summary.merge_cells(f'E{row}:F{row}')  
        # Adjust summary column widths
        for col in range(1, summary.max_column + 1):
            max_length = 0
            column = get_column_letter(col)
            
            for cell in summary[column]:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = (max_length + 2)
            summary.column_dimensions[column].width = adjusted_width
        
        adjust_column_widths(summary)
        
        filename = f"wallet_debit_summ_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id, start_date=start_date, end_date=end_date)
        print("report saved")
        
        os.remove(filename)
        return response, document_id, filename
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def generate_wallet_bank_detailed_summary(request, black_fill=None, white_bold_font=None, task=None):
    try:
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        if not date_range:
            return Response({"error": "date range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
            
        paid_status_token = ConfigProject.objects.get(token="payment_status_paid_token").value
        payment_type_debit = ConfigProject.objects.get(token="direct_debit_token").value
        
        start_date = None
        end_date = None
        
        if date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            payments = Payment.objects.filter(payment_date__range=(start_date.date(), end_date.date()), 
                                            #status__token=paid_status_token, 
                                            payment_type_token=payment_type_debit)
            if exploitation:
                payment_invoices = payments.filter(invoice__exploitation=exploitation)
                payment_commitment_deposits = payments.filter(commitment_deposit__invoices__exploitation=exploitation)
                payments_none = payments.filter(invoice__isnull=True, commitment_deposit__isnull=True)
                payments = payment_invoices | payment_commitment_deposits | payments_none
            multi_q = payment_multi_filter_q(**get_multi_ids(request.data))
            if multi_q:
                payments = payments.filter(multi_q).distinct()
            payments = sorted(payments, key=lambda x: x.payment_date if x.payment_date else datetime.date.max)
        else:
            raise Exception("Error obtaining payments for report wallet summary")

        wb = openpyxl.Workbook()
        summary = wb.active
        summary.title = _("Resum rebuts")

        grand_total = sum(float(payment.amount or 0) for payment in payments)
        total_payments = len(payments)
        row = 0

        title = _("Rebuts %(start)s - %(end)s") % {
            "start": start_date.strftime('%d/%m/%Y'),
            "end": end_date.strftime('%d/%m/%Y'),
        }
        row = add_row(summary, row, [title])
        summary.merge_cells(f'A{row}:D{row}')

        row = jump_row(row)

        headers = [_("REMESA"), _("FECHA REGISTRO"), _("BANCO"), _("CIF"), _("FACTURA"), _("FECHA VENCIMIENTO"), _("IMPORTE FACTURA"), _("IMPORTE TOTAL REMESA")]
        row = add_row(summary, row, headers, fill=black_fill, font=white_bold_font)
        
        #TODO: LATER WORK WITH OTHER COUNTRIES
        for idx_payment, payment in enumerate(payments, start=1):
            if task and idx_payment % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx_payment,
                        'total': total_payments,
                        'percent': round((idx_payment / total_payments) * 100, 2) if total_payments else 0.0
                    }
                )
            bank = None
            bank_token = None
            bank_name = ""
            bank_country = None
            
            remittance = None
            remittance_token = ""
            invoice = None
            if payment.invoice:
                invoice = payment.invoice
            elif payment.commitment_deposit:
                invoice = payment.commitment_deposit.invoices.first()
            
            invoice_amount = 0
            if invoice:
                invoice_amount = invoice.left_to_pay
            elif payment.amount:
                invoice_amount = payment.amount
            
            try:
                remittance = PaymentRemittance.objects.filter(payments=payment, sent_at__isnull=False).order_by('-sent_at').first()
                if remittance:
                    remittance_token = remittance.token
            except Exception as e:
                print(f"Error getting remittance {payment.token}: {e}")
                pass
            
            if payment.payment_bank and len(payment.payment_bank) >= 8:
                bank_country = payment.payment_bank[0:2]
                if bank_country == "ES":
                    bank_token = payment.payment_bank[4:8]
                    
            if bank_token:
                try:
                    bank = Bank.objects.get(token=bank_token)
                    bank_name = bank.name
                except Exception as e:
                    bank = None
                    bank_name = ""
                    pass
            if not bank:
                try:
                    bank = Bank.objects.get(token=str(int(bank_token)))
                    bank_name = bank.name
                except Exception as e:
                    bank = None
                    bank_name = ""
                    pass
            
            bank_title = f"{bank_token}" if bank_token else ""
            if bank_name and bank_name != "":
                bank_title += f" ({bank_name})"
            invoice_serie = invoice.serie_final.upper() if invoice else ""
            
            row_data = [
                remittance_token, payment.payment_date.strftime('%d-%m-%Y') if payment.payment_date else "", 
                bank_title, payment.customer_token_final or "",
                invoice_serie, payment.due_date.strftime('%d-%m-%Y') if payment.due_date else "",
                invoice_amount, payment.amount or 0
            ]
            colored =  [i for i in range(0, len(row_data) + 1) if i % 2 == 0]
            row = add_row(summary, row, row_data, colored=colored)
        
        row = jump_row(row)
        grand_totals = [
            _("TOTALS"),
            str(total_payments),
            "", "", "", "", "",
            f"{round(grand_total, 2)} €"
        ]
        row = add_row(summary, row, grand_totals, fill=black_fill, font=white_bold_font)
        #summary.merge_cells(f'E{row}:F{row}')  
        # Adjust summary column widths
        for col in range(1, summary.max_column + 1):
            max_length = 0
            column = get_column_letter(col)
            
            for cell in summary[column]:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = (max_length + 2)
            summary.column_dimensions[column].width = adjusted_width
        
        adjust_column_widths(summary)
        
        filename = f"wallet_debit_summ_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id, start_date=start_date, end_date=end_date)
        print("report saved")
        
        os.remove(filename)
        return response, document_id, filename
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def generate_wallet_cash_detailed_summary(request, black_fill=None, white_bold_font=None, task=None):
    try:
        print("generate wallet cash detailed summary")
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        if not date_range:
            return Response({"error": "date range is required."}, status=status.HTTP_400_BAD_REQUEST), None, None
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        
        paid_status_token = ConfigProject.objects.get(token="payment_status_paid_token").value
        payment_type_debit = ConfigProject.objects.get(token="direct_debit_token").value
        
        start_date = None
        end_date = None
        if date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            payments = Payment.objects.filter(
                                            status__token=paid_status_token
                                            ).exclude(
                                                payment_type_token=payment_type_debit
                                            ).filter(
                                                Q(paid_at__range=(start_date.date(), end_date.date()))
                                            )

            print("payments", payments)

            if exploitation:
                payments = payments.filter(Q(invoice__exploitation=exploitation) | Q(commitment_deposit__invoices__exploitation=exploitation) | Q(invoice__isnull=True, commitment_deposit__isnull=True))
            multi_q = payment_multi_filter_q(**get_multi_ids(request.data))
            if multi_q:
                payments = payments.filter(multi_q).distinct()
            payments = sorted(payments, key=lambda x: x.payment_date if x.payment_date else datetime.date.max)
        else:
            raise Exception("Error obtaining payments for report wallet summary")
        wb = openpyxl.Workbook()
        summary = wb.active
        summary.title = _("Resumen cobros")
        
        grand_total = sum(float(payment.amount) for payment in payments)
        total_payments = len(payments)
        row = 0
        
        title = _("Cobros %(start)s - %(end)s") % {
            "start": start_date.strftime('%d/%m/%Y'),
            "end": end_date.strftime('%d/%m/%Y'),
        }
        row = add_row(summary, row, [title])
        summary.merge_cells(f'A{row}:D{row}')
        
        row = jump_row(row)
        
        headers = [_("FECHA COBRO"), _("CIF"), _("FACTURA"), _("IMPORTE COBRADO")]
        row = add_row(summary, row, headers, fill=black_fill, font=white_bold_font)
        #TODO: LATER WORK WITH OTHER COUNTRIES
        for idx_payment, payment in enumerate(payments, start=1):
            if task and idx_payment % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': idx_payment,
                        'total': total_payments,
                        'percent': round((idx_payment / total_payments) * 100, 2) if total_payments else 0.0
                    }
                )
            invoice_serie = payment.invoice.serie_final.upper() if payment.invoice else payment.commitment_deposit.token if payment.commitment_deposit else ""
            row_data = [
                payment.payment_date.strftime('%d-%m-%Y') if payment.payment_date else "", 
                payment.customer_token_final,
                invoice_serie, payment.amount
            ]
            colored =  [i for i in range(0, len(row_data) + 1) if i % 2 == 0]
            row = add_row(summary, row, row_data, colored=colored)
        row = jump_row(row)
        grand_totals = [
            _("TOTALES"),
            str(total_payments), "",
            f"{round(grand_total, 2)} €"
        ]
        row = add_row(summary, row, grand_totals, fill=black_fill, font=white_bold_font)
        #summary.merge_cells(f'E{row}:F{row}')  
        # Adjust summary column widths
        for col in range(1, summary.max_column + 1):
            max_length = 0
            column = get_column_letter(col)
            
            for cell in summary[column]:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            
            adjusted_width = (max_length + 2)
            summary.column_dimensions[column].width = adjusted_width
        
        adjust_column_widths(summary)
        filename = f"wallet_debit_summ_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id, start_date=start_date, end_date=end_date)
        print("report saved")
        
        os.remove(filename)
        return response, document_id, filename
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None

def _build_unpaid_excel(payments, start_date, end_date, filename, name, type_id, black_fill, white_bold_font, returned_status_token, task=None):
    wb = openpyxl.Workbook()
    
    # --- PESTANYA 1: RESUM ---
    summary = wb.active
    summary.title = _("Resumen recibos")
    
    grand_total = sum(float(payment.amount or 0) for payment in payments)
    total_payments = len(payments)
    row = 0
    
    title = _("Recibos %(start)s - %(end)s") % {
        "start": start_date.strftime('%d/%m/%Y'),
        "end": end_date.strftime('%d/%m/%Y'),
    }
    row = add_row(summary, row, [title])
    summary.merge_cells(f'A{row}:F{row}')

    row = jump_row(row)

    headers = [
        _("REMESA"),
        _("FECHA DEVOLUCIÓN"),
        _("BANCO EMPRESA"),
        _("CIF"),
        _("FACTURA"),
        _("IMPORTE FACTURA"),
    ]
    row = add_row(summary, row, headers, fill=black_fill, font=white_bold_font)

    for idx_payment, payment in enumerate(payments, start=1):
        if task and idx_payment % 50 == 0:
            task.update_state(
                state='PROGRESS',
                meta={
                    'current': idx_payment,
                    'total': total_payments,
                    'percent': round((idx_payment / total_payments) * 100, 2) if total_payments else 0.0
                }
            )
        company_bank = None
        company_bank_token = None
        company_bank_name = ""
        
        remittance = None
        remittance_token = ""
        invoice_amount = payment.invoice.total_final if payment.invoice else (payment.amount or 0)
        try:
            remittances = PaymentRemittance.objects.filter(payments=payment, sent_at__isnull=False).order_by('-sent_at')
            if remittances.exists():
                remittance = remittances.first()
                remittance_token = remittance.token
                company_bank = remittance.company_bank
            else:
                remittance_token = ""
        except Exception:
            pass

        if company_bank and company_bank.bank:
            company_bank_token = company_bank.bank.token
            company_bank_name = company_bank.bank.name or ""
        elif company_bank and company_bank.iban and len(company_bank.iban) >= 8:
            company_bank_country = company_bank.iban[0:2]
            if company_bank_country == "ES":
                company_bank_token = company_bank.iban[4:8]
                bank_company = Bank.objects.filter(token__in=get_spanish_bank_code_candidates(company_bank_token)).first()
                if bank_company:
                    company_bank_name = bank_company.name
                    company_bank_token = bank_company.token
                else:
                    company_bank_name = ""

        company_bank_title = f"{company_bank_token}" if company_bank_token else ""
        if company_bank_name and company_bank_name != "":
            company_bank_title += f" ({company_bank_name})"

        invoice_serie = payment.invoice.serie_final.upper() if payment.invoice else (payment.commitment_deposit.token if payment.commitment_deposit else "")
        reject_date = (
            payment.reject_date.strftime('%d-%m-%Y')
            if payment.status
            and payment.status.token == returned_status_token
            and payment.reject_date
            else ""
        )
        row_data = [
            remittance_token,
            reject_date,
            company_bank_title,
            payment.customer_token_final or "",
            invoice_serie, invoice_amount
        ]
        colored = [i for i in range(0, len(row_data) + 1) if i % 2 == 0]
        row = add_row(summary, row, row_data, colored=colored)

    row = jump_row(row)
    grand_totals = [
        _("TOTALS"),
        "",
        "",
        str(total_payments),
        "",
        f"{round(grand_total, 2)} €"
    ]
    row = add_row(summary, row, grand_totals, fill=black_fill, font=white_bold_font)
    
    for col in range(1, summary.max_column + 1):
        max_length = 0
        column = get_column_letter(col)
        for cell in summary[column]:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        summary.column_dimensions[column].width = adjusted_width
    
    adjust_column_widths(summary)
    
    # --- PESTANYA 2: DETALLAT ---
    detailed = wb.create_sheet(title=_("Detalle recibos"))
    row = 0
    row = add_row(detailed, row, [title])
    
    headers_det = [
        _("REMESA"),
        _("FECHA DEVOLUCIÓN"),
        _("BANCO EMPRESA"),
        _("CIF"),
        _("FACTURA"),
        _("IMPORTE FACTURA"),
        _("MOTIVO DEVOLUCIÓN"),
        _("BANCO CLIENTE"),
        _("CONTRATO"),
        _("CONTADOR"),
        _("DIRECCIÓN SUMINISTRO"),
        _("NOM TITULAR"),
        _("VIA DE COMUNICACIÓ"),
        _("VALOR VIA DE COMUNICACIÓ"),
    ]
    last_col = get_column_letter(len(headers_det))
    detailed.merge_cells(f"A{row}:{last_col}{row}")
    
    row = jump_row(row)
    row = add_row(detailed, row, headers_det, fill=black_fill, font=white_bold_font)
    
    for payment in payments:
        company_bank = None
        company_bank_token = None
        company_bank_name = ""
        
        remittance = None
        remittance_token = ""
        invoice_amount = payment.invoice.total_final if payment.invoice else (payment.amount or 0)
        try:
            remittances = PaymentRemittance.objects.filter(payments=payment, sent_at__isnull=False).order_by('-sent_at')
            if remittances.exists():
                remittance = remittances.first()
                remittance_token = remittance.token
                company_bank = remittance.company_bank
            else:
                remittance_token = ""
        except Exception:
            pass

        if company_bank and company_bank.bank:
            company_bank_token = company_bank.bank.token
            company_bank_name = company_bank.bank.name or ""
        elif company_bank and company_bank.iban and len(company_bank.iban) >= 8:
            company_bank_country = company_bank.iban[0:2]
            if company_bank_country == "ES":
                company_bank_token = company_bank.iban[4:8]
                bank_company = Bank.objects.filter(token__in=get_spanish_bank_code_candidates(company_bank_token)).first()
                if bank_company:
                    company_bank_name = bank_company.name
                    company_bank_token = bank_company.token
                else:
                    company_bank_name = ""

        company_bank_title = f"{company_bank_token}" if company_bank_token else ""
        if company_bank_name and company_bank_name != "":
            company_bank_title += f" ({company_bank_name})"

        invoice_serie = payment.invoice.serie_final.upper() if payment.invoice else (payment.commitment_deposit.token if payment.commitment_deposit else "")
        reject_date = (
            payment.reject_date.strftime('%d-%m-%Y')
            if payment.status
            and payment.status.token == returned_status_token
            and payment.reject_date
            else ""
        )
        contract = _wallet_payment_contract(payment)
        contract_token = contract.token if contract else ""
        meter_token = _wallet_supply_meter_token(contract)
        supply_address = _wallet_supply_address(contract)
        row_data = [
            remittance_token,
            reject_date,
            company_bank_title,
            payment.customer_token_final or "",
            invoice_serie, invoice_amount,
            _wallet_reject_reason(payment),
            _wallet_client_bank_label(payment),
            contract_token,
            meter_token,
            supply_address,
            _wallet_holder_name(contract),
            _wallet_communication_type(contract),
            _wallet_communication_value(contract),
        ]
        colored = [i for i in range(0, len(row_data) + 1) if i % 2 == 0]
        row = add_row(detailed, row, row_data, colored=colored)

    row = jump_row(row)
    grand_totals_det = [
        _("TOTALS"),
        "",
        "",
        "",
        str(total_payments),
        f"{round(grand_total, 2)} €",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    ]
    row = add_row(detailed, row, grand_totals_det, fill=black_fill, font=white_bold_font)
    
    for col in range(1, detailed.max_column + 1):
        max_length = 0
        column = get_column_letter(col)
        for cell in detailed[column]:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        detailed.column_dimensions[column].width = adjusted_width
        
    adjust_column_widths(detailed)
    
    wb.save(filename)

    with open(filename, "rb") as f:
        response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f"attachment; filename={filename}"
    
    document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id, start_date=start_date, end_date=end_date)
    print("report saved")
    
    os.remove(filename)
    return response, document_id, filename


def generate_wallet_unpaid_summary(request, black_fill=None, white_bold_font=None, task=None):
    return generate_wallet_unpaid_detailed_summary(request, black_fill, white_bold_font, task=task)

def _wallet_payment_contract(payment):
    """Contract linked to invoice, commitment deposit, or payment directly."""
    if payment.invoice_id and payment.invoice and payment.invoice.contract_id:
        return payment.invoice.contract
    if payment.commitment_deposit_id and payment.commitment_deposit and payment.commitment_deposit.contract_id:
        return payment.commitment_deposit.contract
    return payment.contract


def _wallet_supply_address(contract):
    if not contract or not contract.supply_point_default_id or not contract.supply_point_default:
        return ""
    addr = contract.supply_point_default.address
    if not addr:
        return ""
    return str(addr)


def _wallet_supply_meter_token(contract):
    if not contract or not contract.supply_point_default_id or not contract.supply_point_default:
        return ""
    meter = contract.supply_point_default.meter
    if not meter:
        return ""
    return meter.token or ""


def _wallet_client_bank_label(payment):
    bank = (payment.payment_bank or "").strip()
    swift = (payment.payment_swift or "").strip()
    if bank and swift:
        return f"{bank} / {swift}"
    return bank or swift or ""


def _wallet_reject_reason(payment):
    if not payment.reject_id or not payment.reject:
        return ""
    return (payment.reject.name or "").strip() or (payment.reject.description or "").strip()


def _wallet_holder_name(contract):
    if not contract or not contract.holder:
        return ""
    holder = contract.holder
    if hasattr(holder, 'full_name') and holder.full_name:
        return holder.full_name
    parts = [getattr(holder, 'name', '') or "", getattr(holder, 'surname', '') or ""]
    return " ".join(p for p in parts if p).strip()


def _wallet_communication_type(contract):
    if not contract:
        return ""
    comm = getattr(contract, 'communication_type', None) or ""
    if comm in ('DIGITAL', 'BOTH'):
        return "Email"
    if comm in ('PAPER', 'PHYSICAL'):
        return "Postal"
    return comm


def _wallet_communication_value(contract):
    if not contract:
        return ""
    comm = getattr(contract, 'communication_type', None) or ""
    if comm in ('DIGITAL', 'BOTH'):
        try:
            contact = contract.person_contact_email
            return (contact.email or "") if contact else ""
        except Exception:
            return ""
    if comm in ('PAPER', 'PHYSICAL'):
        return _wallet_supply_address(contract)
    return ""


def generate_wallet_unpaid_detailed_summary(request, black_fill=None, white_bold_font=None, task=None):
    try:
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        remittance_id = request.data.get('remittance_id') or request.data.get('id')
        multi_ids = get_multi_ids(request.data)
        remittance_ids = multi_ids.pop('remittance_ids', [])

        if not date_range and not remittance_id and not remittance_ids:
            return Response({"error": "date range or remittance id is required."}, status=status.HTTP_400_BAD_REQUEST), None, None

        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)

        unpaid_status_token = ConfigProject.objects.get(token="payment_status_expired_token").value
        endowment_status_token = ConfigProject.objects.get(token="payment_status_endowment_token").value
        payment_type_debit = ConfigProject.objects.get(token="direct_debit_token").value
        returned_status_token = ConfigProject.objects.get(token="payment_status_returned_token").value

        start_date = None
        end_date = None

        if date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            payments_qs = Payment.objects.filter(
                Q(reject_date__range=(start_date.date(), end_date.date())) |
                Q(commitment_deposit__invoices__issue_date__range=(start_date.date(), end_date.date())) |
                Q(created_at__range=(start_date.date(), end_date.date()), invoice__isnull=True, commitment_deposit__isnull=True)
            )
        elif remittance_id:
            try:
                remittance = PaymentRemittance.objects.get(id=remittance_id)
            except PaymentRemittance.DoesNotExist:
                return Response({"error": "remittance not found."}, status=status.HTTP_400_BAD_REQUEST), None, None

            ref_date = remittance.sent_at or remittance.desired_send_at or (remittance.created_at.date() if remittance.created_at else datetime.date.today())
            if isinstance(ref_date, datetime.datetime):
                ref_date = ref_date.date()
            start_date = datetime.datetime.combine(ref_date, datetime.time.min)
            end_date = datetime.datetime.combine(ref_date, datetime.time.max)
            payments_qs = Payment.objects.filter(remittances=remittance)
        elif remittance_ids:
            remittances_qs = PaymentRemittance.objects.filter(id__in=remittance_ids)
            remittance = remittances_qs.order_by('-sent_at').first()
            ref_date = None
            if remittance:
                ref_date = remittance.sent_at or remittance.desired_send_at or (remittance.created_at.date() if remittance.created_at else datetime.date.today())
            if not ref_date:
                ref_date = datetime.date.today()
            if isinstance(ref_date, datetime.datetime):
                ref_date = ref_date.date()
            start_date = datetime.datetime.combine(ref_date, datetime.time.min)
            end_date = datetime.datetime.combine(ref_date, datetime.time.max)
            payments_qs = Payment.objects.filter(remittances__in=remittances_qs).distinct()
        else:
            raise Exception("Error obtaining payments for report wallet summary")

        multi_q = payment_multi_filter_q(**multi_ids)
        if multi_q:
            payments_qs = payments_qs.filter(multi_q).distinct()

        payments_qs = payments_qs.filter(
            status__token__in=[unpaid_status_token, endowment_status_token, returned_status_token],
            payment_type_token=payment_type_debit
        ).exclude(
            commitment_deposit__status__token='-1'
        ).select_related(
            "invoice__contract__supply_point_default__address",
            "invoice__contract__supply_point_default__meter",
            "invoice__contract__holder",
            "invoice__contract__person_contact_email",
            "commitment_deposit__contract__supply_point_default__address",
            "commitment_deposit__contract__supply_point_default__meter",
            "commitment_deposit__contract__holder",
            "commitment_deposit__contract__person_contact_email",
            "contract__supply_point_default__address",
            "contract__supply_point_default__meter",
            "contract__holder",
            "contract__person_contact_email",
            "reject",
            "status",
        )
        if exploitation:
            payments_qs = payments_qs.filter(Q(invoice__exploitation=exploitation) | Q(commitment_deposit__invoices__exploitation=exploitation) | Q(invoice__isnull=True, commitment_deposit__isnull=True))
        payments = sorted(
            list(payments_qs),
            key=lambda x: x.payment_date if x.payment_date else datetime.date.max,
        )
        
        filename = f"{_('retorn_sepa')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return _build_unpaid_excel(payments, start_date, end_date, filename, name, type_id, black_fill, white_bold_font, returned_status_token, task=task)
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None


def generate_wallet_all_unpaid_summary(request, black_fill=None, white_bold_font=None, task=None):
    try:
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        remittance_id = request.data.get('remittance_id') or request.data.get('id')
        multi_ids = get_multi_ids(request.data)
        remittance_ids = multi_ids.pop('remittance_ids', [])

        if not date_range and not remittance_id and not remittance_ids:
            return Response({"error": "date range or remittance id is required."}, status=status.HTTP_400_BAD_REQUEST), None, None

        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)

        unpaid_status_token = ConfigProject.objects.get(token="payment_status_expired_token").value
        endowment_status_token = ConfigProject.objects.get(token="payment_status_endowment_token").value
        returned_status_token = ConfigProject.objects.get(token="payment_status_returned_token").value

        start_date = None
        end_date = None

        if date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            payments_qs = Payment.objects.filter(
                Q(reject_date__range=(start_date.date(), end_date.date())) |
                Q(commitment_deposit__invoices__issue_date__range=(start_date.date(), end_date.date())) |
                Q(created_at__range=(start_date.date(), end_date.date()), invoice__isnull=True, commitment_deposit__isnull=True) |
                Q(reject_date__isnull=True, updated_at__date__range=(start_date.date(), end_date.date()))
            )
        elif remittance_id:
            try:
                remittance = PaymentRemittance.objects.get(id=remittance_id)
            except PaymentRemittance.DoesNotExist:
                return Response({"error": "remittance not found."}, status=status.HTTP_400_BAD_REQUEST), None, None

            ref_date = remittance.sent_at or remittance.desired_send_at or (remittance.created_at.date() if remittance.created_at else datetime.date.today())
            if isinstance(ref_date, datetime.datetime):
                ref_date = ref_date.date()
            start_date = datetime.datetime.combine(ref_date, datetime.time.min)
            end_date = datetime.datetime.combine(ref_date, datetime.time.max)
            payments_qs = Payment.objects.filter(remittances=remittance)
        elif remittance_ids:
            remittances_qs = PaymentRemittance.objects.filter(id__in=remittance_ids)
            remittance = remittances_qs.order_by('-sent_at').first()
            ref_date = None
            if remittance:
                ref_date = remittance.sent_at or remittance.desired_send_at or (remittance.created_at.date() if remittance.created_at else datetime.date.today())
            if not ref_date:
                ref_date = datetime.date.today()
            if isinstance(ref_date, datetime.datetime):
                ref_date = ref_date.date()
            start_date = datetime.datetime.combine(ref_date, datetime.time.min)
            end_date = datetime.datetime.combine(ref_date, datetime.time.max)
            payments_qs = Payment.objects.filter(remittances__in=remittances_qs).distinct()
        else:
            raise Exception("Error obtaining payments for report wallet summary")

        multi_q = payment_multi_filter_q(**multi_ids)
        if multi_q:
            payments_qs = payments_qs.filter(multi_q).distinct()

        payments_qs = payments_qs.filter(
            status__token__in=[unpaid_status_token, endowment_status_token, returned_status_token]
        ).exclude(
            commitment_deposit__status__token='-1'
        ).select_related(
            "invoice__contract__supply_point_default__address",
            "invoice__contract__supply_point_default__meter",
            "invoice__contract__holder",
            "invoice__contract__person_contact_email",
            "commitment_deposit__contract__supply_point_default__address",
            "commitment_deposit__contract__supply_point_default__meter",
            "commitment_deposit__contract__holder",
            "commitment_deposit__contract__person_contact_email",
            "contract__supply_point_default__address",
            "contract__supply_point_default__meter",
            "contract__holder",
            "contract__person_contact_email",
            "reject",
            "status",
        )
        if exploitation:
            payments_qs = payments_qs.filter(Q(invoice__exploitation=exploitation) | Q(commitment_deposit__invoices__exploitation=exploitation) | Q(invoice__isnull=True, commitment_deposit__isnull=True))
        payments = sorted(
            list(payments_qs),
            key=lambda x: x.payment_date if x.payment_date else datetime.date.max,
        )
            
        filename = f"{_('all_unpaid')}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return _build_unpaid_excel(payments, start_date, end_date, filename, name, type_id, black_fill, white_bold_font, returned_status_token, task=task)
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None
    
def generate_pending_invoices_person_summary(request, black_fill=None, white_bold_font=None):
    try:
        person_id = request.data.get('person_id', None)
        
        if person_id:
            person = Person.objects.get(id=person_id)
        else:
            raise Exception("Error obtaining person for report pending invoices person summary")
        
        wb = openpyxl.Workbook()
        sheet = wb.active
        sheet.title = _("Factures pendents de %(name)s %(surname)s") % {"name": person.name, "surname": person.surname}
        
        row = 0
        titles = [_("Núm factura"), _("Contracte"), _("Adreça subm."), _("Total factura"), _("Total pendent"), _("Data factura")]
        row = add_row(sheet, row, titles, fill=black_fill, font=white_bold_font)
        
        invoices = Invoice.objects.filter(
            status__token__in=["-1", "2"],
        ).filter(
            Q(customer_token_final=person.token) | Q(payer_token_final=person.token)
        )

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        for inv in invoices:
            invoice_row = [
                inv.serie_final,
                inv.contract.token,
                str(inv.contract.supply_point_default.address),
                inv.total_final,
                inv.left_to_pay,
                inv.issue_date.strftime('%d/%m/%Y') if inv.issue_date else "",
            ]
            row = add_row(sheet, row, invoice_row)
        
        adjust_column_widths(sheet)
        
        filename = f"{person.token}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        document_id = save_report(content=wb, filename=filename, name=filename.split('.')[0], type_id=None)
        
        os.remove(filename)
        return response, document_id, None
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None
    
    

def generate_total_customers_debt_summary(request, black_fill=None, white_bold_font=None, task=None):
    try:
        id = request.data.get('id', None)
        date_range = request.data.get('date_range', None)
        name = request.data.get('name', '')
        type_id = request.data.get('type_id', None)
        exploitation_id = request.data.get('exploitation_id', None)
        name = request.data.get('name', '')
        
        start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
        end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            
        cutoff_date = end_date.date()
        
        payment_paid_token = ConfigProject.objects.get(token="payment_status_paid_token").value
        payment_status_returned_token = ConfigProject.objects.get(token="payment_status_returned_token").value
        payment_status_pending_token = ConfigProject.objects.get(token="payment_status_pending_token").value
        payment_status_expired_token = ConfigProject.objects.get(token="payment_status_expired_token").value
        payment_status_endowment_token = ConfigProject.objects.get(token="payment_status_endowment_token").value
        payment_status_irrecoverable_token = ConfigProject.objects.get(token="payment_status_irrecoverable_token").value
        
        invoice_type_invoice_token = ConfigProject.objects.get(token="invoice_type_invoice_token").value
        
        invoice_payoff_token = ConfigProject.objects.get(token="invoice_status_payoff_token").value
        invoice_pending_token = ConfigProject.objects.get(token="invoice_status_pending_token").value
        invoice_cancelled_token = ConfigProject.objects.get(token="invoice_status_cancelled_token").value
        payment_balance_token = ConfigProject.objects.get(token="payment_status_piggy_token").value
        
        invoices = (
            Invoice.objects.filter(
                type_final=invoice_type_invoice_token,
                issue_date__lte=cutoff_date,
            ).exclude(
                status__token__in=[invoice_payoff_token,invoice_pending_token]
            ).exclude(
                payments__status__token=payment_balance_token
            ).filter(
                Q(payments__payment_date__gt=cutoff_date, payments__status__token=payment_paid_token) | 
                Q(payments__status__token__in=[
                    payment_status_returned_token, payment_status_pending_token,
                    payment_status_expired_token, payment_status_endowment_token, 
                    payment_status_irrecoverable_token])
            )
        )

        print("invoices: ", invoices.count())
        invoices = invoices.annotate(
            return_invoice_issue_date=Subquery(
                Invoice.objects.filter(token=OuterRef("return_token"))
                .values("issue_date")[:1]
            )
        ).exclude(
            Q(status__token=invoice_cancelled_token)
            & (
                Q(issue_date__lt=cutoff_date)
                | Q(return_token__isnull=True)
                | Q(return_token__exact="")
                | Q(return_invoice_issue_date__isnull=True)
                | Q(return_invoice_issue_date__lte=cutoff_date)
            )
        )

        # Collect all related contract IDs from different invoice relationships.
        contract_ids = set(
            invoices.values_list("contract__id", flat=True).distinct()
        )
        contract_request_ids = set(
            Contract.objects.filter(
                contract_request__id__in=invoices.values_list(
                    "contract_request__id", flat=True
                ).distinct()
            )
            .values_list("id", flat=True)
            .distinct()
        )
        contract_termination_ids = set(
            invoices.values_list(
                "contract_termination__contract__id", flat=True
            ).distinct()
        )

        all_contract_ids = (
            contract_ids | contract_request_ids | contract_termination_ids
        )

        contracts = Contract.objects.filter(id__in=all_contract_ids).distinct()

        multi_ids = get_multi_ids(request.data)
        contract_multi_q = contract_multi_filter_q(person_ids=multi_ids['person_ids'], contract_ids=multi_ids['contract_ids'])
        if contract_multi_q:
            contracts = contracts.filter(contract_multi_q).distinct()

        # Accumulate debt per contract (keyed by token); in-memory dict so it persists.
        contract_debt = {}
        
        single_invoices = {}

        wb = openpyxl.Workbook()
        contract_debt_sheet = wb.create_sheet(title=_("Contractes amb deute"))
        pending_invoices_sheet = wb.create_sheet(title=_("Factures pendents"))
        
        row = 0
        inv_row = 0
        titles = [_("Explotació"), _("Contracte"), _("Abonat"), _("NIF Client"), _("Deute Pendent")]
        row = add_row(contract_debt_sheet, row, titles, fill=black_fill, font=white_bold_font)
        
        inv_titles = [_("Contracte"), _("NIF Client"), _("Núm. factura"), _("Data factura"), _("Estat"), _("Data pagament"), _("Total factura"), _("Total pendent")]
        inv_row = add_row(pending_invoices_sheet, inv_row, inv_titles, fill=black_fill, font=white_bold_font)
        count = 0
        total_invoices_progress = invoices.count()
        for inv in invoices:
            if count % 1000 == 0:
                print(f"processing invoice {count} out of {total_invoices_progress}")
            count += 1
            if task and count % 50 == 0:
                task.update_state(
                    state='PROGRESS',
                    meta={
                        'current': count,
                        'total': total_invoices_progress,
                        'percent': round((count / total_invoices_progress) * 100, 2) if total_invoices_progress else 0.0
                    }
                )
            contract_token = None
            if inv.contract:
                contract_token = inv.contract.token
            elif inv.contract_request:
                contract_token = inv.contract_request.token
                try:
                    contract_token = Contract.objects.get(token=contract_token).token
                except Exception as e:
                    print(f"error getting contract {contract_token}: {e}")
                    continue
            elif inv.contract_termination:
                contract_token = inv.contract_termination.contract.token
            if contract_token is not None:
                contract_debt[contract_token] = contract_debt.get(contract_token, 0) + inv.left_to_pay
            else:
                # Aggregate debt for customers whose invoices are not linked to a contract.
                prev_data = single_invoices.get(inv.customer_token_final, {})
                customer_debt = prev_data.get("left_to_pay", 0) + inv.left_to_pay
                single_invoices[inv.customer_token_final] = {
                    "exploitation": inv.exploitation.name if inv.exploitation else "",
                    "customer_token_final": inv.customer_token_final,
                    "customer_final": inv.customer_final,
                    "left_to_pay": customer_debt,
                }
            payment = inv.payments.all().order_by('-payment_date').first()
            inv_row_data = [
                inv.contract.token if inv.contract else inv.contract_request.token if inv.contract_request else inv.contract_termination.contract.token if inv.contract_termination else "",
                inv.customer_token_final,
                inv.serie_final,
                inv.issue_date.strftime('%d-%m-%Y') if inv.issue_date else "",
                inv.status.name,
                payment.payment_date.strftime('%d-%m-%Y') if payment and payment.payment_date and payment.status.token == payment_paid_token else "",
                inv.total_final,
                inv.left_to_pay,
            ]
            inv_row = add_row(pending_invoices_sheet, inv_row, inv_row_data)
        
        adjust_column_widths(pending_invoices_sheet)    
        contract_count = 0
        for contract in contracts:
            if contract_count % 1000 == 0:
                print(f"processing contract {contract_count} out of {contracts.count()}")
            contract_count += 1
            total_debt = contract_debt.get(contract.token, 0)
            contract_row_data = [
                contract.supply_point_default.connection.exploitation.name if contract.supply_point_default and contract.supply_point_default.connection and contract.supply_point_default.connection.exploitation else "",
                contract.token,
                str(contract.holder),
                contract.holder.token,
                total_debt,
            ]
            row = add_row(contract_debt_sheet, row, contract_row_data)
        
        # Add rows for "single" invoices (customers without a linked contract) to the same debt sheet.
        for data in single_invoices.values():
            contract_row_data = [
                data["exploitation"],
                "",
                data["customer_final"],
                data["customer_token_final"],
                data["left_to_pay"],
            ]
            row = add_row(contract_debt_sheet, row, contract_row_data)
        
        adjust_column_widths(contract_debt_sheet)  
        
        filename = f"{name}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        wb.save(filename)

        # Send the file as a response
        with open(filename, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = f"attachment; filename={filename}"
        
        document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id)
        os.remove(filename)
        return response, document_id, None
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None
    
    

    
def generate_sgt_txt_report(request, black_fill=None, white_bold_font=None, task=None):
    try:
        print("getting sgt txt report")
        
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
        start_date = None
        end_date = None
        
        exploitation = None
        if exploitation_id:
            exploitation = Exploitation.objects.get(id=exploitation_id)
        
        if billing_ids:
            invoices = Invoice.objects.filter(billing_id__in=billing_ids)
            invoices = filter_pending_invoices(invoices, request)
        elif date_range:
            start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
            end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
            invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
            invoices = Invoice.objects.filter(issue_date__range=(start_date.date(), end_date.date()), type_final=invoice_type, payments__is_active=True, exploitation__isnull=False).distinct()
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

        multi_q = invoice_multi_filter_q(**get_multi_ids(request.data))
        if multi_q:
            invoices = invoices.filter(multi_q).distinct()

        content_file, file_name = generate_sgt_txt_content(None, invoices)

        response = HttpResponse(content_file.getvalue(), content_type="text/plain")
        response["Content-Disposition"] = f'attachment; filename="{file_name}"'
        document_id = save_report(
            content=content_file.getvalue(),
            filename=file_name,
            name=name,
            type_id=type_id,
            start_date=start_date,
            end_date=end_date,
        )
        return response, document_id, None
    except Exception as e:
        return Response({"error": f"Ha ocorregut un error inesperat: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR), None, None
    

def generate_pending_invoices_values_report(request, black_fill=None, white_bold_font=None):
    
    id = request.data.get('id', None)
    date_range = request.data.get('date_range', None)
    name = request.data.get('name', '')
    type_id = request.data.get('type_id', None)
    exploitation_id = request.data.get('exploitation_id', None)
    accounting_type = request.data.get('accounting_type', None)
    
    
    start_date = datetime.datetime.strptime(date_range[0], '%Y-%m-%dT%H:%M:%S.%fZ')
    end_date = datetime.datetime.strptime(date_range[1], '%Y-%m-%dT%H:%M:%S.%fZ')
    
    cutoff_date = end_date
    cancelled_issue_date_cutoff = end_date - datetime.timedelta(days=30)
    post_year_cutoff = end_date
    paid_status_token = ConfigProject.objects.get(token="payment_status_paid_token").value

    # Invoices issued on/before cutoff that were NOT paid during the period:
    # - include if no "paid" payments exist yet
    # - include if latest "paid" payment_date is AFTER the cutoff (paid later)
    # - exclude if latest "paid" payment_date is on/before cutoff (paid within period)
    payment_paid_token = ConfigProject.objects.get(token="payment_status_paid_token").value
    invoice_payoff_token = ConfigProject.objects.get(token="invoice_status_payoff_token").value
    invoice_pending_token = ConfigProject.objects.get(token="invoice_status_pending_token").value
    invoice_cancelled_token = ConfigProject.objects.get(token="invoice_status_cancelled_token").value
    payment_balance_token = ConfigProject.objects.get(token="payment_status_piggy_token").value
    payment_tokens = ConfigProject.objects.filter(
        token__in=[
            "payment_status_returned_token",
            "payment_status_pending_token",
            "payment_status_expired_token",
            "payment_status_endowment_token",
            "payment_status_irrecoverable_token"
            ]
    ).values_list("value", flat=True)
    invoices = (
        Invoice.objects.filter(
            type_final="F",
            issue_date__gte=start_date,
            issue_date__lte=cutoff_date,
        ).exclude(
            status__token__in=[invoice_payoff_token,invoice_pending_token]
        ).exclude(
            payments__status__token=payment_balance_token
        ).filter(
            Q(payments__payment_date__gt=cutoff_date, payments__status__token=payment_paid_token) | 
            Q(payments__status__token__in=payment_tokens)
        )
    )

    # Cancelled invoices handling (return invoices):
    # - Cancelled with issue_date < 2025-10-01 => ignore
    # - Cancelled with no return_token => ignore
    # - Cancelled with return_token => keep ONLY if the referenced invoice issue_date is post-2025 (>= 2026-01-01)
    print("invoices: ", invoices.count())
    invoices = invoices.annotate(
        return_invoice_issue_date=Subquery(
            Invoice.objects.filter(token=OuterRef("return_token"))
            .values("issue_date")[:1]
        )
    ).exclude(
        Q(status__token=invoice_cancelled_token)
        & (
            Q(issue_date__lt=cancelled_issue_date_cutoff)
            | Q(return_token__isnull=True)
            | Q(return_token__exact="")
            | Q(return_invoice_issue_date__isnull=True)
            | Q(return_invoice_issue_date__lte=post_year_cutoff)
        )
    )

    # Collect all related contract IDs from different invoice relationships.
    contract_ids = set(
        invoices.values_list("contract__id", flat=True).distinct()
    )
    contract_request_ids = set(
        Contract.objects.filter(
            contract_request__id__in=invoices.values_list(
                "contract_request__id", flat=True
            ).distinct()
        )
        .values_list("id", flat=True)
        .distinct()
    )
    contract_termination_ids = set(
        invoices.values_list(
            "contract_termination__contract__id", flat=True
        ).distinct()
    )

    all_contract_ids = (
        contract_ids | contract_request_ids | contract_termination_ids
    )

    contracts = Contract.objects.filter(id__in=all_contract_ids).distinct()

    # Accumulate debt per contract (keyed by token); in-memory dict so it persists.
    contract_debt = {}
    
    single_invoices = {}

    wb = openpyxl.Workbook()
    contract_debt_sheet = wb.create_sheet(title=_("Contractes amb deute"))
    pending_invoices_sheet = wb.create_sheet(title=_("Factures pendents"))
    
    row = 0
    inv_row = 0
    titles = [_("Explotació"), _("Contracte"), _("Abonat"), _("NIF Abonat"), _("Deute Pendent")]
    row = add_row(contract_debt_sheet, row, titles, fill=black_fill, font=white_bold_font)
      
    inv_titles = [_("Contracte"), _("NIF Abonat"), _("Núm Factura"), _("Data Factura"), _("Estat"), _("Data pagament"), _("Total Factura"), _("Total Pendent")]
    inv_row = add_row(pending_invoices_sheet, inv_row, inv_titles, fill=black_fill, font=white_bold_font)
    count = 0
    for inv in invoices:
        if count % 1000 == 0:
            print(f"processing invoice {count} out of {invoices.count()}")
        count += 1
        contract_token = None
        if inv.contract:
            contract_token = inv.contract.token
        elif inv.contract_request:
            contract_token = inv.contract_request.token
            try:
                contract_token = Contract.objects.get(token=contract_token).token
            except Exception as e:
                print(f"error getting contract {contract_token}: {e}")
                continue
        elif inv.contract_termination:
            contract_token = inv.contract_termination.contract.token
        if contract_token is not None:
            contract_debt[contract_token] = contract_debt.get(contract_token, 0) + inv.left_to_pay
        else:
            # Aggregate debt for customers whose invoices are not linked to a contract.
            prev_data = single_invoices.get(inv.customer_token_final, {})
            customer_debt = prev_data.get("left_to_pay", 0) + inv.left_to_pay
            single_invoices[inv.customer_token_final] = {
                "exploitation": inv.exploitation.name if inv.exploitation else "",
                "customer_token_final": inv.customer_token_final,
                "customer_final": inv.customer_final,
                "left_to_pay": customer_debt,
            }
        payment = inv.payments.all().order_by('-payment_date').first()
        inv_row_data = [
            inv.contract.token if inv.contract else inv.contract_request.token if inv.contract_request else inv.contract_termination.contract.token if inv.contract_termination else "",
            inv.customer_token_final,
            inv.serie_final,
            inv.issue_date.strftime('%d-%m-%Y') if inv.issue_date else "",
            inv.status.name,
            payment.payment_date.strftime('%d-%m-%Y') if payment and payment.payment_date and payment.status.token == payment_paid_token else "",
            inv.total_final,
            inv.left_to_pay,
        ]
        inv_row = add_row(pending_invoices_sheet, inv_row, inv_row_data)
    
    adjust_column_widths(pending_invoices_sheet)    
    contract_count = 0
    for contract in contracts:
        if contract_count % 1000 == 0:
            print(f"processing contract {contract_count} out of {contracts.count()}")
        contract_count += 1
        total_debt = contract_debt.get(contract.token, 0)
        contract_row_data = [
            contract.supply_point_default.connection.exploitation.name if contract.supply_point_default and contract.supply_point_default.connection and contract.supply_point_default.connection.exploitation else "",
            contract.token,
            str(contract.holder),
            contract.holder.token,
            total_debt,
        ]
        row = add_row(contract_debt_sheet, row, contract_row_data)
    
    # Add rows for "single" invoices (customers without a linked contract) to the same debt sheet.
    for data in single_invoices.values():
        contract_row_data = [
            data["exploitation"],
            "",
            data["customer_final"],
            data["customer_token_final"],
            data["left_to_pay"],
        ]
        row = add_row(contract_debt_sheet, row, contract_row_data)
    
    adjust_column_widths(contract_debt_sheet)  
    
    filename = f"deute_pendent_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    wb.save(filename)

    # Send the file as a response
    with open(filename, "rb") as f:
        response = HttpResponse(f.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = f"attachment; filename={filename}"
    
    document_id = save_report(content=wb, filename=filename, name=name, type_id=type_id)
    os.remove(filename)
    return response, document_id, None