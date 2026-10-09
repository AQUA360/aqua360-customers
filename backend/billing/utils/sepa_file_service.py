from decimal import Decimal
from datetime import datetime, timedelta, date
import uuid
import xml.etree.ElementTree as ET
from decouple import config
from django.utils import timezone
import re
from django.utils.translation import gettext as _
from coredata.models import Bank, ConfigProject
from coredata.utils.iban_validator_utils import get_spanish_bic
from pricing.models import ProductOrigin
from service.models import Exploitation
from service.serializers.company_serializer import CompanySerializer
from faker import Faker
fake = Faker()
from schwifty import IBAN as SchwiftyIBAN

def generate_payment_remittance_ident_msg(vat):
    """
    Build MsgId as {vat}{YYYYMMDD}{NNN}, where NNN is 1 + the highest
    existing PaymentRemittance.token sequence for the same vat+date prefix.
    """
    from billing.models import PaymentRemittance

    base_token = f"{vat}{datetime.now().strftime('%Y%m%d')}"
    existing_tokens = PaymentRemittance.objects.filter(
        token__startswith=base_token
    ).values_list('token', flat=True)

    max_seq = 0
    prefix_len = len(base_token)
    for token in existing_tokens:
        if not token:
            continue
        suffix = token[prefix_len:]
        if suffix.isdigit():
            max_seq = max(max_seq, int(suffix))

    return f"{base_token}{max_seq + 1:03d}"

def get_sepa_signature_date(payment):
    """
    Returns the SEPA signature date for a payment.
    The logic follows: contract -> payment -> sepa_document -> updated_at/created_at
    Fallback: contract -> payment -> IBAN -> updated_at/created_at
    """
    try:
        # Get contract from payment (either directly or via commitment_deposit)
        contract = getattr(payment, 'contract', None)
        if not contract and hasattr(payment, 'commitment_deposit') and payment.commitment_deposit:
            contract = payment.commitment_deposit.contract
        
        if contract and contract.payment:
            # Priority 1: sepa_document in contract.payment
            if hasattr(contract.payment, 'sepa_document'):
                sepa_doc = contract.payment.sepa_document
                if sepa_doc:
                    sig_date = sepa_doc.updated_at or sepa_doc.created_at
                    if sig_date:
                        return sig_date.strftime("%Y-%m-%d")

            # Priority 2: IBAN object in contract.payment
            if hasattr(contract.payment, 'IBAN') and contract.payment.IBAN:
                iban_obj = contract.payment.IBAN
                sig_date = getattr(iban_obj, 'updated_at', None) or getattr(iban_obj, 'created_at', None)
                if sig_date:
                    return sig_date.strftime("%Y-%m-%d")

    except Exception as e:
        # Silently fail and return None to use fallback logic
        pass
    return None

def generate_xml(self, document, document_data, bank_instance):
        root = ET.Element("Document", {
            "xmlns": "urn:iso:std:iso:20022:tech:xsd:pain.008.001.02",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"
        })
        date_time = (datetime.now() + timedelta(days=1)).strftime('%Y%m%d%H%M%S') 
        exploitation = Exploitation.objects.filter(is_active=True).first()
        
        if (exploitation.company.company_banks.count() == 0):
            raise Exception("Company has no banks")

        bank = bank_instance
        cstmrCdtTrfInitn = ET.SubElement(root, "CstmrDrctDbtInitn")
        grpHdr = ET.SubElement(cstmrCdtTrfInitn, "GrpHdr")

        #TODO: If there's more than one exploitation in the payments document, fix the conflict
        #Get the existing exploitation company CIF for the moment
        uuid_str = str(uuid.uuid4())
        unique_value = "".join(
                str((int(c, 16) % 10) + 1) if c in "0123456789abcdef" else c
                for c in uuid_str
            )[:10]

        from billing.views.sepa_payment_document_generate_view import calculate_control_code
        ident = "ES" + calculate_control_code(exploitation.company.vat) + '001' + exploitation.company.vat
        ident_msg = f"{exploitation.company.vat}{datetime.now().strftime('%Y%m%d')}{unique_value}"
        
        document.msgId = ident_msg
        document.save()
        ET.SubElement(grpHdr, "MsgId").text = ident_msg
        ET.SubElement(grpHdr, "CreDtTm").text = datetime.now().strftime("%Y-%m-%dT%H:%M:%S:%f")[:-4]
        
        total_transactions = sum(len(line.payments.all()) for line in document.lines.all())
        ET.SubElement(grpHdr, "NbOfTxs").text = str(total_transactions)

        total_amount = sum(data['amount'] for iban, customers in document_data.items() for customer_token, data in customers.items())
        ET.SubElement(grpHdr, "CtrlSum").text = f"{total_amount:.2f}"

        #InitgPty
        initg_pty = ET.SubElement(grpHdr, "InitgPty")
        ET.SubElement(initg_pty, "Nm").text = exploitation.company.alias
        initg_id = ET.SubElement(initg_pty, "Id")
        initg_prvt_id = ET.SubElement(initg_id, "PrvtId")
        initg_other = ET.SubElement(initg_prvt_id, "Othr")
        ET.SubElement(initg_other, "Id").text = bank.sepa_cred_identifier
        initg_schmenm =ET.SubElement(initg_other, "SchmeNm")
        ET.SubElement(initg_schmenm, "Prtry").text = "SEPA"
        ET.SubElement(initg_other, "Issr").text = "ISO"
        #END GrpHdr
        
        #PmtInf
        #PmtInfId
        pmtInf = ET.SubElement(cstmrCdtTrfInitn, "PmtInf")
        ET.SubElement(pmtInf, "PmtInfId").text = ident[:25]
        ET.SubElement(pmtInf, "PmtMtd").text = "DD"
        ET.SubElement(pmtInf, "NbOfTxs").text = str(total_transactions)
        ET.SubElement(pmtInf, "CtrlSum").text = f"{total_amount:.2f}"

        pmtTpInf = ET.SubElement(pmtInf, "PmtTpInf")
        svcLvl = ET.SubElement(pmtTpInf, "SvcLvl")
        ET.SubElement(svcLvl, "Cd").text = "SEPA"  
        lclinstrm = ET.SubElement(pmtTpInf, "LclInstrm")
        ET.SubElement(lclinstrm, "Cd").text = "CORE"
        ET.SubElement(pmtTpInf, "SeqTp").text = "RCUR"
        #END PmtInfId

        ET.SubElement(pmtInf, "ReqdColltnDt").text = date_time
        cdtr = ET.SubElement(pmtInf, "Cdtr")
        ET.SubElement(cdtr, "Nm").text = exploitation.company.alias
        
        """ pstlAdr = ET.SubElement(cdtr, "PstlAdr")
        ET.SubElement(pstlAdr, "Ctry").text = "ES"
        ET.SubElement(pstlAdr, "AdrLine").text = f"{exploitation.company.address}, {exploitation.company.location}" """

        cdtr_acct = ET.SubElement(pmtInf, "CdtrAcct")
        cdtr_acct_id = ET.SubElement(cdtr_acct, "Id")
        ET.SubElement(cdtr_acct_id, "IBAN").text = bank.iban

        cdtr_agt = ET.SubElement(pmtInf, "CdtrAgt")
        fin_instn_id = ET.SubElement(cdtr_agt, "FinInstnId")
        ET.SubElement(fin_instn_id, "BIC").text = bank.swift

        chrg_br = ET.SubElement(pmtInf, "ChrgBr")
        chrg_br.text = "SLEV"

        cdtr_schme_id = ET.SubElement(pmtInf, "CdtrSchmeId")
        id_element = ET.SubElement(cdtr_schme_id, "Id")
        prvt_id = ET.SubElement(id_element, "PrvtId")
        othr = ET.SubElement(prvt_id, "Othr")
        ET.SubElement(othr, "Id").text = bank.sepa_cred_identifier
        schmeNm = ET.SubElement(othr, "SchmeNm")
        ET.SubElement(schmeNm, "Prtry").text = "SEPA"
        
        ident=0
        for iban, customers in document_data.items():
            for customer_token, data in customers.items():
                ident += 1
                drct_dbt_tx_inf = ET.SubElement(pmtInf, "DrctDbtTxInf")
                pmtId = ET.SubElement(drct_dbt_tx_inf, "PmtId")
                end_to_end_id = f"{date_time}_{customer_token}_{unique_value}"
                ET.SubElement(pmtId, "InstrId").text = end_to_end_id
                ET.SubElement(pmtId, "EndToEndId").text = end_to_end_id

                amount = Decimal(str(data["amount"]))
                instdAmt = ET.SubElement(
                    drct_dbt_tx_inf, "InstdAmt", {"Ccy": "EUR"}
                )
                instdAmt.text = f"{amount:.2f}"

                drct_dbt_tx = ET.SubElement(drct_dbt_tx_inf, "DrctDbtTx")
                mndt_rltd_inf = ET.SubElement(drct_dbt_tx, "MndtRltdInf")
                ET.SubElement(mndt_rltd_inf, "MndtId").text = customer_token
                
                # Get signature date from contract sepa document if possible
                from billing.models import Payment
                sig_date_str = None
                payment_id = data.get('payment_ids', [None])[0]
                if payment_id:
                    payment_item = Payment.objects.filter(id=payment_id).first()
                    if payment_item:
                        sig_date_str = get_sepa_signature_date(payment_item)
                
                if not sig_date_str:
                    sig_date_str = datetime.now().strftime("%Y-%m-%d")

                ET.SubElement(mndt_rltd_inf, "DtOfSgntr").text = sig_date_str

                dbtr = ET.SubElement(drct_dbt_tx_inf, "Dbtr")
                ET.SubElement(dbtr, "Nm").text = data["tax_name"]

                iban_country = data["iban"][:2].upper() if data.get("iban") else ""
                non_eea_sepa_countries = ['GB', 'CH', 'GI', 'JE', 'GG', 'IM', 'MC', 'SM', 'VA'] # removed AD for now
                
                if iban_country in non_eea_sepa_countries:
                    dbtr_adr = ET.SubElement(dbtr, "PstlAdr")
                    
                    country_code = data.get("country_code") or data.get("country") or iban_country
                    ET.SubElement(dbtr_adr, "Ctry").text = country_code[:2].upper()
                    
                    if data.get("postal_code"):
                        town = data.get("city") or data.get("location") or "Unknown"
                        ET.SubElement(dbtr_adr, "AdrLine").text = f"{data['postal_code'][:16]} {town[:35]}"
                        
                    # ET.SubElement(dbtr_adr, "TwnNm").text = town[:35]
                    
                    if data.get("address"):
                        ET.SubElement(dbtr_adr, "AdrLine").text = data["address"][:70]

                dbtr_acct = ET.SubElement(drct_dbt_tx_inf, "DbtrAcct")
                dbtr_acct_id = ET.SubElement(dbtr_acct, "Id")
                
                is_iban = data["iban"] and re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$', data["iban"])
                if is_iban:
                    ET.SubElement(dbtr_acct_id, "IBAN").text = data["iban"]
                else:
                    othr = ET.SubElement(dbtr_acct_id, "Othr")
                    ET.SubElement(othr, "Id").text = data["iban"]

                #OPTIONAL?
                rmtInf = ET.SubElement(drct_dbt_tx_inf, "RmtInf")
                ET.SubElement(rmtInf, "Ustrd").text = f"FRA  {customer_token}"
                

        xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')
        return xml_string
    

def generate_xml_payments(payments, bank_instance, send_date, is_return=False):
        def to_local_date(value):
            if not value:
                return None
            if isinstance(value, datetime):
                if timezone.is_aware(value):
                    value = timezone.localtime(value)
                return value.date()
            if isinstance(value, date):
                return value
            return None

        try:
            origin_reading_token = ConfigProject.objects.get(token='origin_reading_token').value
            payment = payments.first()
            today = timezone.localdate()
            send_date_strf = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            is_unique = True
            
            if any(payment.invoice and payment.invoice.origin.token == origin_reading_token for payment in payments):
                is_unique = False
            if send_date:
                if isinstance(send_date, str):
                    send_date_obj = datetime.strptime(send_date, '%Y-%m-%d')
                else:
                    send_date_obj = send_date
                send_date_strf = send_date_obj.strftime('%Y-%m-%d')
            else:
                if payment.invoice:
                    send_at_date = to_local_date(payment.invoice.send_at)
                    if send_at_date and send_at_date >= today:
                        send_date_strf = send_at_date.strftime('%Y-%m-%d')
                    else:
                        due_date_date = to_local_date(payment.invoice.due_date)
                        if due_date_date and due_date_date >= today:
                            send_date_strf = due_date_date.strftime('%Y-%m-%d')
                elif payment.due_date and payment.due_date.date() >= today:
                    send_date_strf = payment.due_date.strftime('%Y-%m-%d')
            
        except Exception as e:
            print("error: ", e)
            if send_date:
                if isinstance(send_date, str):
                    send_date_obj = datetime.strptime(send_date, '%Y-%m-%d')
                else:
                    send_date_obj = send_date
                send_date_strf = send_date_obj.strftime('%Y-%m-%d')
            else:
                send_date_strf = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d') 
        print("send date string: ", send_date_strf)
        pain_type = "pain.008.001.02" if not is_return else "pain.001.001.03"
        root = ET.Element("Document", {
            "xmlns": f"urn:iso:std:iso:20022:tech:xsd:{pain_type}",
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance"
        })
        exploitation = payments.first().invoice.exploitation if payments.first().invoice else payments.first().commitment_deposit.contract.supply_point_default.connection.exploitation if payments.first().commitment_deposit else payments.first().contract.supply_point_default.connection.exploitation if payments.first().contract and payments.first().contract.supply_point_default else None
        if not exploitation:
            exploitation = Exploitation.objects.filter(is_active=True).first()

        if not bank_instance:
            raise Exception("Company has no banks")

        # L'empresa emissora surt del compte amb que es remesa, no de
        # l'explotacio: hi ha explotacions que serveixen mes d'una empresa i
        # `exploitation.company` sempre en donaria la mateixa. Cada banc genera
        # el seu fitxer, per tant el banc es qui determina de manera coherent el
        # titular (Cdtr/Dbtr), el NIF i l'identificador de creditor del fitxer.
        company = bank_instance.company or (exploitation.company if exploitation else None)
        if not company:
            raise Exception("Company bank has no company")

        #company_address_ser = CompanySerializer(company).data
        company_address = None
        if company.address and company.address.street:
            company_address = f"{company.address.street.name}"
            if company.address.street_number:
                company_address = f"{company_address}, {str(company.address.street_number)}"

        bank = bank_instance
        cstmrCdtTrfInitn = ET.SubElement(root, "CstmrDrctDbtInitn") if not is_return else ET.SubElement(root, "CstmrCdtTrfInitn")
        grpHdr = ET.SubElement(cstmrCdtTrfInitn, "GrpHdr")

        from billing.views.sepa_payment_document_generate_view import calculate_control_code
        ident = "ES" + calculate_control_code(company.vat) + '001' + company.vat
        ident_msg = generate_payment_remittance_ident_msg(company.vat)
        
        ET.SubElement(grpHdr, "MsgId").text = ident_msg
        ET.SubElement(grpHdr, "CreDtTm").text = datetime.now().isoformat()
        
        total_transactions = len(payments)
        ET.SubElement(grpHdr, "NbOfTxs").text = str(total_transactions)

        total_amount = sum(payment.amount for payment in payments)
        ET.SubElement(grpHdr, "CtrlSum").text = f"{total_amount:.2f}"

        #InitgPty
        initg_pty = ET.SubElement(grpHdr, "InitgPty")
        ET.SubElement(initg_pty, "Nm").text = company.alias
        initg_id = ET.SubElement(initg_pty, "Id")
        initg_prvt_id = ET.SubElement(initg_id, "PrvtId")
        initg_other = ET.SubElement(initg_prvt_id, "Othr")
        ET.SubElement(initg_other, "Id").text = bank.sepa_cred_identifier
        initg_schmenm =ET.SubElement(initg_other, "SchmeNm")
        ET.SubElement(initg_schmenm, "Prtry").text = "SEPA"
        ET.SubElement(initg_other, "Issr").text = "ISO"
        #END GrpHdr
        
        #PmtInf
        #PmtInfId
        pmtInf = ET.SubElement(cstmrCdtTrfInitn, "PmtInf")
        ET.SubElement(pmtInf, "PmtInfId").text = ident_msg #ident[:25]
        ET.SubElement(pmtInf, "PmtMtd").text = "DD" if not is_return else "TRF"
        ET.SubElement(pmtInf, "BtchBookg").text = "false"
        ET.SubElement(pmtInf, "NbOfTxs").text = str(total_transactions)
        ET.SubElement(pmtInf, "CtrlSum").text = f"{total_amount:.2f}"

        pmtTpInf = ET.SubElement(pmtInf, "PmtTpInf")
        svcLvl = ET.SubElement(pmtTpInf, "SvcLvl")
        ET.SubElement(svcLvl, "Cd").text = "SEPA"  
        lclinstrm = ET.SubElement(pmtTpInf, "LclInstrm")
        ET.SubElement(lclinstrm, "Cd").text = "CORE" if not is_return else "DIVI"
        # ET.SubElement(pmtTpInf, "SeqTp").text = "OOFF" if is_unique else "RCUR"
        if not is_return:
            ET.SubElement(pmtTpInf, "SeqTp").text = "RCUR"
        #END PmtInfId

        if is_return:
            ET.SubElement(pmtInf, "ReqdExctnDt").text = send_date_strf
        else:
            ET.SubElement(pmtInf, "ReqdColltnDt").text = send_date_strf
        
        if not is_return:
            cdtr = ET.SubElement(pmtInf, "Cdtr")
            ET.SubElement(cdtr, "Nm").text = company.alias

            """ pstlAdr = ET.SubElement(cdtr, "PstlAdr")
            ET.SubElement(pstlAdr, "Ctry").text = "ES"
            ET.SubElement(pstlAdr, "AdrLine").text = company_address """

            cdtr_acct = ET.SubElement(pmtInf, "CdtrAcct")
            cdtr_acct_id = ET.SubElement(cdtr_acct, "Id")
            ET.SubElement(cdtr_acct_id, "IBAN").text = bank.iban

            cdtr_agt = ET.SubElement(pmtInf, "CdtrAgt")
            fin_instn_id = ET.SubElement(cdtr_agt, "FinInstnId")
            ET.SubElement(fin_instn_id, "BIC").text = bank.swift

            chrg_br = ET.SubElement(pmtInf, "ChrgBr")
            chrg_br.text = "SLEV"

            cdtr_schme_id = ET.SubElement(pmtInf, "CdtrSchmeId")
            id_element = ET.SubElement(cdtr_schme_id, "Id")
            prvt_id = ET.SubElement(id_element, "PrvtId")
            othr = ET.SubElement(prvt_id, "Othr")
            ET.SubElement(othr, "Id").text = bank.sepa_cred_identifier
            schmeNm = ET.SubElement(othr, "SchmeNm")
            ET.SubElement(schmeNm, "Prtry").text = "SEPA"
        else:
            dbtr = ET.SubElement(pmtInf, "Dbtr")
            ET.SubElement(dbtr, "Nm").text = company.alias
            
            dbtr_id = ET.SubElement(dbtr, "Id")
            prvt_id = ET.SubElement(dbtr_id, "PrvtId")
            prvt_other = ET.SubElement(prvt_id, "Othr")
            ET.SubElement(prvt_other, "Id").text = company.vat
            schmeNm = ET.SubElement(prvt_other, "SchmeNm")
            ET.SubElement(schmeNm, "Prtry").text = "SEPA"
            
            dbtr_acct = ET.SubElement(pmtInf, "DbtrAcct")
            dbtr_acct_id = ET.SubElement(dbtr_acct, "Id")
            ET.SubElement(dbtr_acct_id, "IBAN").text = bank.iban
            
            dbtr_agt = ET.SubElement(pmtInf, "DbtrAgt")
            fin_instn_id = ET.SubElement(dbtr_agt, "FinInstnId")
            ET.SubElement(fin_instn_id, "BIC").text = bank.swift
            
            ET.SubElement(pmtInf, "ChrgBr").text = "SLEV"
            

        
        language = config('LANGUAGE', default="ca")
        origin_water = ProductOrigin.objects.get(token='aigua')
        
        # Track mandate ids already used. Same mandate id is allowed only if IBAN is the same.
        # If the same base mandate id appears with different IBANs, we assign a stable suffix per IBAN.
        mndt_id_to_iban = {}
        mndt_id_iban_to_assigned = {}
        mndt_id_suffix_counters = {}
        used_mndt_ids = set()
        
        ident=0
        for payment in payments:
            ident += 1
            customer_token = payment.payer_token_final if payment.payer_token_final else payment.customer_token_final
            customer_name = payment.payer_final if payment.payer_final else payment.customer_final
            customer_name = customer_name.replace("&", "N")
            address_final = payment.address_final
            location_final = payment.location_final
            payment_bank_final = payment.payment_bank
            if payment_bank_final is None:
                payment_bank_final = ""
            elif not isinstance(payment_bank_final, str):
                payment_bank_final = str(payment_bank_final)
            payment_bank_final = payment_bank_final.strip()
            bank_swift = payment.payment_swift
            
            """ payment_send_date = payment.invoice.send_at if payment.invoice and payment.invoice.send_at else payment.due_date if payment.due_date else payment.payment_date if payment.payment_date else datetime.now()
            
            send_date_aware = timezone.make_aware(send_date) if send_date else None
            # turn both dates to datetime.date to compare
            payment_send_date_date = payment_send_date.date() if isinstance(payment_send_date, datetime) else payment_send_date
            send_date_aware_date = send_date_aware.date() if isinstance(send_date_aware, datetime) else send_date_aware
            
            if not payment_send_date or (
                send_date_aware and payment_send_date_date < send_date_aware_date
            ):
                payment_send_date = send_date_aware """
            
            # PAYMENT SEND DATE IS NOT USED TO SEND PAYMENTS, BUT TO DECLARE WHEN SEPA IS SIGNED (WHOOPS)
            payment_send_date = send_date_strf
            
            if payment.commitment_deposit:
                if language == "ca":
                    title = f"COMPROMÍS DE PAGAMENT {payment.commitment_deposit.token}"
                elif language == "es":
                    title = f"COMPROMISO DE PAGAMENTO {payment.commitment_deposit.token}"
                else:
                    title = f"PAYMENT COMMITMENT {payment.commitment_deposit.token}"
            if payment.invoice:
                title = payment.invoice.serie_final
                if payment.invoice.contract and payment.invoice.origin == origin_water:
                    if language == "ca":
                        title = f"AIGUA CONTRACTE {payment.invoice.contract.token}"
                    elif language == "es":
                        title = f"AGUA CONTRATO {payment.invoice.contract.token}"
                    else:
                        title = f"WATER CONTRACT {payment.invoice.contract.token}"
            if is_return:
                title = f"{_('Return xml msg')} {payment.contract.token if payment.contract else payment.person.token if payment.person else payment.token}"
            
            if not bank_swift or len(bank_swift) == 0:
                inv_com = payment.invoice if payment.invoice else payment.commitment_deposit if payment.commitment_deposit else None
                if inv_com:
                    if inv_com.contract and inv_com.contract.payment and inv_com.contract.payment.IBAN:
                        if inv_com.contract.payment.IBAN.iban == payment_bank_final:
                            if inv_com.contract.payment.IBAN.swift:
                                bank_swift = inv_com.contract.payment.IBAN.swift
                            else:
                                bank_swift = None
            is_spanish_iban = payment_bank_final and payment_bank_final.startswith('ES')

            if is_spanish_iban and (not bank_swift or len(bank_swift) == 0):
                bank_token = payment_bank_final[4:8]
                
                try:
                    bank_swift = Bank.objects.get(token=bank_token).bic
                except Exception as e:
                    try:
                        bank_swift = Bank.objects.get(token=int(bank_token)).bic
                    except Exception as e:
                        bank_swift = None
            
            if not bank_swift and payment_bank_final:
                try:
                    schwifty_bank = SchwiftyIBAN(payment_bank_final)
                    bank_swift = str(schwifty_bank.bic)
                    print("bank_swift from schwifty: ", bank_swift)
                except Exception:
                    bank_swift = None

            # Un BIC incomplet (el catàleg i les factures antigues porten "BSAB") es completava a cegues
            # amb "ESMMXXX": si el registre oficial coneix l'entitat, es fa servir el seu BIC.
            if is_spanish_iban and bank_swift and len(bank_swift.strip()) not in (8, 11):
                bank_swift = get_spanish_bic(payment_bank_final[4:8]) or bank_swift
            
            if bank_swift and len(bank_swift) > 0:
                if is_spanish_iban:
                    if len(bank_swift) == 4:
                        bank_swift = f"{bank_swift}ESMMXXX"
                    elif len(bank_swift) == 6:
                        bank_swift = f"{bank_swift}MMXXX"
                    elif len(bank_swift) == 8:
                        bank_swift = f"{bank_swift}XXX"
                else:
                    if len(bank_swift) == 8:
                        bank_swift = f"{bank_swift}XXX"



            if bank_swift and len(bank_swift) > 0:
                bank_swift = bank_swift.upper()
            
            drct_dbt_tx_inf = ET.SubElement(pmtInf, "DrctDbtTxInf") if not is_return else ET.SubElement(pmtInf, "CdtTrfTxInf")
            
            pmtId = ET.SubElement(drct_dbt_tx_inf, "PmtId")
            end_to_end_id = f"{payment.token}-{ident}"
            if not is_return:
                ET.SubElement(pmtId, "InstrId").text = end_to_end_id
            ET.SubElement(pmtId, "EndToEndId").text = end_to_end_id

            amount = Decimal(str(payment.amount))
            
            if not is_return:
                instAmt_parent = drct_dbt_tx_inf
            else:
                instAmt_parent = ET.SubElement(drct_dbt_tx_inf, "Amt")
            
            instdAmt = ET.SubElement(
                instAmt_parent, "InstdAmt", {"Ccy": "EUR"}
            )
            instdAmt.text = f"{amount:.2f}"

            debtor_iban = (payment_bank_final or "").strip().upper()

            if payment.contract and payment.contract.payment and payment.contract.payment.mandate_id:
                base_mndt_id = payment.contract.payment.mandate_id
            else:
                base_mndt_id = F"{customer_token}{payment.token}"

            mndt_id = base_mndt_id
            if base_mndt_id in mndt_id_to_iban:
                previous_iban = mndt_id_to_iban[base_mndt_id]
                if previous_iban != debtor_iban:
                    assigned = mndt_id_iban_to_assigned.get((base_mndt_id, debtor_iban))
                    if assigned:
                        mndt_id = assigned
                    else:
                        suffix = mndt_id_suffix_counters.get(base_mndt_id, 1)
                        mndt_id = f"{base_mndt_id}-{suffix}"
                        while mndt_id in used_mndt_ids:
                            suffix += 1
                            mndt_id = f"{base_mndt_id}-{suffix}"
                        mndt_id_suffix_counters[base_mndt_id] = suffix + 1
                        mndt_id_iban_to_assigned[(base_mndt_id, debtor_iban)] = mndt_id
            else:
                mndt_id_to_iban[base_mndt_id] = debtor_iban

            used_mndt_ids.add(mndt_id)
            if not is_return:
                drct_dbt_tx = ET.SubElement(drct_dbt_tx_inf, "DrctDbtTx")
                mndt_rltd_inf = ET.SubElement(drct_dbt_tx, "MndtRltdInf")
                ET.SubElement(mndt_rltd_inf, "MndtId").text = mndt_id
            
                # Get signature date from contract sepa document if possible
                sig_date_str = get_sepa_signature_date(payment)
                if not sig_date_str:
                    # if payment_send_date is not a date but a string, try to convert it to a date
                    if isinstance(payment_send_date, str):
                        print("payment_send_date is a string: ", payment_send_date)
                        try:
                            payment_send_date = datetime.strptime(payment_send_date, "%Y-%m-%d")
                        except:
                            raise Exception("payment_send_date is not a valid date")
                    sig_date_str = payment_send_date.strftime("%Y-%m-%d")

                ET.SubElement(mndt_rltd_inf, "DtOfSgntr").text = sig_date_str
                ET.SubElement(mndt_rltd_inf, "AmdmntInd").text = "false"
            
            # DBTRAGT
            dbtr_agt = ET.SubElement(drct_dbt_tx_inf, "DbtrAgt") if not is_return else ET.SubElement(drct_dbt_tx_inf, "CdtrAgt")
            fin_instn_id = ET.SubElement(dbtr_agt, "FinInstnId")
            if bank_swift:
                ET.SubElement(fin_instn_id, "BIC").text = bank_swift

            # DBTR
            dbtr = ET.SubElement(drct_dbt_tx_inf, "Dbtr") if not is_return else ET.SubElement(drct_dbt_tx_inf, "Cdtr")
            ET.SubElement(dbtr, "Nm").text = customer_name
            
            if not is_return:
                iban_country = payment_bank_final[:2].upper() if payment_bank_final else ""
                non_eea_sepa_countries = ['GB', 'CH', 'GI', 'JE', 'GG', 'IM', 'MC', 'SM', 'VA', 'AD']

                if iban_country in non_eea_sepa_countries:
                    dbtr_adr = ET.SubElement(dbtr, "PstlAdr")
                    
                    country_code = iban_country
                    town = location_final or "Unknown"
                    zip_code = None
                    
                    if payment.invoice:
                        country_code = payment.invoice.country_final or iban_country
                        town = payment.invoice.city_final or payment.invoice.location_final or town
                        zip_code = payment.invoice.postal_code_final

                    ET.SubElement(dbtr_adr, "Ctry").text = country_code[:2].upper()
                    
                    if zip_code:
                        ET.SubElement(dbtr_adr, "AdrLine").text = f"{str(zip_code)[:16]} {str(town)[:35]}"
                            
                        # ET.SubElement(dbtr_adr, "TwnNm").text = str(town)[:35]
                    
                    if address_final:
                        ET.SubElement(dbtr_adr, "AdrLine").text = str(address_final)[:70]
                
                dbtr_id = ET.SubElement(dbtr, "Id")
                dbtr_ord_id = ET.SubElement(dbtr_id, "OrgId")
                dbtr_other = ET.SubElement(dbtr_ord_id, "Othr")
                ET.SubElement(dbtr_other, "Id").text = customer_token
                dbtr_schemNm = ET.SubElement(dbtr_other, "SchmeNm")
                ET.SubElement(dbtr_schemNm, "Prtry").text = "SEPA"
                ET.SubElement(dbtr_other, "Issr").text = "ISO"

            dbtr_acct = ET.SubElement(drct_dbt_tx_inf, "DbtrAcct") if not is_return else ET.SubElement(drct_dbt_tx_inf, "CdtrAcct")
            dbtr_acct_id = ET.SubElement(dbtr_acct, "Id")
            
            is_iban = payment_bank_final and re.match(r'^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$', payment_bank_final)
            ET.SubElement(dbtr_acct_id, "IBAN").text = payment_bank_final
            
            # OTHR DOES NO WORK LIKE THIS
            # if is_iban:
            #     ET.SubElement(dbtr_acct_id, "IBAN").text = payment_bank_final
            # else:
            #     othr = ET.SubElement(dbtr_acct_id, "Othr")
            #     ET.SubElement(othr, "Id").text = payment_bank_final
            

            rmtInf = ET.SubElement(drct_dbt_tx_inf, "RmtInf")
            ET.SubElement(rmtInf, "Ustrd").text = title
                

        xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=True).decode('utf-8')
        return xml_string, ident_msg