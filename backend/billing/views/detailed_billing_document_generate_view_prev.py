import datetime
import unicodedata
from collections import defaultdict
from io import BytesIO
from types import SimpleNamespace
import re
from django.core.files.storage import default_storage
from django.http import FileResponse
from matplotlib.dates import relativedelta
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from django.core.files.base import ContentFile
from decimal import Decimal
from billing.models import Billing, Invoice, InvoiceLineItem
from contract.models import Contract
from coredata.models import ConfigProject
from service.models import Company, Exploitation, SupplyPoint
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions

class DetailedBillingDocumentGenerateView(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Billing.objects.all().order_by('-created_at')
    
    def __init__(self, *args, **kwargs):
        self.contract_domestic_use_type_token = None
        self.contract_industrial_use_type_token = None
        self.contract_municipal_use_type_token = None
        self.contract_keeper_use_type_token = None
        self.token_meter_status_no_meter = None
        self.debt_vulnerable_token = None
        self.tarifa_social_token = None
    
    def put(self, request, *args, **kwargs):
        print("In Detailed Billing Document Generate View")
        # FACDETA
        
        origin_reading_token = ConfigProject.objects.get(token='origin_reading_token').value
        token_product_canon = ConfigProject.objects.get(token='product_canon_token').value
        invoice_token_pending = ConfigProject.objects.get(token='invoice_status_pending_token').value
        main_company_token = ConfigProject.objects.get(token='main_company_token').value
        self.contract_domestic_use_type_token = ConfigProject.objects.get(token='contract_domestic_use_type_token').value
        self.contract_industrial_use_type_token = ConfigProject.objects.get(token='contract_industrial_use_type_token').value
        self.contract_municipal_use_type_token = ConfigProject.objects.get(token='contract_municipal_use_type_token').value
        self.contract_comercial_use_type_token = ConfigProject.objects.get(token='contract_comercial_use_type_token').value
        self.contract_keeper_use_type_token = ConfigProject.objects.get(token='contract_keeper_use_type_token').value
        self.token_meter_status_no_meter = ConfigProject.objects.get(token='token_meter_status_no_meter').value
        self.debt_vulnerable_token = ConfigProject.objects.get(token='debt_vulnerable_token').value
        self.tarifa_social_token = ConfigProject.objects.get(token='tarifa_social').value
        company = Company.objects.get(vat=main_company_token)
        invoice_type = ConfigProject.objects.get(token="invoice_type_invoice_token").value
        active_contract_token = ConfigProject.objects.get(token='contract_active_token').value
        exploitations = Exploitation.objects.filter(is_active=True)
        
        consumption_30_days = 6
        
        file_urls = []
        
        for exploitation in exploitations:
            print("\n\n--------------------------------")
            print("Exploitation: ", exploitation.name)
            total_exploitation = 0
        
            invoices = Invoice.objects.filter(
                payments__is_active=True, 
                type_final=invoice_type,
                exploitation=exploitation,
                origin__token=origin_reading_token,
                issue_date__year=2025,
                issue_date__gte=datetime.date(2025,10,1),
                ).exclude(
                    status__token=invoice_token_pending
                ).distinct()
            print("Invoices: ", invoices.count())
            entity_code = company.supply_code
            entity_nif = company.vat 
            ine_code = exploitation.code
            
            # Group invoices by year based on issue_date
            invoices_by_year = defaultdict(list)
            for invoice in invoices:
                year = invoice.issue_date.year
                invoices_by_year[year].append(invoice)
            
            # Process each year separately
            for year, year_invoices in invoices_by_year.items():
                print(f"Processing year {year} with {len(year_invoices)} invoices")
                content_file = BytesIO()
                total_invoices = 0
                file_name = f"FD{entity_code}_{ine_code}_{year}.txt"
            
                max_characters = 664
                
                """ 
                CAPÇELERA DEL SUPORT
                REGISTRE DETALL DE FACTURES AMB 664 CHATS A CADA LINEA
                REGISTRE TOTAL DEL SUPORT
                """
                #
                #   SUPPORT HEADER
                #
                # support_header_space_length = 16-(len(entity_code) + len(entity_nif))
            
                support_header = f"10{normalize_text((entity_code + entity_nif), 16)}FACTDETA{year}{ine_code}{repeat_to_at_least_length(' ', 628)}"
                
                content_file.write((support_header + "\n").encode("utf-8"))
                
                #
                #   INVOICES DETAIL
                #
                
                #TODO: INVOICE LINES DETAIL
                
                invoice_tokens = [invoice.token for invoice in year_invoices]
                refactored_invoices = Invoice.objects.filter(
                    return_token__in=invoice_tokens,
                    type_final=invoice_type
                ).order_by('return_token', '-created_at')
                
                refactored_invoice_map = {}
                for inv in refactored_invoices:
                    if inv.return_token not in refactored_invoice_map:
                        refactored_invoice_map[inv.return_token] = inv

                for invoice in year_invoices:
                    if total_invoices % 500 == 0:
                        print("Processed: ", total_invoices)
                    first_reading = invoice.readings.order_by('-reading_date').first()
                    if first_reading:
                        date_consumption_end = first_reading.reading_date.strftime("%Y%m%d")
                        if first_reading.previous_reading:
                            date_consumption_start = first_reading.previous_reading.reading_date.strftime("%Y%m%d")
                        else:
                            if invoice.consumption_days:
                                date_consumption_start = ((first_reading.reading_date) - relativedelta(days=abs(invoice.consumption_days))).strftime("%Y%m%d")
                            else:
                                date_consumption_start = (first_reading.reading_date - relativedelta(days=abs(first_reading.consumption_days) if first_reading.consumption_days else 0)).strftime("%Y%m%d")
                    else:
                        print("invoice.id: ", invoice.serie_final)
                        raise Exception("No first reading found for invoice")
                        
                        
                    applied_adjustments = []
                    for line_item in invoice.line_items.all():
                        if hasattr(line_item, "adjustments") and line_item.adjustments:
                            applied_adjustments.extend(line_item.adjustments.all())
                    read_consumption = abs(invoice.consumption)
                    consumption = 0
                    
                    contract = invoice.contract if invoice.contract else None
                    if not contract:
                        if invoice.contract_termination:
                            contract = invoice.contract_termination.contract
                        if invoice.contract_request:
                            contract = Contract.objects.filter(contract_request=invoice.contract_request).first()
                    policy_num = contract.token.replace('/','')
                    
                    meter_type = get_meter_type(self, invoice, contract)
                    debt_vulnerable_token = self.debt_vulnerable_token
                    line_items = InvoiceLineItem.objects.filter(invoice=invoice, product__exploitation=exploitation, is_active=True)
                    line_items_by_meters = line_items.order_by('-reading__meter__created_at').values('reading__meter').distinct()
                    
                    #TODO LATER: ADD A LINE FOR EACH METER
                    meter_count = 0
                        
                    for meter in line_items_by_meters:
                        clean_invoice = get_clean_serie_final(invoice, meter_count)
                        line_items = line_items.filter(reading__meter__id=meter['reading__meter'])
                        
                        line_items_canon = line_items.filter(product__token__startswith=token_product_canon)
                        
                        if not line_items_canon.exists():
                            continue
                        
                        refactored_invoice = refactored_invoice_map.get(invoice.token, None)
                        price_total = sum(abs(line_item.price) for line_item in line_items_canon)
                        """ print("contract use type: ", contract.use_type)
                        print("contract use type: ", contract.use_type.token if contract.use_type else None)
                        for line_item in line_items_canon:
                            print("line item: ", line_item)
                            print("line item: ", line_item.interval) """
                        if ((contract.use_type and contract.use_type.token == self.contract_domestic_use_type_token) or contract.use_aca == "D") and any(line_item.interval and line_item.interval > 0 for line_item in line_items_canon):
                            consumption = sum(abs(line_item.units) for line_item in line_items_canon)
                            if not refactored_invoice:
                                consumption = sum(abs(line_item.units) for line_item in line_items_canon.filter(
                                    price_unit__gte=0   # FILTER FOR CORRECTIONS (TEMPORARY)
                                ))
                        else:
                            """ if round(price_total, 2) == 0:  # NOMÉS ELS INDUSTRIALS NO S'HAN DE DECLARA SI ÉS 0
                                continue """
                            consumption = abs(line_items_canon.exclude(line_item_type__quantity__token="diferencia_fuita").order_by('-units').first().units)
                            if line_items_canon.filter(line_item_type__quantity__token="diferencia_fuita").exists():
                                consumption += abs(line_items_canon.filter(line_item_type__quantity__token="diferencia_fuita").order_by('-units').first().units)
                        # if int(consumption) == 0 or (round(price_total, 2) == 0 and all(round(line_item.price_unit, 4) == 0 for line_item in line_items_canon)):
                        if int(consumption) == 0 and (round(price_total, 2) == 0 and all(round(line_item.price_unit, 4) == 0 for line_item in line_items_canon)):
                            continue
                        price_rate_letter = get_price_rate(self, invoice, line_items_canon.exclude(line_item_type__quantity__token="diferencia_fuita").distinct())
                        
                        if price_rate_letter in ["I", "A"] and round(price_total, 2) == 0:
                            continue
                        
                        try:
                            codi_establiment = contract.variables.filter(type__token__in=["Factura-ACA"]).first().value
                        except:
                            codi_establiment = None
                        
                        total_invoices += 1
                        len_policy_num = 15 - len(policy_num)
                        
                        if invoice.readings.all().count() > 0:
                            #read_consumption = sum(int(reading.calculated_value) - int(reading.estimated_used if reading.estimated_used else 0) for reading in invoice.readings.filter(meter__id=meter['reading__meter']))
                            read_consumption = sum(int(reading.real_consumption) for reading in invoice.readings.filter(meter__id=meter['reading__meter']))
                        # since everything else makes sense, reading could be wrong (will be later fixed)
                        if read_consumption > consumption:
                            read_consumption = consumption
                        if codi_establiment and price_rate_letter == "M":
                            consumption = 0
                        # print("read consumption after: ", read_consumption)
                        len_read_consumption = 12 - len(str(int(read_consumption)))
                        len_consumption = 12 - len(str(int(abs(consumption))))
                        
                        line_content = "20"
                        line_content += ine_code
                        
                        line_content += normalize_text(clean_invoice,10)      #should be 10 chars max
                        line_content += invoice.issue_date.strftime("%Y%m%d")
                        none_valid = ['00000000T', '00000001R', '99999999R', 'X0000000T']
                        line_content += normalize_text(invoice.customer_token_final if invoice.customer_token_final not in none_valid else '99999999R', 20)        #POS 36
                        
                        line_content += price_rate_letter
                        if not invoice.customer_is_juridic:
                            name_compare = f"{contract.holder.name} {contract.holder.surname if contract.holder.surname else ''}"
                            if name_compare == invoice.customer_final:
                                customers_final_surnames = contract.holder.surname.split(' ') if contract.holder.surname else []
                                first_surname = customers_final_surnames[0] if len(customers_final_surnames) > 0 else ''
                                second_surname = customers_final_surnames[1] if len(customers_final_surnames) > 1 else ''
                                name = contract.holder.name
                            else:
                                customers_final_surnames = invoice.customer_final.split(' ')
                                first_surname = customers_final_surnames[1] if len(customers_final_surnames) > 1 else ''
                                second_surname = customers_final_surnames[2] if len(customers_final_surnames) > 2 else ''
                                name = customers_final_surnames[0]
                            
                            line_content += normalize_text((first_surname).upper(),15)
                            line_content += normalize_text((second_surname).upper(),15)
                            line_content += normalize_text((name).upper(), 10)
                        else:
                            if len(invoice.customer_final) <= 40:
                                len_juridic_name = 40 - len(invoice.customer_final)
                                
                                line_content += invoice.customer_final.upper() 
                                line_content += repeat_to_at_least_length(' ', len_juridic_name)
                            else:
                                line_content += normalize_text(invoice.customer_final.upper(), 40)
                        
                        line_content += get_address(invoice, contract)        #START POST 88 END POS 183
                        
                        line_content += repeat_to_at_least_length('0', len_policy_num) + policy_num
                        line_content += normalize_text(invoice.contract.supply_point_default.meter.code, 25)
                        line_content += meter_type     #POS 223
                        
                        line_content += date_consumption_start
                        line_content += date_consumption_end        #END POS 240
                        
                        
                        read_consumption_str = repeat_to_at_least_length('0', len_read_consumption) + str(int(read_consumption))
                        consumption_str = repeat_to_at_least_length('0', len_consumption) + str(int(abs(consumption)))
                        
                        if consumption < 0:
                            consumption_str = '-' + consumption_str[1:]
                        if refactored_invoice:
                            read_consumption_str = '-' + read_consumption_str[1:] if read_consumption_str.startswith('0') and int(read_consumption) > 0 else read_consumption_str
                            consumption_str = '-' + consumption_str[1:] if consumption_str.startswith('0') and int(consumption) > 0 else consumption_str
                        
                        line_content += read_consumption_str
                        line_content += consumption_str    #END POS 264
                        
                        total_leak = 0
                        if line_items_canon.filter(line_item_type__quantity__token="diferencia_fuita").exists():
                            total_leak = sum(int(line_item.units) for line_item in line_items_canon.filter(line_item_type__quantity__token="diferencia_fuita").distinct())
                        
                        """ print("line_items_canon: ", line_items_canon)
                        for line_item in line_items_canon:
                            print("line_item: ", line_item.product.name)
                            print("line_item: ", line_item.name)
                            print("line_item: ", line_item.units)
                            print("line_item: ", line_item.price_unit)
                            print("line_item: ", line_item.price)
                            print("line_item: ", line_item.line_item_type) """
                        # line_content += "|"
                        line_content += get_canon_line_items(self, invoice, line_items_canon, contract, total_leak, refactored_invoice, price_rate_letter) #END POS 500
                        # line_content += "|"
                        #TODO: FUITES
                        # print("leak item:", line_items_canon.filter(line_item_type__quantity__token="diferencia_fuita"))
                        if line_items_canon.filter(line_item_type__quantity__token="diferencia_fuita").exists():
                            len_leak_consumption = 9 - len(str(int(total_leak)))
                            # print("total leak:", total_leak)
                            line_item_leak = line_items_canon.filter(line_item_type__quantity__token="diferencia_fuita").first()
                            len_price_units = 3 - len(str(round(line_item_leak.price_unit, 4)).split('.')[0])
                            len_total_units = 12 - len(str(round(abs(line_item_leak.price),2)).split('.')[0])
                            # print("price unit:", line_item_leak.price_unit)
                            # print("price:", line_item_leak.price)
                            price_units = str(abs(round(line_item_leak.price_unit, 4))).split('.')[0]
                            total_units = str(round(abs(line_item_leak.price),2)).split('.')[0]
                            try:
                                len_price_units_decimal = 6 - len(str(round(line_item_leak.price_unit, 4)).split('.')[1])
                                price_units_decimal = str(round(line_item_leak.price_unit, 4)).split('.')[1]
                                len_total_units_decimal = 4 - len(str(round(abs(line_item_leak.price),2)).split('.')[1])
                                total_units_decimal = str(round(abs(line_item_leak.price),2)).split('.')[1]
                            except:
                                len_price_units_decimal = 5
                                price_units_decimal = "0"
                                len_total_units_decimal = 3
                                total_units_decimal = "0"
                            total_leak_consumption_str = repeat_to_at_least_length('0', len_leak_consumption) + str(int(total_leak))
                            total_leak_units_str = repeat_to_at_least_length('0', len_total_units) + total_units + total_units_decimal + repeat_to_at_least_length('0', len_total_units_decimal) # import facturat de fuites 9(12)v9(4)
                            if refactored_invoice:
                                total_leak_units_str = '-' + total_leak_units_str[1:] if total_leak_units_str.startswith('0') else total_leak_units_str
                                total_leak_consumption_str = '-' + total_leak_consumption_str[1:] if total_leak_consumption_str.startswith('0') else total_leak_consumption_str
                            line_content += total_leak_consumption_str # volum facturat de fuites
                            line_content += repeat_to_at_least_length('0', len_price_units) + price_units + price_units_decimal + repeat_to_at_least_length('0', len_price_units_decimal)  # tarifa de fuites 9(3)v9(6)
                            line_content += total_leak_units_str
                        else:
                            line_content += repeat_to_at_least_length('0', 34)
                        
                        # line_content += "|"
                        #TODO IMPORTA TARIFA DE QUOTA ?????
                        line_content += repeat_to_at_least_length('0', 16) # import quota anual 9(12)v9(4)
                        line_content += repeat_to_at_least_length('0', 16) # import facturat de quota 9(12)v9(4)
                        total_line_items_canon = get_total_line_items(line_items_canon)
                        total_canon = (str(total_line_items_canon)).split('.')
                        total_exploitation += total_line_items_canon
                        # line_content += repeat_to_at_least_length('0', 12-len(total_canon[0]))      #START POS 566
                        try:
                            decimal_part = total_canon[1]
                            
                            decimal_part_padded = decimal_part.ljust(3, '0')
                            first_two_digits = int(decimal_part_padded[:2])
                            third_digit = int(decimal_part_padded[2])
                            first_canon = int(total_canon[0])
                            if third_digit >= 5:
                                first_two_digits += 1
                                
                                if first_two_digits == 100:
                                    first_two_digits = 0
                                    first_canon += 1
                            first_canon_str = repeat_to_at_least_length('0', 12-len(str(first_canon)))
                            if refactored_invoice:
                                first_canon_str = '-' + first_canon_str[1:] if first_canon_str.startswith('0') else first_canon_str
                            line_content += first_canon_str      #START POS 566
                            line_content += str(first_canon)
                            line_content += f"{first_two_digits:02}0"
                        except:
                            line_content += repeat_to_at_least_length('0', 12-len(total_canon[0]))      #START POS 566
                            line_content += total_canon[0]
                            line_content += repeat_to_at_least_length('0', 2)
                        """ 
                        total_iva = str(float(invoice.total_final) - float(invoice.subtotal_final)).split('.')
                        
                        line_content += repeat_to_at_least_length('0', 11-len(total_iva[0]))
                        line_content += total_iva[0]
                        line_content += normalize_text(total_iva[1],2).replace(' ', '0')    #END POS 593
                        """
                        # # line_content += "|"
                        line_content += repeat_to_at_least_length('0', 12)
                        
                        
                        # CAP EXEMPLE AMB TOTAL FACTURA DECLARAT
                        """ total_invoice = str(round(invoice.total_final,2)).split('.')
                        line_content += repeat_to_at_least_length('0', 12-len(total_invoice[0]))
                        line_content += total_invoice[0]
                        try:
                            decimal_part = total_invoice[1]
                            
                            decimal_part_padded = decimal_part.ljust(3, '0')
                            first_two_digits = int(decimal_part_padded[:2])
                            third_digit = int(decimal_part_padded[2])
                            
                            if third_digit >= 5:
                                first_two_digits += 1
                                
                                if first_two_digits == 100:
                                    first_two_digits = 0
                            
                            line_content += f"{first_two_digits:02}"
                            line_content += repeat_to_at_least_length('0', 2-len(str(int(total_invoice[1]))))
                        except:
                            line_content += repeat_to_at_least_length('0', 2) """
                        
                        line_content += repeat_to_at_least_length('0', 14)
                        
                        
                        if refactored_invoice:
                            #TODO ADD CANCELLED INVOICE NUMBER AND ISSUE DATE INSTEAD (WHAT IS THIS INVOICE?) 
                            line_content += normalize_text(get_clean_serie_final(refactored_invoice, meter_count), 10)
                            line_content += refactored_invoice.issue_date.strftime('%Y%m%d')
                        else:
                            line_content += normalize_text('', 10)
                            line_content += normalize_text('', 8)
                        # # line_content += "|"
                        # 'S' SO ÉS UNA ANUL·LACIÓ D'UNA FACTURA CANCEL·LADA (NO S'HAN TROBAT EXEMPLES DE 'S')
                        line_content += 'N'
                        is_domestic = price_rate_letter == "D"
                        
                        if is_domestic:
                            # 'S' SI HA HAGUT UNA AMPLICACIÓ DE TRAMS (AFEGIR CONDICIONAL A INVOICELINEITEM)
                            try:
                                first_interval = line_items_canon.filter(interval=1, end_stretch__isnull=False).first()
                                line_item = first_interval.line_item_type
                                end_stretch = 0
                                if line_item.price_interval and len(line_item.price_interval.price_interval_stretches) > 0:
                                    end_stretch = line_item.price_interval.price_interval_stretches.order_by('stretch').first().end_stretch
                                    if invoice.consumption_days and invoice.consumption_days != 0:
                                        end_stretch = end_stretch * (invoice.consumption_days / 90) # CANON NOMES TRIMESTRAL PER DOMESTIC (?)
                                first_interval_end_stretch = first_interval.end_stretch
                            except:
                                end_stretch = 0
                                first_interval_end_stretch = 0
                            first_interval_diff = first_interval_end_stretch - end_stretch
                            # if first_interval_diff != 0 :
                            if contract.total_persons > 3 and is_domestic:
                                line_content += 'S'
                                len_total_persons = 2 - len(str(contract.total_persons))
                                line_content += repeat_to_at_least_length('0', len_total_persons) + str(contract.total_persons)
                            else:
                                line_content += 'N00'
                        else:
                            line_content += ' 00'
                        if is_domestic:
                            # 'S' SI TÉ BO SOCIAL (valor no implementat?)
                            if any(
                                cond.quantity and 'value' in cond.quantity and cond.quantity['value'] == f"variable.{self.tarifa_social_token}"
                                for adj in applied_adjustments for cond in adj.adjustment.conditions.all()
                            ):
                                line_content += 'S'
                            else:
                                line_content += 'N'
                        else:
                            line_content += ' '
                        
                        if any(adj.is_vulnerable for adj in applied_adjustments) and ((contract.use_type and contract.use_type.token == self.contract_domestic_use_type_token) or contract.use_aca == "D"):
                            line_content += 'S'
                        else:
                            line_content += 'N'
                            
                        # line_content += normalize_text(' ', 10)
                        
                        # print("codi_establiment: ", codi_establiment)
                        # print("price_rate_letter: ", price_rate_letter)
                        if price_rate_letter == "M" and codi_establiment:
                            #TODO: CODI ACA ESTABLIMENT?
                            len_codi_establiment = 10 - len(codi_establiment)
                            line_content += repeat_to_at_least_length('0', len_codi_establiment) + codi_establiment
                        else:
                            line_content += normalize_text(' ', 10)
                        
                        if meter_type == "G":
                            try:
                                total_active_contracts = Contract.objects.filter(
                                    supply_point_default__meter__id=meter['reading__meter'], 
                                    status__token=active_contract_token).count()
                                if contract.variables.filter(type__token="general").exists():
                                    variable = contract.variables.filter(type__token="general").first()
                                    total_active_contracts = variable.value
                                len_active_contracts = 3 - len(str(total_active_contracts))
                                line_content += repeat_to_at_least_length('0', len_active_contracts)
                                line_content += str(total_active_contracts)
                            except:
                                line_content += repeat_to_at_least_length('0', 3)
                        else:
                            line_content += repeat_to_at_least_length('0', 3)
                        
                        #TODO: NUM PLACES D'ESTABLIMENTS TURISTICS, HOTELS, CAMPINGS...
                        line_content += repeat_to_at_least_length('0', 4)
                        
                        line_content += repeat_to_at_least_length('0', 8)
                        line_content += repeat_to_at_least_length('0', 9)
                        
                        if len(line_content) != 664:
                            print("len line content: ", len(line_content))
                            print("line different in line: ", line_content)
                            print("contract: ", contract.token)
                            print("invoice: ", invoice.serie_final)
                        
                        meter_count += 1
                        
                        line_content = remove_accents(line_content)
                        content_file.write((line_content + "\n").encode("utf-8"))
            
                #
                #   SUPPORT FOOTER
                #
                total_lines_report = total_invoices + 2
                len_before_ine_code = 9 - len(ine_code)
                len_total_invoices = 8 - len(str(total_invoices))
                len_total_lines_report = 8 - len(str(total_lines_report))
                support_footer = f"30{entity_code}{entity_nif}{repeat_to_at_least_length(' ', len_before_ine_code)}{ine_code}{repeat_to_at_least_length('0', len_total_invoices)}{total_invoices}{repeat_to_at_least_length('0', len_total_lines_report)}{total_lines_report}{repeat_to_at_least_length(' ', 624)}"

                
                #
                #   FILE
                #
                
                content_file.write((support_footer + "\n").encode("utf-8"))
                
                # Save this year's file separately
                print("\n TOTAL EXPLOITATION: ", total_exploitation)
                file = ContentFile(content_file.getvalue(), name=file_name)
                temp_rel_path = f"tmp/FACDETA/{file_name}"
                saved_path = default_storage.save(temp_rel_path, file)
                file_url = request.build_absolute_uri(default_storage.url(saved_path))
                file_urls.append({"year": year, "file_url": file_url, "file_name": file_name})
        
        # Return list of file URLs
        if file_urls:
            return Response({"files": file_urls, "message": "Files generated successfully"}, status=status.HTTP_200_OK)
        
        return Response({"error": "No invoices found"}, status=status.HTTP_404_NOT_FOUND)


def repeat_to_at_least_length(s, wanted):
    if wanted >= 0:
        return s * (wanted//len(s))
    return ''

def remove_accents(text):
    nfd = unicodedata.normalize('NFD', str(text))
    s = ''.join(c for c in nfd if unicodedata.category(c) != 'Mn')
    allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,-/()')
    return ''.join(c if c in allowed else ' ' for c in s)

def normalize_text(content, length):
    content = str(content)
    return (content[:length]).ljust(length)

def get_total_homes(invoice, contract):
    meter = contract.supply_point_default.meter
    supply_points_contracts = SupplyPoint.objects.filter(meter=meter, contract__isnull=False).distinct()
    return supply_points_contracts.count()

def get_address(invoice, contract):
    text = ""
    if contract:
        address = contract.supply_point_default.address
        street = address.street   #50
        number =  address.street_number.number if address.street_number and address.street_number.number else '' #2
        floor = address.floor if address.floor else '' #2
        door = address.door if address.door else '' #2
        stair = address.stair if address.stair else '' #2
        postal_code = address.postal_code if address.postal_code else '' #5
        #city =  (address.province.name).upper() if address.province else '' #2
        city =  invoice.exploitation.name.upper() if invoice.exploitation else '' #2
        street_type = street.type.aca_abbreviation if street.type and street.type.aca_abbreviation else "CR"
        
        text += normalize_text((street_type).upper() + (street.name).upper(), 52)
        text += normalize_text(number, 7)
        text += normalize_text(floor, 2)
        text += normalize_text(door, 2)
        text += normalize_text(stair, 2)
        text += normalize_text(postal_code, 5)
        text += normalize_text(city, 25)
        
        return text
        
    return normalize_text(text,95)

def get_price_rate(self, invoice, line_items_canon):
    
    """ 
    "Q" PELS USOS RAMADERS SENSE CÀNON D'AIGUA O PER QUOTA
    "D" PELS USOS DOMÈSTICS
    "I" PELS USOS INDUSTRIALS
    "A" PELS USOS DE LA MUNICIPALITAT
    "E" PER ALTRES USOS EXEMPTS
    "M" PELS MESURAMENTS DIRECTES
    """
    
    contract = invoice.contract if invoice.contract else invoice.contract_request
    # print("contract: ", contract.token)
    if contract and contract.use_aca:
        # print("contract.use_aca: ", contract.use_aca)
        return contract.use_aca
    if contract and contract.use_type:
        if contract.use_type.token == self.contract_domestic_use_type_token:
            return "D"
        elif (contract.use_type.token == self.contract_industrial_use_type_token or contract.use_type.token == self.contract_comercial_use_type_token):
            return "A" if len(line_items_canon.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()) == 1 else "I"
        elif contract.use_type.token == self.contract_municipal_use_type_token:
            return "A" if len(line_items_canon.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()) == 1 else "I" # SI NOMÉS TÉ GENERAL, ÉS MUNICIPAL
        elif contract.use_type.token == self.contract_keeper_use_type_token:
            return "A" if len(line_items_canon.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()) == 1 else "I" #Q
    print("should be domestic: ", any(line_item.interval > 1 for line_item in line_items_canon))
    return "D" if any(line_item.interval > 0 for line_item in line_items_canon) else "A" if len(line_items_canon.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()) == 1 else "I" #"E" #check what value should be here in case of no contract or different situations

def get_clean_serie_final(invoice, meter_count):
    clean_invoice = invoice.serie_final.replace('/','')
    """ if '/' in invoice.serie_final:
        clean_invoice = clean_invoice[4:]
    else:
        clean_invoice = f"{invoice.issue_date.strftime('%m%Y')[1:]}{clean_invoice[:-7]}" """
    clean_invoice = f"{meter_count:02}{clean_invoice[:2]}{clean_invoice[-6:]}"
    return clean_invoice

def get_meter_type(self, invoice, contract):
    
    """ 
    "C" - COMPTADOR INDIVIDUAL
    "G" - COMPTADOR GENERAL
    "A" - AFORAMENTS
    "O" - ALTRES
    """
    token_meter_status_no_meter = self.token_meter_status_no_meter
    meter = None
    if contract:
        meter = contract.supply_point_default.meter if contract.supply_point_default else None
    if not meter or meter.status.token == token_meter_status_no_meter:
        return "A"
    if meter.is_general or contract.variables.filter(type__token="general").exists():
        return "G"
    if contract.supply_points.count() == 1:
        return "C"
    return "O"

def get_total_line_items(line_items):
    return round(abs(sum(line_item.price for line_item in line_items)), 2)


def _aggregate_canon_line_items(line_items_list, is_domestic):
    """
    Aggregate canon line items by (line_item_type, price_unit) and, for domestic,
    also by interval. Sums units and price so that repeated meter+line_item_type+price_unit
    are shown as a single line with combined total.
    For domestic contracts, if canon lines share the same (interval) but
    have different price_unit (e.g. positive/negative adjustments), merge them by interval:
    keep units (they should match), sum price, and **preserve the original price_unit**
    instead of recomputing it from the aggregated total, to avoid small rounding changes.
    Returns a list of SimpleNamespace(units, price_unit, price, line_item_type, interval).
    """
    if not line_items_list:
        return []

    groups = defaultdict(
        lambda: {"units": None, "price": 0.0, "price_unit": None, "line_item_type": None, "interval": None}
    )

    for li in line_items_list:
        if is_domestic:
            # Group domestic canon by interval only (ignore type/price_unit differences)
            key = (li.units or 0, li.interval or 0)
        else:
            key = (li.line_item_type_id or 0, float(li.price_unit or 0))
        g = groups[key]

        if is_domestic:
            # For domestic, units for same interval should be the same; keep first seen.
            if g["units"] is None:
                g["units"] = float(li.units or 0)
        else:
            if g["units"] is None:
                g["units"] = 0.0
            g["units"] += float(li.units or 0)

        g["price"] += float(li.price or 0)
        g["name"] = li.name
        if g["line_item_type"] is None:
            g["line_item_type"] = li.line_item_type
            g["price_unit"] = li.price_unit
            g["interval"] = li.interval

    result = []
    for g in groups.values():
        units = g["units"] if g["units"] is not None else 0.0
        if is_domestic:
            # Preserve the original unit price for domestic contracts to avoid
            # changing it due to rounding differences between total/units.
            price_unit = g["price_unit"] or 0.0
        else:
            price_unit = g["price_unit"]
        result.append(
            SimpleNamespace(
                units=units,
                price_unit=price_unit,
                price=g["price"],
                line_item_type=g["line_item_type"],
                interval=g["interval"],
                name=g["name"],
            )
        )
    return result


def get_canon_line_items(self, invoice, line_items, contract, total_leak, refactored_invoice, price_rate_letter):
    content = ''
    #POS 426 TO 436?
    debt_vulnerable_token = self.debt_vulnerable_token
    tarifa_social_token = self.tarifa_social_token
    
    #watch out!!! using for now since no price rate is calculating leak by intervals
    line_items = line_items.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()
    if contract and ((contract.use_type and contract.use_type.token == self.contract_domestic_use_type_token) or contract.use_aca == "D"):
        line_items = line_items.exclude(line_item_type__quantity__token="diferencia_fuita").distinct()
    # print("line_items: ", line_items)

    original_list = list(line_items)
    is_domestic = price_rate_letter == "D"
    aggregated = _aggregate_canon_line_items(original_list, is_domestic)
    line_item_len = len(aggregated)
    # print("aggregated: ", aggregated)

    extra_line_item_info = 4 - line_item_len
    volume_billed = 0
    price_rate_billed = 0

    if contract:
        not_in_any_type = False
        if not contract.use_aca:
            if contract.use_type:
                if contract.use_type.token != self.contract_domestic_use_type_token and contract.use_type.token != self.contract_industrial_use_type_token and contract.use_type.token != self.contract_municipal_use_type_token and contract.use_type.token != self.contract_comercial_use_type_token and contract.use_type.token != self.contract_keeper_use_type_token:
                    not_in_any_type = True
            else:
                not_in_any_type = True
        else:
            if contract.use_aca == "M":
                return content + repeat_to_at_least_length('0', 236)
        
        if is_domestic:
            # print("domestic")
            len_volume = 9
            len_price_rate = 9
            
            value_to_add_social = False

            
            for line_item in original_list:
                for adj in line_item.adjustments.all():
                    for cond in adj.adjustment.conditions.all():
                        if (
                            cond.quantity 
                            and 'value' in cond.quantity 
                            and cond.quantity['value'] == f"variable.{tarifa_social_token}"
                            and cond.operation != "is_null" # pot tenir la variable per "negar-la", per validar que és null
                            ):
                            value_to_add_social = True
            
            #START POS - 264/298/332/366 END 400
            for line_item in sorted(aggregated, key=lambda x: (x.interval or x.price_unit or 0)):
                used_units = abs(int(line_item.units))
                if value_to_add_social and line_item.price_unit == 0:
                    used_units = 0
                units_str = repeat_to_at_least_length('0', len_volume-len(str(used_units))) 
                if refactored_invoice:
                    units_str = '-' + units_str[1:] if units_str.startswith('0') else units_str
                content += units_str
                content += str(used_units)
                
                price_unit_split = str(round(line_item.price_unit or 0, 4)).split('.') if abs(int(line_item.units)) > 0 else ['0', '0']
                content += repeat_to_at_least_length('0', 3-len(price_unit_split[0]))
                content += price_unit_split[0]
                try:
                    content += price_unit_split[1]
                    content += repeat_to_at_least_length('0', 6-len(price_unit_split[1]))
                except:
                    content += repeat_to_at_least_length('0', 6)

                total_split = str(round(abs(line_item.price or 0), 2)).split('.')
                total_split_str = repeat_to_at_least_length('0', 12-len(total_split[0]))
                if refactored_invoice:
                    total_split_str = '-' + total_split_str[1:] if total_split_str.startswith('0') else total_split_str
                content += total_split_str
                content += total_split[0]
                try:
                    content += total_split[1]
                    content += repeat_to_at_least_length('0', 4-len(str((total_split[1]))))
                except:
                    content += repeat_to_at_least_length('0', 4)
            if extra_line_item_info > 0:
                for i in range(extra_line_item_info):
                    content += repeat_to_at_least_length('0', len_volume)
                    content += repeat_to_at_least_length('0', 9)
                    content += repeat_to_at_least_length('0', 16)
            
            

            #START AT 400 END AT 426
            #should negative be added????¿?¿ (No found examples of negative values here)
            # content += "|"
            total_price_lineitems = get_total_line_items(original_list)
            
            if (value_to_add_social and total_price_lineitems == 0):
                
                total_consumption = sum(abs(int(li.units or 0)) for li in original_list)
                # if line_item_len > 1:
                #     total_consumption = 0
                len_consumption = 5 - len(str(int(total_consumption)))
                
                total_consumption_str = repeat_to_at_least_length('0', len_consumption) + str(int(total_consumption))
                total_final_units_str = repeat_to_at_least_length('0', 9)
                if refactored_invoice:
                    total_consumption_str = '-' + total_consumption_str[1:] if total_consumption_str.startswith('0') else total_consumption_str
                    total_final_units_str = '-' + total_final_units_str[1:] if total_final_units_str.startswith('0') else total_final_units_str
                content += total_consumption_str
                content += repeat_to_at_least_length('0', 12)
                content += total_final_units_str
                content += repeat_to_at_least_length('0', 74)
            else:
                content += repeat_to_at_least_length('0', 5)
                content += repeat_to_at_least_length('0', 9)
                content += repeat_to_at_least_length('0', 12)
                content += repeat_to_at_least_length('0', 74)
            # content += "|"
            return content
        
        elif (contract.use_type and (contract.use_type.token == self.contract_industrial_use_type_token or contract.use_type.token == self.contract_municipal_use_type_token or contract.use_type.token == self.contract_comercial_use_type_token or contract.use_type.token == self.contract_keeper_use_type_token)) or not_in_any_type or contract.use_aca in ["I", "A"]:
            # print("industrial")
            content += repeat_to_at_least_length('0', 162)
            len_volume = 12

            for line_item in sorted(aggregated, key=lambda x: (x.price_unit), reverse=True):
                line_units_str = repeat_to_at_least_length('0', len_volume-len(str(abs(int(line_item.units)))))
                if refactored_invoice:
                    line_units_str = '-' + line_units_str[1:] if line_units_str.startswith('0') else line_units_str
                
                content += line_units_str
                content += str(abs(int(line_item.units)))

                price_unit_split = str(round(line_item.price_unit or 0, 4)).split('.') if round(abs(line_item.price or 0), 2) > 0 or abs(int(line_item.units)) > 0 else str(round(0, 4)).split('.')
                content += repeat_to_at_least_length('0', 3-len(price_unit_split[0]))
                content += price_unit_split[0]
                try:
                    content += price_unit_split[1]
                    content += repeat_to_at_least_length('0', 6-len(price_unit_split[1]))
                except:
                    content += repeat_to_at_least_length('0', 6)

                total_split = str(round(abs(line_item.price or 0), 2)).split('.')
                line_total_split_str = repeat_to_at_least_length('0', 12-len(total_split[0]))
                if refactored_invoice:
                    line_total_split_str = '-' + line_total_split_str[1:] if line_total_split_str.startswith('0') else line_total_split_str
                
                content += line_total_split_str
                content += total_split[0]
                try:
                    content += total_split[1] 
                    content += repeat_to_at_least_length('0', 4-len(total_split[1]))
                except:
                    content += repeat_to_at_least_length('0', 4)
            
            for i in range(2 - line_item_len):
                content += repeat_to_at_least_length('0', 37)
                
            
            """ if line_item_len == 1:
                content += repeat_to_at_least_length('0', 37)
            if line_item_len == 0:
                content += repeat_to_at_least_length('0', 73) #??? """

            return content
    print("none")
    return content + repeat_to_at_least_length('0', 236)
            