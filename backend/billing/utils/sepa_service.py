import datetime
import xml.etree.ElementTree as ET
from datetime import timedelta, date
from billing.models import CommitmentDeposit, DocumentSEPA, Invoice, InvoiceStatus, Payment, PaymentRemittance, PaymentStatus, RejectMotive
from billing.utils.invoice_service import invoice_return_charge
from contract.models import Contract, ContractRequest
from coredata.models import ConfigProject
from dateutil.relativedelta import relativedelta
from documentmanager.utils.main_utils import download_document

def extract_payments_data(root, namespaces, msgId, client_doc_ids, clients_data, rjt_date):
    payments_data = []
    if root is None:
        print("###################################################################")
        for data in clients_data:
            client_data = {}
            client_data["end_to_end_id"] = data["document_end_id"].split("-")[0]
            client_data["IBAN"] = data["IBAN"]
            client_data["RJT"] = data["reject_token"]
            client_data["RJT_DATE"] = rjt_date if rjt_date else data["reject_date"]
            payments_data.append(client_data)
            
        return payments_data
            
    for namespace in namespaces:
        for report in root.findall(".//pain:CstmrDrctDbtInitn", namespace):
            group_header = report.find(".//pain:GrpHdr", namespace)
            print("group_header", group_header)
            if group_header is not None:
                reportMsgId = group_header.findall(".//pain:MsgId", namespace)
                if reportMsgId and reportMsgId[0].text != msgId:
                    raise ValueError("Message ID mismatch in SEPA document.")

            accounts = report.findall(".//pain:DbtrAcct", namespace)
            sepa_ids = report.findall(".//pain:DrctDbtTxInf", namespace)
            
            # Use the rjt_date passed as argument if provided (which comes from extract_report_data logic)
            final_rjt_date = rjt_date if isinstance(rjt_date, str) else rjt_date.strftime("%Y-%m-%d") if rjt_date else None
                    
            for sepa_id, acct in zip(sepa_ids, accounts):
                sepa_id_element = sepa_id.find(".//pain:EndToEndId", namespace)
                if sepa_id_element is not None:
                    sepa_id_text = sepa_id_element.text
                    if sepa_id_text in client_doc_ids:
                        client_data = {}
                        client_data["end_to_end_id"] = sepa_id_text.split("-")[0]
                        client_account = acct.find(".//pain:Id/pain:IBAN", namespace)
                        if client_account is not None:
                            client_data["IBAN"] = client_account.text
                        else:
                            client_account_othr = acct.find(".//pain:Id/pain:Othr/pain:Id", namespace)
                            if client_account_othr is not None:
                                client_data["IBAN"] = client_account_othr.text
                        client_data["RJT"] = clients_data[
                            client_doc_ids.index(sepa_id_text)
                        ]["reject_token"]
                        
                        client_sts_dt = sepa_id.find(".//pain:StsUpdtDtTm", namespace)
                        if client_sts_dt is not None and client_sts_dt.text:
                            client_data["RJT_DATE"] = client_sts_dt.text.split("T")[0]
                        else:
                            client_data["RJT_DATE"] = final_rjt_date
                        payments_data.append(client_data)
    return payments_data


def identify_returned_payments(payments, payments_data):
    returned_payments = []
    paid_payments = []
    payment_tokens = [payment["end_to_end_id"] for payment in payments_data]
    og_payment_tokens = [payment.token for payment in payments]
    client_data_not_found = []
    
    for payment_token in payment_tokens:
        if payment_token not in og_payment_tokens:
            client_data_not_found.append(payments_data[payment_tokens.index(payment_token)])

    for payment in payments:
        
        if payment.token in payment_tokens:
            return_data = {}
            return_data["payment"] = payment
            return_data["RJT"] = payments_data[
                payment_tokens.index(payment.token)
            ]["RJT"]
            if "RJT_DATE" in payments_data[payment_tokens.index(payment.token)]:
                return_data["RJT_DATE"] = payments_data[
                    payment_tokens.index(payment.token)
                ]["RJT_DATE"]
            returned_payments.append(return_data)
        else:
            paid_payments.append(payment)
    
    
    
    return returned_payments, paid_payments, client_data_not_found


def prepare_rejection_info(returned_payments, company_data, paid_payments, client_data_not_found, rjt_date):
    try:
        from datetime import datetime
        
        rejections = []
        rjt_dt = datetime.strptime(str(rjt_date), "%Y-%m-%dT%H:%M:%S")
        for payment_data in returned_payments:
            rejection = {}
            returned_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
            paid_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
            payment = payment_data["payment"]
            contract = None
            motive = None
            
            invoice = None
            commitment_deposit = None
            item_rjt_date = rjt_date # Start with the default for the file
            if payment_data.get("RJT"):
                try:
                    motive = RejectMotive.objects.get(token=payment_data["RJT"])
                except RejectMotive.DoesNotExist:
                    pass # RejectMotive with token {payment_data['RJT']} not found.
            if not item_rjt_date:
                if "RJT_DATE" in payment_data:
                    item_rjt_date = payment_data["RJT_DATE"]
                if "reject_date" in payment_data:
                    item_rjt_date = payment_data["reject_date"]
            if payment.invoice:
                invoice = Invoice.objects.get(id=payment.invoice.id)

                if payment.invoice.contract:
                    contract = Contract.objects.get(id=payment.invoice.contract.id)
                elif payment.invoice.contract_request:
                    contract = ContractRequest.objects.get(
                        id=payment.invoice.contract_request.id
                    )
                
                """ if payment.status != returned_status:
                    generateReturnedPayment(payment, motive) """
            else:
                commitment_deposit = CommitmentDeposit.objects.get(id=payment.commitment_deposit.id)
                contract = commitment_deposit.contract
            
                    
            if payment.payment_date and rjt_date:
                try:
                    payment_dt = payment.payment_date if isinstance(payment.payment_date, datetime) else datetime.strptime(str(payment.payment_date), "%Y-%m-%d")
                except ValueError:
                    payment_dt = datetime.strptime(str(payment.payment_date), "%Y-%m-%dT%H:%M:%S")
                try:
                    rjt_dt = rjt_date if isinstance(rjt_date, datetime) else datetime.strptime(str(rjt_date), "%Y-%m-%d")
                except ValueError:
                    pass
                if payment_dt > rjt_dt:
                    rejection["skip_return"] = True
                else:     
                    rejection["skip_return"] = False
            else:
                rjt_dt = rjt_date
            
            
            # If the payment is paid and not direct debit, skip
            if payment.status == paid_status and payment.payment_type and payment.payment_type_token != 'DIRECT_DEBIT':
                rejection["not_found"] = False
                rejection["skip_return"] = True
                rejection["contract"] = contract.token if contract else None
                rejection["contract_id"] = contract.id if contract else None
                rejection["payment_id"] = payment.id
                rejection["payment_token"] = payment.token
                rejection["payment_date"] = str(payment.payment_date) if payment.payment_date else None
                rejection["invoice"] = invoice.serie_final if invoice else None
                rejection["commitment_deposit"] = commitment_deposit.token if commitment_deposit else None
                rejection["holder"] = company_data["name"]
                rejection["amount"] = payment.amount
                rejection["prev_status"] = payment.status.name
                rejection["prev_status_color"] = payment.status.color
                rejection["motive_id"] = None
                rejection["motive"] = f'Invoice paid through another payment method: {payment.payment_type}'
                final_rjt_str = item_rjt_date.strftime("%Y-%m-%d") if hasattr(item_rjt_date, "strftime") else str(item_rjt_date).split("T")[0] if item_rjt_date else None
                rejection["rjt_dt"] = final_rjt_str # Ensure rjt_dt is always added
                rejections.append(rejection)
                continue
            
            if payment.payment_date and item_rjt_date:
                try:
                    payment_dt = payment.payment_date if isinstance(payment.payment_date, datetime) else datetime.strptime(str(payment.payment_date), "%Y-%m-%d")
                except ValueError:
                    payment_dt = datetime.strptime(str(payment.payment_date), "%Y-%m-%dT%H:%M:%S")
                try:
                    rjt_dt = item_rjt_date if isinstance(item_rjt_date, datetime) else datetime.strptime(str(item_rjt_date), "%Y-%m-%d")
                except ValueError:
                    rjt_dt = datetime.strptime(str(item_rjt_date), "%Y-%m-%dT%H:%M:%S")
                
                rejection["rjt_dt"] = rjt_dt.strftime("%Y-%m-%d") if hasattr(rjt_dt, "strftime") else str(rjt_dt).split("T")[0] if rjt_dt else None
                
                if payment_dt > rjt_dt:
                    rejection["not_found"] = False
                    rejection["skip_return"] = True
                    rejection["contract"] = contract.token if contract else None
                    rejection["contract_id"] = contract.id if contract else None
                    rejection["payment_id"] = payment.id
                    rejection["payment_token"] = payment.token
                    rejection["payment_date"] = str(payment.payment_date) if payment.payment_date else None
                    rejection["invoice"] = invoice.serie_final if invoice else None
                    rejection["commitment_deposit"] = commitment_deposit.token if commitment_deposit else None
                    rejection["holder"] = company_data["name"]
                    rejection["amount"] = payment.amount
                    rejection["prev_status"] = payment.status.name
                    rejection["prev_status_color"] = payment.status.color
                    rejection["motive_id"] = None
                    rejection["motive"] = f'Payment date is after reject date: {payment.payment_date} > {item_rjt_date}'
                    rejections.append(rejection)
                    continue
            else:
                rejection["rjt_dt"] = item_rjt_date.strftime("%Y-%m-%d") if hasattr(item_rjt_date, "strftime") else str(item_rjt_date).split("T")[0] if item_rjt_date else None
            
            # payment.status = returned_status
            # payment.reject = motive
            # payment.reject_date = date.today()
            # payment.save()
            
            rejection["not_found"] = False
            rejection["contract"] = contract.token if contract else None
            rejection["contract_id"] = contract.id if contract else None
            rejection["payment_id"] = payment.id
            rejection["payment_token"] = payment.token
            rejection["payment_date"] = str(payment.payment_date) if payment.payment_date else None
            rejection["invoice"] = invoice.serie_final if invoice else None
            rejection["commitment_deposit"] = commitment_deposit.token if commitment_deposit else None
            rejection["holder"] = company_data["name"]
            rejection["amount"] = payment.amount
            rejection["prev_status"] = payment.status.name
            rejection["prev_status_color"] = payment.status.color
            rejection["motive_id"] = motive.id if motive else None
            rejection["motive"] = motive.name if motive else None
            rejection["rjt_dt"] = item_rjt_date.strftime("%Y-%m-%d") if hasattr(item_rjt_date, "strftime") else str(item_rjt_date).split("T")[0] if item_rjt_date else None
            rejections.append(rejection)
        
        for client_data in client_data_not_found:
            rejection = handle_not_found_payment(client_data, company_data, rjt_dt)
            rejections.append(rejection)
        return rejections
    except Exception as e:
        raise Exception(f"Error in prepare_rejection_info: {e}")

def generateReturnedPayment(payment, motive):
    returned_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
    try:
        invoice = payment.invoice
        if invoice.parent_invoice:
            while invoice.parent_invoice:
                invoice = invoice.parent_invoice
                
        if payment.status != returned_status:
            new_invoice = invoice_return_charge(invoice, 'RECLAMACIÓ DE SERVEI')
        
            payment.status = returned_status
            payment.reject = motive
            payment.save()
    except:
        raise Exception("Error in generateReturnedPayment")

    
def getDocumentSEPAPayments(msgId, company_data, clients_data, file_content, og_msg_id, rjt_date):
    try:
        # Group rejections by pmt_inf_id to support files with multiple remittances
        groups = {}
        for client in clients_data:
            p_id = client.get("pmt_inf_id") or og_msg_id or msgId
            if p_id not in groups:
                groups[p_id] = []
            groups[p_id].append(client)
            
        all_rejections = []
        for p_id, block_clients in groups.items():
            try:
                document = PaymentRemittance.objects.get(token=p_id)
            except Exception as e:
                document = None
                
            client_doc_ids = [c.get("document_end_id") for c in block_clients if c.get("document_end_id")]
            
            if document:
                rejections = handle_document_sepa(document, company_data, block_clients, p_id, client_doc_ids, file_content, rjt_date)
            else:
                rejections = handle_no_document(company_data, block_clients, p_id, client_doc_ids, rjt_date)
            
            all_rejections.extend(rejections)
            
        return all_rejections

    except Exception as e:
        raise Exception(f"Error in getDocumentSEPAPayments: {e}")

def handle_no_document(company_data, clients_data, msgId, client_doc_ids, rjt_date):
    rejections = []
    for client_data in clients_data:
        rejection = handle_not_found_payment(client_data, company_data, rjt_date)
        rejections.append(rejection)
    return rejections

def handle_not_found_payment(client_data, company_data, rjt_date):
    # client_data may come from clients_data (has reject_token, document_end_id, name, etc.)
    # or from payments_data via client_data_not_found (has RJT, end_to_end_id, IBAN, RJT_DATE)
    motive = None
    reject_token = client_data.get("reject_token") or client_data.get("RJT")
    reject_date = rjt_date if rjt_date else client_data.get("reject_date") or client_data.get("RJT_DATE")
    try:
        if reject_token:
            motive = RejectMotive.objects.get(token=reject_token)
        else:
            motive = None
    except RejectMotive.DoesNotExist:
        pass # RejectMotive with token {reject_token} not found.
    rejection = {}
    returned_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
    paid_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
    contract = None
    
    invoice = None
    commitment_deposit = None

    payment_token = client_data.get("document_end_id") or client_data.get("end_to_end_id", "")

    if '-' in payment_token:
        payment_token = payment_token.split("-")[0]

    #TODO: DELETE in a few months, this is for historic payments coming from KAIS
    if payment_token.startswith("2026A"):
        payment_token = payment_token[-8:]

    payment = Payment.objects.filter(token=payment_token).first()
    if not payment:
        rejection = {}
        rejection['not_found'] = True
        rejection["skip_return"] = False
        rejection["holder_name"] = client_data.get("name", "")
        rejection["holder_iban"] = client_data.get("IBAN", "")
        rejection['client_id'] = client_data.get("document_end_id") or client_data.get("end_to_end_id", "")
        rejection["payment_date"] = client_data.get("payment_date", "")
        rejection["amount"] = client_data.get("amount", "")
        rejection["motive_id"] = None
        rejection["motive"] = motive.name if motive else None
        rejection["rjt_dt"] = reject_date # Ensure rjt_dt is always added
        return rejection
    if payment.invoice:
        invoice = Invoice.objects.get(id=payment.invoice.id)

        if payment.invoice.contract:
            contract = Contract.objects.get(id=payment.invoice.contract.id)
        elif payment.invoice.contract_request:
            contract = ContractRequest.objects.get(
                id=payment.invoice.contract_request.id
            )
        
        """ if payment.status != returned_status:
            generateReturnedPayment(payment, motive) """
    else:
        commitment_deposit = CommitmentDeposit.objects.get(id=payment.commitment_deposit.id)
        contract = commitment_deposit.contract
        
    # If the payment is paid and not direct debit, skip
    if payment.status == paid_status and payment.payment_type_token != 'DIRECT_DEBIT':
        rejection["not_found"] = False
        rejection["skip_return"] = True
        rejection["contract"] = contract.token if contract else None
        rejection["contract_id"] = contract.id if contract else None
        rejection["payment_id"] = payment.id
        rejection["payment_token"] = payment.token
        rejection["payment_date"] = str(payment.payment_date) if payment.payment_date else None
        rejection["invoice"] = invoice.serie_final if invoice else None
        rejection["commitment_deposit"] = commitment_deposit.token if commitment_deposit else None
        rejection["holder"] = company_data["name"]
        rejection["amount"] = payment.amount
        rejection["prev_status"] = payment.status.name
        rejection["prev_status_color"] = payment.status.color
        rejection["motive_id"] = None
        rejection["motive"] = f'Invoice paid through another payment method: {payment.payment_type}'
        rejection["rjt_dt"] = reject_date # Ensure rjt_dt is always added
        return rejection
    
    if payment.payment_date and reject_date:
        from datetime import datetime
        try:
            payment_dt = payment.payment_date if isinstance(payment.payment_date, datetime) else datetime.strptime(str(payment.payment_date), "%Y-%m-%d")
        except ValueError:
            payment_dt = datetime.strptime(str(payment.payment_date), "%Y-%m-%dT%H:%M:%S")
        try:
            rjt_dt = reject_date if isinstance(reject_date, datetime) else datetime.strptime(str(reject_date), "%Y-%m-%d")
        except ValueError:
            rjt_dt = datetime.strptime(str(reject_date), "%Y-%m-%dT%H:%M:%S")
        if payment_dt > rjt_dt:
            rejection["skip_return"] = True
        else:     
            rejection["skip_return"] = False
    
    rejection["not_found"] = False
    rejection["contract"] = contract.token if contract else None
    rejection["contract_id"] = contract.id if contract else None
    rejection["payment_id"] = payment.id
    rejection["payment_token"] = payment.token
    rejection["payment_date"] = str(payment.payment_date) if payment.payment_date else None
    rejection["invoice"] = invoice.serie_final if invoice else None
    rejection["commitment_deposit"] = commitment_deposit.token if commitment_deposit else None
    rejection["holder"] = company_data["name"]
    rejection["amount"] = payment.amount
    rejection["prev_status"] = payment.status.name
    rejection["prev_status_color"] = payment.status.color
    rejection["motive_id"] = motive.id if motive else None
    rejection["motive"] = motive.name if motive else None
    rejection["rjt_dt"] = reject_date # Ensure rjt_dt is always added
    return rejection

def handle_document_sepa(document, company_data, clients_data, msgId, client_doc_ids, or_file_content, rjt_date):
    payments = document.payments.all()
        
    file_content = None
    root = None
    try:
        doc_file = download_document(document.document)
        file_content = doc_file.content.decode("utf-8")
    except Exception as e:
        pass # Original File not available

    if file_content:
        root = ET.fromstring(file_content)
        
    namespaces = [
        {
            "pain": "urn:iso:std:iso:20022:tech:xsd:pain.008.001.02"
        },
        {
            "pain": "urn:iso:std:iso:20022:tech:xsd:pain.002.001.10"
        }
    ]

    payments_data = extract_payments_data(
        root, namespaces, msgId, client_doc_ids, clients_data, rjt_date
    )

    returned_payments, paid_payments, identified_returned_payments = identify_returned_payments(
        payments, payments_data
    )


    rejections = prepare_rejection_info(
        returned_payments, company_data, paid_payments, identified_returned_payments, rjt_date
    )
    return rejections

def extract_report_data(report, namespace):
    report_data = {}
    rjt_date = None

    group_header = report.find(".//pain:GrpHdr", namespace)
    if group_header is not None:
        msg_id_elem = group_header.find(".//pain:MsgId", namespace)
        report_data["message_id"] = msg_id_elem.text if msg_id_elem is not None else None
        
        cre_dt_tm_elem = group_header.find(".//pain:CreDtTm", namespace)
        if cre_dt_tm_elem is not None and cre_dt_tm_elem.text:
            val = cre_dt_tm_elem.text
            if "T" in val:
                val = val.split("T")[0]
            report_data["creation_datetime"] = val
        else:
            report_data["creation_datetime"] = None

    group_org_header = report.find(".//pain:OrgnlGrpInfAndSts", namespace)
    if group_org_header is not None:
        org_msg_id_elem = group_org_header.find(".//pain:OrgnlMsgId", namespace)
        report_data["orgn_msg_id"] = org_msg_id_elem.text if org_msg_id_elem is not None else None
        
        orgn_nb_txs_elem = group_org_header.find(".//pain:OrgnlNbOfTxs", namespace)
        report_data["orgn_nb_txs"] = orgn_nb_txs_elem.text if orgn_nb_txs_elem is not None else None
        
        orgn_ctrl_sum_elem = group_org_header.find(".//pain:OrgnlCtrlSum", namespace)
        report_data["orgn_ctrl_sum"] = orgn_ctrl_sum_elem.text if orgn_ctrl_sum_elem is not None else None

    # Version-based date logic
    cre_dt = None
    if report_data.get("creation_datetime"):
        try:
            cre_dt = datetime.datetime.fromisoformat(report_data["creation_datetime"].replace('Z', '+00:00'))
        except:
            try:
                cre_dt = datetime.datetime.strptime(report_data["creation_datetime"][:19], "%Y-%m-%dT%H:%M:%S")
            except:
                pass

    if "002.001.10" in namespace.get("pain", ""):
        # Version 10: Always use CreDtTm
        rjt_date = cre_dt
    else:
        # Version 03 or others: Compare CreDtTm and OrgnlMsgId portion
        org_date = None
        if report_data.get("orgn_msg_id"):
            print("orgn_msg_id", report_data["orgn_msg_id"])
            try:
                # Prioritize YYYY-MM-DD
                org_date = datetime.datetime.strptime(report_data["orgn_msg_id"][:10], "%Y-%m-%d")
            except:
                try:
                    # Fallback YYYYMMDD
                    org_date = datetime.datetime.strptime(report_data["orgn_msg_id"][:8], "%Y%m%d")
                except:
                    pass
        if cre_dt and org_date:
            # Pick the one closest to today (absolute difference)
            today = datetime.datetime.now()
            if abs(today - cre_dt) < abs(today - org_date):
                rjt_date = cre_dt
            else:
                rjt_date = org_date
        else:
            rjt_date = cre_dt or org_date
    
    return report_data, rjt_date.strftime("%Y-%m-%dT%H:%M:%S")


def extract_company_data(report, namespace):
    company_data = {}
    name_list = []
    iban_list = []

    creditor_bic = (
        report.find(".//pain:BICOrBEI", namespace).text
        if report.find(".//pain:BICOrBEI", namespace) is not None
        else None
    )
    company_data["SWIFT"] = creditor_bic

    for org_id in report.findall(".//pain:Cdtr", namespace):
        company_name = org_id.find(".//pain:Nm", namespace)
        if company_name is not None:
            name_list.append(company_name.text)

    for org_id in report.findall(".//pain:CdtrAcct", namespace):
        company_account = org_id.find(".//pain:IBAN", namespace)
        if company_account is not None:
            iban_list.append(company_account.text)
        else:
            company_account_othr = org_id.find(".//pain:Othr/pain:Id", namespace)
            if company_account_othr is not None:
                iban_list.append(company_account_othr.text)

    if not all(x == name_list[0] for x in name_list):
        raise Exception("Multiple companies found")
    company_data["name"] = name_list[0]

    if not all(x == iban_list[0] for x in iban_list):
        raise Exception("Multiple bank data for the same company found")
    company_data["IBAN"] = iban_list[0]

    return company_data


def extract_clients_data(report, namespace, rjt_date_og):
    clients_data = []
    
    # Check for OrgnlPmtInfAndSts blocks
    pmt_inf_blocks = report.findall(".//pain:OrgnlPmtInfAndSts", namespace)
    
    # If no blocks, treat the report as a single block
    if not pmt_inf_blocks:
        blocks_to_process = [(None, report)]
    else:
        blocks_to_process = []
        for block in pmt_inf_blocks:
            inf_id_elem = block.find(".//pain:OrgnlPmtInfId", namespace)
            inf_id = inf_id_elem.text if inf_id_elem is not None else None
            blocks_to_process.append((inf_id, block))

    for pmt_inf_id, block in blocks_to_process:
        tx_infos = block.findall(".//pain:TxInfAndSts", namespace)
        
        for tx_info in tx_infos:
            client_data = {}
            client_data["pmt_inf_id"] = pmt_inf_id
            
            # OrgnlEndToEndId
            elem = tx_info.find(".//pain:OrgnlEndToEndId", namespace)
            if elem is not None:
                client_data["document_end_id"] = elem.text
                
            # Debtor Name (Look in TxInfAndSts or nested OrgnlTxRef)
            elem = tx_info.find(".//pain:Dbtr/pain:Nm", namespace)
            if elem is None:
                elem = tx_info.find(".//pain:OrgnlTxRef/pain:Dbtr/pain:Nm", namespace)
            if elem is not None:
                client_data["name"] = elem.text
                
            # Debtor IBAN
            elem = tx_info.find(".//pain:DbtrAcct/pain:Id/pain:IBAN", namespace)
            if elem is None:
                elem = tx_info.find(".//pain:OrgnlTxRef/pain:DbtrAcct/pain:Id/pain:IBAN", namespace)
            if elem is not None:
                client_data["IBAN"] = elem.text
            else:
                elem = tx_info.find(".//pain:DbtrAcct/pain:Id/pain:Othr/pain:Id", namespace)
                if elem is None:
                    elem = tx_info.find(".//pain:OrgnlTxRef/pain:DbtrAcct/pain:Id/pain:Othr/pain:Id", namespace)
                if elem is not None:
                    client_data["IBAN"] = elem.text
            
            # BIC
            elem = tx_info.find(".//pain:DbtrAgt/FinInstnId/pain:BIC", namespace)
            if elem is None:
                elem = tx_info.find(".//pain:OrgnlTxRef/pain:DbtrAgt/pain:FinInstnId/pain:BIC", namespace)
            if elem is not None:
                client_data["SWIFT"] = elem.text
                
            # Reject Code
            elem = tx_info.find(".//pain:StsRsnInf/pain:Rsn/pain:Cd", namespace)
            if elem is None:
                elem = tx_info.find(".//pain:Rsn/pain:Cd", namespace)
            if elem is not None:
                client_data["reject_token"] = elem.text
                
            # Amount
            elem = tx_info.find(".//pain:InstdAmt", namespace)
            if elem is None:
                elem = tx_info.find(".//pain:OrgnlTxRef/pain:Amt/pain:InstdAmt", namespace)
            if elem is not None:
                client_data["amount"] = elem.text
                
            # Payment date
            elem = tx_info.find(".//pain:ReqdColltnDt", namespace)
            if elem is None:
                elem = tx_info.find(".//pain:OrgnlTxRef/pain:ReqdColltnDt", namespace)
            if elem is not None:
                client_data["payment_date"] = elem.text
                
            # Reject date logic
            tx_sts_dt = tx_info.find(".//pain:StsUpdtDtTm", namespace)
            if tx_sts_dt is not None and tx_sts_dt.text:
                client_data['reject_date'] = tx_sts_dt.text.split("T")[0]
            else:
                # Use the passed smart default (which could be a string or date object)
                if hasattr(rjt_date_og, "strftime"):
                    client_data['reject_date'] = rjt_date_og.strftime("%Y-%m-%d")
                else:
                    client_data['reject_date'] = rjt_date_og

            clients_data.append(client_data)
            
    return clients_data

def extract_og_msg_id(report, namespace):
    og_msg_id = report.find(".//pain:OrgnlPmtInfId", namespace)
    if og_msg_id is not None:
        return og_msg_id.text
    return None