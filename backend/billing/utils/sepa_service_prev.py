import xml.etree.ElementTree as ET
from datetime import timedelta, date
from billing.models import CommitmentDeposit, DocumentSEPA, Invoice, InvoiceStatus, Payment, PaymentStatus, RejectMotive
from billing.utils.invoice_service import invoice_return_charge
from contract.models import Contract, ContractRequest
from coredata.models import ConfigProject
from dateutil.relativedelta import relativedelta
from documentmanager.utils.main_utils import download_document


def extract_payments_data(root, namespace, msgId, client_doc_ids, clients_data):
    payments_data = []
    for report in root.findall(".//pain:CstmrDrctDbtInitn", namespace):
        group_header = report.find(".//pain:GrpHdr", namespace)
        if group_header is not None:
            reportMsgId = group_header.find(".//pain:MsgId", namespace)
            if reportMsgId is not None and reportMsgId.text != msgId:
                raise ValueError("Message ID mismatch in SEPA document.")

        accounts = report.findall(".//pain:DbtrAcct", namespace)
        sepa_ids = report.findall(".//pain:DrctDbtTxInf", namespace)

        for sepa_id, acct in zip(sepa_ids, accounts):
            sepa_id_element = sepa_id.find(".//pain:EndToEndId", namespace)
            if sepa_id_element is not None:
                sepa_id_text = sepa_id_element.text
                if sepa_id_text in client_doc_ids:
                    client_data = {}
                    client_data["end_to_end_id"] = sepa_id_text
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
                    payments_data.append(client_data)
    return payments_data


def identify_returned_payments(payments, payments_data):
    returned_payments = []
    paid_payments = []
    payment_ibans = [payment["IBAN"] for payment in payments_data]

    for payment_id in payments:
        print("\n\nPAYMENT ID")
        print(payment_id)
        payment_instance = Payment.objects.get(id=payment_id)
        print("\n")
        print(payment_instance.payment_bank)
        print(payment_ibans)
        print("\n\npayment_instance")
        print(payment_instance)
        if payment_instance.payment_bank in payment_ibans:
            return_data = {}
            return_data["payment"] = payment_instance
            return_data["RJT"] = payments_data[
                payment_ibans.index(payment_instance.payment_bank)
            ]["RJT"]
            returned_payments.append(return_data)
        else:
            paid_payments.append(payment_instance)
    return returned_payments, paid_payments


def prepare_rejection_info(returned_payments, company_data, paid_payments):
    try:
        rejections = []
        for payment_data in returned_payments:
            rejection = {}
            returned_status = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_returned_token').value)
            payment = payment_data["payment"]
            contract = None
            motive = None
            
            invoice = None
            commitment_deposit = None
            
            if payment_data["RJT"]:
                try:
                    motive = RejectMotive.objects.get(token=payment_data["RJT"])
                except RejectMotive.DoesNotExist:
                    print(
                        f"RejectMotive with token {payment_data['RJT']} not found."
                    )
            if payment.invoice_id:
                invoice = Invoice.objects.get(id=payment.invoice_id)

                if payment.invoice.contract:
                    contract = Contract.objects.get(id=payment.invoice.contract.id)
                elif payment.invoice.contract_request:
                    contract = ContractRequest.objects.get(
                        id=payment.invoice.contract_request.id
                    )
                
                if payment.status != returned_status:
                    generateReturnedPayment(payment, motive)
            else:
                commitment_deposit = CommitmentDeposit.objects.get(id=payment.commitment_deposit_id)
                contract = commitment_deposit.contract
                payment.status = returned_status
                payment.reject = motive
                payment.save()
                    
            print("\ngenerated Returned Payment")
            
            rejection["contract"] = contract.token if contract else None
            rejection["invoice"] = invoice.token if invoice else None
            rejection["commitment_deposit"] = commitment_deposit.token if commitment_deposit else None
            rejection["holder"] = company_data["name"]
            rejection["amount"] = payment.amount
            rejection["prev_status"] = payment.status.name
            rejection["motive"] = motive.name if motive else None
            rejections.append(rejection)
            print("rejection added")
            
        #TODO: check if automatically set as paid the rest?
        """ for payment in paid_payments:
            status_paid = PaymentStatus.objects.get(token=ConfigProject.objects.get(token='payment_status_paid_token').value)
            if payment.status != status_paid:
                payment.status = status_paid
                payment.save() """
        print("updated payments")

        return rejections
    except:
        raise Exception("Error in prepare_rejection_info")

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

    
def getDocumentSEPAPayments(msgId, company_data, clients_data):
    try:
        document = DocumentSEPA.objects.get(msgId=msgId)

        client_doc_ids = [
            client_data["document_end_id"] for client_data in clients_data
        ]

        payments = [
            payment.id
            for line in document.lines.all()
            for payment in line.payments.all()
        ]
        
        print("\n\nPAYMENTS")
        print(payments)

        doc_file = download_document(document.document)
        file_content = doc_file.content.decode("utf-8")

        root = ET.fromstring(file_content)
        namespace = {
            "pain": "urn:iso:std:iso:20022:tech:xsd:pain.008.001.02"
        }

        payments_data = extract_payments_data(
            root, namespace, msgId, client_doc_ids, clients_data
        )

        returned_payments, paid_payments = identify_returned_payments(
            payments, payments_data
        )
        
        print("DIF PAYMENTS")
        print(returned_payments)
        print(paid_payments)

        rejections = prepare_rejection_info(
            returned_payments, company_data, paid_payments
        )
        print("returned rejections")

        return rejections

    except DocumentSEPA.DoesNotExist:
        print(f"DocumentSEPA with msgId {msgId} not found.")
        raise Exception(f"DocumentSEPA with msgId {msgId} not found.")
    except Exception as e:
        print(f"Error in getDocumentSEPAPayments: {e}")
        raise Exception(f"Error in getDocumentSEPAPayments: {e}")


def extract_report_data(report, namespace):
    report_data = {}

    group_header = report.find(".//pain:GrpHdr", namespace)
    if group_header is not None:
        report_data["message_id"] = (
            group_header.find(".//pain:MsgId", namespace).text
            if group_header.find(".//pain:MsgId", namespace) is not None
            else None
        )
        report_data["creation_datetime"] = (
            group_header.find(".//pain:CreDtTm", namespace).text
            if group_header.find(".//pain:CreDtTm", namespace) is not None
            else None
        )

    group_org_header = report.find(".//pain:OrgnlGrpInfAndSts", namespace)
    if group_org_header is not None:
        report_data["orgn_msg_id"] = (
            group_org_header.find(".//pain:OrgnlMsgId", namespace).text
            if group_org_header.find(".//pain:OrgnlMsgId", namespace)
            is not None
            else None
        )
        report_data["orgn_nb_txs"] = (
            group_org_header.find(".//pain:OrgnlNbOfTxs", namespace).text
            if group_org_header.find(".//pain:OrgnlNbOfTxs", namespace)
            is not None
            else None
        )
        report_data["orgn_ctrl_sum"] = (
            group_org_header.find(".//pain:OrgnlCtrlSum", namespace).text
            if group_org_header.find(".//pain:OrgnlCtrlSum", namespace)
            is not None
            else None
        )

    return report_data


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


def extract_clients_data(report, namespace):
    clients_data = []
    debtors = report.findall(".//pain:Dbtr", namespace)
    accounts = report.findall(".//pain:DbtrAcct", namespace)
    swifts = report.findall(".//pain:DbtrAgt", namespace)
    rejections = report.findall(".//pain:Rsn", namespace)
    sepa_ids = report.findall(".//pain:TxInfAndSts", namespace)

    for dbtr, acct, swift, rejection, sepa_id in zip(
        debtors, accounts, swifts, rejections, sepa_ids
    ):
        client_data = {}

        client_name = dbtr.find(".//pain:Nm", namespace)
        if client_name is not None:
            client_data["name"] = client_name.text

        client_account = acct.find(".//pain:Id/pain:IBAN", namespace)
        if client_account is not None:
            client_data["IBAN"] = client_account.text
        else:
            client_account_othr = acct.find(".//pain:Id/pain:Othr/pain:Id", namespace)
            if client_account_othr is not None:
                client_data["IBAN"] = client_account_othr.text

        client_swift = swift.find(".//pain:FinInstnId/pain:BIC", namespace)
        if client_swift is not None:
            client_data["SWIFT"] = client_swift.text

        client_reject_token = rejection.find(".//pain:Cd", namespace)
        if client_reject_token is not None:
            client_data["reject_token"] = client_reject_token.text

        client_document_id = sepa_id.find(".//pain:OrgnlEndToEndId", namespace)
        if client_document_id is not None:
            client_data["document_end_id"] = client_document_id.text

        clients_data.append(client_data)

    return clients_data
