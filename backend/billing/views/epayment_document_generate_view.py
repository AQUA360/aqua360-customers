import base64
from decimal import ROUND_HALF_UP, Decimal
import json
from celery import group, chord
from django.conf import settings
import os
from datetime import datetime, timedelta
import uuid
import timeit
from django.conf import settings
from django.http import FileResponse, JsonResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, DjangoModelPermissions
from billing.models import Invoice, InvoiceClass, InvoiceLineItem, InvoiceSerie, InvoiceStatus, Message, Payment, PaymentStatus
from billing.serializers.invoice_serializer import InvoiceFullSerializer
from billing.serializers.payment_serializer import PaymentSEPASerializer
from billing.signals import create_payment_invoice
from billing.utils.payment_service import get_payment_SEPA_data
from django.db.models import Sum
import xml.etree.ElementTree as ET
from django.core.files.base import ContentFile
from billing.views.invoice_pdf_view import InvoiceReportPDFDownloadViewSet, generate_report_invoice_pdf
from contract.models import ContractRequest
from coredata.models import Bank, ConfigProject, Country, Person, PersonContact
from coredata.utils.other_utils import round_ceil
from documentmanager.utils.main_utils import upload_document
from documentmanager.utils.hdd_service import upload_to_hdd
from service.models import Company, CompanyBank, Exploitation
from billing.tasks import generate_and_upload_xml, generate_invoice_pdf
from billing.utils.invoice_service import find_person_for_invoice_customer
from django.db.models.signals import post_save
from faker import Faker
from django.db.models import Q
fake = Faker()

class EPaymentDocumentGenerateViewSet(APIView):
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    queryset = Payment.objects.all().order_by('-created_at')
    
    def post(self, request, *args, **kwargs):
        print("In E-Payment Document Generate View")
        origins = request.data["origins"]
        start_date = request.data["start_date"]
        end_date = request.data["end_date"]
        exploitation_id = request.data["exploitation"]
        billing_id = request.data["billing"]
        print("got exploitation id")
        print(exploitation_id)
        filters = Q()
                
        if origins:
            if origins:
                filters |= Q(invoice__origin__id__in=origins)
            filters &= Q(invoice__accounting_office_final__isnull=False)
            filters &= Q(invoice__managing_body_final__isnull=False)
            filters &= Q(invoice__processing_unit_final__isnull=False)
            if start_date:
                filters &= Q(payment_date__gte=start_date)
            if end_date:
                filters &= Q(payment_date__lte=end_date)
            if exploitation_id:
                filters &= Q(invoice__exploitation=exploitation_id)
            if billing_id:
                filters &= Q(invoice__billing=billing_id)
            payments = (
                Payment.objects.filter(filters)
                .distinct()
            )
            payment_ids = payments.values_list('id', flat=True)
            serializedPayments = PaymentSEPASerializer(payments, many=True).data
            return JsonResponse({
                    "payment_ids": list(payment_ids) if payment_ids else [],
                    "payments": serializedPayments if payments else [],
                    "anomalies": [],
                    "document_file": None
                    })
            
        return JsonResponse({
                    "payment_ids": None,
                    "payments": None,
                    "anomalies": None, 
                    "document_file": None})
        
        
    
    def put(self, request, *args, **kwargs):
        print("In E-Payment Document Generate View")
        payment_ids = request.data["payment_ids"]
        exclude_payment_ids = request.data["exclude_payment_ids"]
        
        #raise Exception("exclude payment ids")
        bank_id = request.data["bank_id"]

        post_save.disconnect(create_payment_invoice, Invoice)
        start_time = timeit.default_timer()
        
        xml_tasks = group(generate_and_upload_xml.s(payment_id, bank_id, request.data) for payment_id in payment_ids)()
        xml_results = xml_tasks.get() 

        document_file_ids = [result for result in xml_results if result]

        # Extract invoice IDs from payment_ids (assuming payment has invoice FK)
        invoice_ids = [Payment.objects.get(pk=payment_id).invoice_id for payment_id in payment_ids]

        pdf_generation_tasks = group(
            generate_invoice_pdf.s(invoice_id, True) for invoice_id in invoice_ids
        )()  
        pdf_results = pdf_generation_tasks.get()
        print("\n\nPDF_results")

        end_time = timeit.default_timer()
        elapsed_time = end_time - start_time
        post_save.connect(create_payment_invoice, Invoice)

        response_data = {
            "document_files": document_file_ids,
            "invoice_files": pdf_results,
            "elapsed_time": elapsed_time,
            "message": "E-payment document generation initiated successfully."
        }

        return JsonResponse(response_data)


def get_einvoice_document(invoice):
    xml_file_name = f"{invoice.serie_final.replace('/', '_')}_{invoice.id}.xml"
    base_name = xml_file_name[:-4] if xml_file_name.endswith('.xml') else xml_file_name
    from documentmanager.models import Document
    return Document.objects.filter(
        entity='REBUTS',
        field='EFACTURA',
        entity_id=invoice.id,
        document_name__startswith=base_name,
        is_active=True,
    ).order_by('-version').first()


def regenerate_einvoice_document(invoice):
    """Regenerate Facturae XML and overwrite the stored document when it exists."""
    xml_data = generate_xml(None, invoice)
    xml_bytes = xml_data.encode('utf-8')
    xml_file_name = f"{invoice.serie_final.replace('/', '_')}_{invoice.id}.xml"
    document = get_einvoice_document(invoice)

    if document and document.service == 'hdd':
        if document.location and os.path.isfile(document.location):
            with open(document.location, 'wb') as f:
                f.write(xml_bytes)
            return document
        xml_file = ContentFile(xml_bytes, name=xml_file_name)
        return upload_to_hdd(
            xml_file,
            'REBUTS',
            'EFACTURA',
            invoice.id,
            invoice.customer_token_final,
            '',
            xml_file_name,
            document,
        )

    if document:
        xml_file = ContentFile(xml_bytes, name=xml_file_name)
        new_document = upload_document(
            xml_file,
            'REBUTS',
            'EFACTURA',
            invoice.id,
            invoice.customer_token_final,
            '',
            settings.DOCUMENT_MANAGER_SERVICES.get('billing'),
            xml_file_name,
        )
        from communication.models import CommunicationFile
        CommunicationFile.objects.filter(file=document).update(file=new_document)
        return new_document

    xml_file = ContentFile(xml_bytes, name=xml_file_name)
    return upload_document(
        xml_file,
        'REBUTS',
        'EFACTURA',
        invoice.id,
        invoice.customer_token_final,
        '',
        settings.DOCUMENT_MANAGER_SERVICES.get('billing'),
        xml_file_name,
    )


def get_einvoice_line_quantity(line_item):
    """Quantity for Facturae XML: 2 decimals like invoice PDF, FACe RCF6a compliant."""
    line_total = round_ceil(line_item.price, 2)
    if not line_item.price_unit:
        return "{:.2f}".format(line_item.units or 0)

    quantity = round_ceil(line_item.units or 0, 2)
    # FACe regla 6a: TotalCost = RedondeoA2(Quantity * UnitPriceWithoutTax).
    # El precio unitario puede tener más de 2 decimales; no se debe redondear antes de multiplicar.
    if round_ceil(quantity * float(line_item.price_unit), 2) != line_total:
        quantity = round(line_total / line_item.price_unit, 2)

    return "{:.2f}".format(quantity)


def get_einvoice_invoice_reference(invoice):
    """Referència del número de factura per als camps de text lliure del Facturae.

    Els ajuntaments veuen el codi de registre de l'AOC, que s'assigna automàticament, i no
    el nostre número de factura. Posant-lo al davant dels textos que el seu ERP arrossega al
    concepte de la transferència podem identificar l'ingrés al banc.
    """
    return f"FRA. {invoice.serie_final}."


def generate_xml(payment, invoice_inst=None):
    print("generating xml")
    invoice = invoice_inst
    contract = None
    person = None
    payment_data = payment.created_at if not invoice else invoice.issue_date
    if not invoice:
        invoice = payment.invoice
    try:
        reading = invoice.readings.first()
    except:
        reading = None
    
    if invoice:
        if invoice.contract:
            contract = invoice.contract
        elif invoice.contract_request:
            contract = ContractRequest.objects.get(id=invoice.contract_request.id)
        elif invoice.contract_termination:
            contract = invoice.contract_termination.contract
        if contract:
            person = contract.holder
        else:
            person = find_person_for_invoice_customer(invoice)
    print("person: ", person)
    direct_debit_token = ConfigProject.objects.get(token='direct_debit_token').value
    bank_transfer_token = ConfigProject.objects.get(token='bank_transfer_token').value
    cash_token = ConfigProject.objects.get(token='cash_token').value
    #TODO: IMPORTANT CHECK COMMENT IN THIS XML. SOME IMPORTANT DETAILS IN NEED OF BEING CHECKED
    print("\n\ninvoice")
    invoice_ser = InvoiceFullSerializer(invoice)
    taxes = invoice_ser.data['taxes']
    #add to taxes, '0.00': 'subtotal'
    taxes_base = invoice_ser.data['taxes_base']
    subtotal = invoice_ser.data['subtotal']
    total = invoice_ser.data['total']
    total_taxes = sum(taxes_base.values())
    total_left = subtotal - total_taxes
    if total_left != 0:
        taxes_base.update({'0.00': total_left})
        taxes.update({'0.00': 0.00})
    
    print(invoice)
    print(invoice.serie_final)
    invoices = None
    residenceTypeCode = None
    #TODO: GET CURRENT USED EXPLOITATION
    exploitation = invoice.exploitation
    contract = invoice.contract if invoice.contract else invoice.contract_request
    if not contract and invoice.contract_termination:
        contract = invoice.contract_termination.contract
    if not exploitation and contract:
        exploitation = contract.supply_point_default.connection.exploitation
        
    if (exploitation and exploitation.company.company_banks.count() == 0):
        raise Exception("Company has no banks")
    if not exploitation:
        main_company_token = ConfigProject.objects.get(token='main_company_token').value
        main_company = Company.objects.get(vat=main_company_token)
    else:
        main_company = exploitation.company
    invoice_line_items = InvoiceLineItem.objects.filter(invoice=invoice, is_active=True)
    batchIdent = f"ES{main_company.vat}{invoice.serie_final}"
    # COMPANY BANK LATER SELECTED
    company_bank = main_company.company_banks.first()
    
    """ for line_item in invoice_line_items:
        print(line_item)
        print(line_item.__dict__) """
    #raise Exception("invoice checking")
    lang = settings.LANGUAGE_CODE
    country_company = Country.objects.get(iso_code=main_company.address.country.iso_code)
    print("gotten country_company")
    print(invoice.country_final)
    country = Country.objects.get(iso_code=invoice.country_final)
    if country.iso_code == 'ES':
        residenceTypeCode = 'R'
    else:
        if country.in_europe:
            residenceTypeCode = 'U'
        else:
            residenceTypeCode = 'E'
    
    
    
    root = ET.Element("Facturae", {
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
            "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
            "xmlns" : "http://www.facturae.es/Facturae/2009/v3.2/Facturae"
        })
    #
    #   FILE HEADER
    #
    fileHeader = ET.SubElement(root, "FileHeader", {"xmlns": ""})
    #CHECK IF MORE VERSIONS COULD BE USED
    ET.SubElement(fileHeader, "SchemaVersion").text = "3.2"
    #'I' individual, 'L' group
    ET.SubElement(fileHeader, "Modality").text = "I"
    #EM: EMISSOR, RE: RECEIVER, TE: THIRD PARTY
    ET.SubElement(fileHeader, "InvoiceIssuerType").text = "EM"
    
    batch = ET.SubElement(fileHeader, "Batch")
    ET.SubElement(batch, "BatchIdentifier").text = batchIdent
    ET.SubElement(batch, "InvoicesCount").text = "1"
    totalInvoicesCount = ET.SubElement(batch, "TotalInvoicesAmount")
    ET.SubElement(totalInvoicesCount, "TotalAmount").text = "{:.2f}".format(total)
    totalOutstandingCount = ET.SubElement(batch, "TotalOutstandingAmount")
    ET.SubElement(totalOutstandingCount, "TotalAmount").text = "{:.2f}".format(total)
    #CHECK POSSIBLE RETENTIONS ?
    totalExecutableAmount = ET.SubElement(batch, "TotalExecutableAmount")
    ET.SubElement(totalExecutableAmount, "TotalAmount").text = "{:.2f}".format(total)
    
    #check how to later add currency depending on the country
    ET.SubElement(batch, "InvoiceCurrencyCode").text = "EUR"
    
    
    #
    #   PARTIES
    #
    
    parties = ET.SubElement(root, "Parties", {"xmlns": ""})
    #
    #   PARTIES: SELLER PARTY
    #
    sellerParty = ET.SubElement(parties, "SellerParty")
    taxIdentification = ET.SubElement(sellerParty, "TaxIdentification")
    ET.SubElement(taxIdentification, "PersonTypeCode").text = "J"
    ET.SubElement(taxIdentification, "ResidenceTypeCode").text = 'R'
    #CHECK LATER HOW TO DO IT WITH OTHER COUNTRIES (FOR EXAMPLE MX NEEDS 'RFC' AND AG NEEDS 'CUIT)
    ET.SubElement(taxIdentification, "TaxIdentificationNumber").text = F"ES{main_company.vat}"
    
    legalEntity = ET.SubElement(sellerParty, "LegalEntity")
    ET.SubElement(legalEntity, "CorporateName").text = main_company.name.upper()
    # ET.SubElement(legalEntity, "TradeName").text = main_company.alias
    """ registrationData = ET.SubElement(legalEntity, "RegistrationData")
    ET.SubElement(registrationData, "Book")
    ET.SubElement(registrationData, "RegisterOfCompaniesLocation")
    ET.SubElement(registrationData, "Sheet")
    ET.SubElement(registrationData, "Folio")
    ET.SubElement(registrationData, "Section")
    ET.SubElement(registrationData, "Volume")
    ET.SubElement(registrationData, "AdditionalRegistrationData") """
    
    if country_company.iso_code == 'ES':
        addressInSpain = ET.SubElement(legalEntity, "AddressInSpain")
        ET.SubElement(addressInSpain, "Address").text = str(main_company.address).upper()
        ET.SubElement(addressInSpain, "PostCode").text = main_company.address.postal_code
        ET.SubElement(addressInSpain, "Town").text = main_company.address.city.name.upper()
        ET.SubElement(addressInSpain, "Province").text = main_company.address.province.name.upper()
        ET.SubElement(addressInSpain, "CountryCode").text = "ESP"   #ESP??
    else:
        overseasAddress = ET.SubElement(legalEntity, "OverseasAddress")
        ET.SubElement(overseasAddress, "Address").text = str(main_company.address).upper()
        ET.SubElement(overseasAddress, "PostCodeAndTown").text = f"{main_company.address.postal_code} {main_company.address.city.name}".upper()
        ET.SubElement(overseasAddress, "Province").text = main_company.address.province.name.upper()
        ET.SubElement(overseasAddress, "CountryCode").text = country_company.iso_code
    
    """ contactDetails = ET.SubElement(legalEntity, "ContactDetails")
    ET.SubElement(contactDetails, "Telephone").text = main_company.contact_phone
    ET.SubElement(contactDetails, "TeleFax")
    if main_company.website:
        ET.SubElement(contactDetails, "WebAddress").text = main_company.website
    else:
        ET.SubElement(contactDetails, "WebAddress")
    ET.SubElement(contactDetails, "ElectronicMail").text = main_company.contact_email
    ET.SubElement(contactDetails, "ContactPersons").text = main_company.contact_name if main_company.contact_name else main_company.name
    #CNAE?
    #CHECK IF THIS INFORMATION IS NEEDED
    ET.SubElement(contactDetails, "INETownCode")
    ET.SubElement(contactDetails, "AdditionalContactDetails") """
    
    #
    #   PARTIES: BUYER PARTY
    #
    buyerParty = ET.SubElement(parties, "BuyerParty")
    taxIdentificationB = ET.SubElement(buyerParty, "TaxIdentification")
    ET.SubElement(taxIdentificationB, "PersonTypeCode").text = "J" if invoice.customer_is_juridic else "F"
    ET.SubElement(taxIdentificationB, "ResidenceTypeCode").text = residenceTypeCode
    # CHECK LATER HOW TO DO IT WITH OTHER COUNTRIES (FOR EXAMPLE MX NEEDS 'RFC' AND AG NEEDS 'CUIT)
    ET.SubElement(taxIdentificationB, "TaxIdentificationNumber").text = f"{invoice.country_final}{invoice.customer_token_final}".upper()
    administrativeCentres = ET.SubElement(buyerParty, "AdministrativeCentres")
    #
    #ADM CENTRE FISCAL
    #
    administrativeCentreF = ET.SubElement(administrativeCentres, "AdministrativeCentre")
    ET.SubElement(administrativeCentreF, "CentreCode").text = invoice.accounting_office_final
    #01: FISCAL (ACC_OFF), 02: RECEPTOR(MNG_OFF), 03: PAGADOR(PRC_UNT), 04:COMPRADOR(Organizational body requesting purchase)
    ET.SubElement(administrativeCentreF, "RoleTypeCode").text = "01"
    # ADD OVERSEAS ADDRESS TO ADMINISTRATIVE CENTRE?
    # CHECK HOW TO OBTAIN THIS DATA
    addressInSpainAC = ET.SubElement(administrativeCentreF, "AddressInSpain")
    ET.SubElement(addressInSpainAC, "Address")  #WHICH ADDRESS TO USE?
    ET.SubElement(addressInSpainAC, "PostCode").text = contract.address_contact.address.postal_code if contract and contract.address_contact else invoice.postal_code_final
    ET.SubElement(addressInSpainAC, "Town").text = contract.address_contact.address.city.name.upper() if contract and contract.address_contact else invoice.city_final.upper()
    ET.SubElement(addressInSpainAC, "Province").text = contract.address_contact.address.province.name.upper() if contract and contract.address_contact else invoice.province_final.upper()
    ET.SubElement(addressInSpainAC, "CountryCode").text = "ESP"
    # CHECK LATER WHAT IS THIS INFORMATION
    ET.SubElement(administrativeCentreF, "CentreDescription")
    #
    #ADM CENTRE RECEPTOR
    #
    administrativeCentreR = ET.SubElement(administrativeCentres, "AdministrativeCentre")
    ET.SubElement(administrativeCentreR, "CentreCode").text = invoice.managing_body_final
    ET.SubElement(administrativeCentreR, "RoleTypeCode").text = "02"
    addressInSpainAC = ET.SubElement(administrativeCentreR, "AddressInSpain")
    #TODO: ADD INFO LATER
    ET.SubElement(addressInSpainAC, "Address") #WHICH ADDRESS TO USE?
    ET.SubElement(addressInSpainAC, "PostCode").text = contract.address_contact.address.postal_code if contract and contract.address_contact else invoice.postal_code_final
    ET.SubElement(addressInSpainAC, "Town").text = contract.address_contact.address.city.name.upper() if contract and contract.address_contact else invoice.city_final.upper()
    ET.SubElement(addressInSpainAC, "Province").text = contract.address_contact.address.province.name.upper() if contract and contract.address_contact else invoice.province_final.upper()
    ET.SubElement(addressInSpainAC, "CountryCode").text = "ESP"
    ET.SubElement(administrativeCentreR, "CentreDescription").text
    #
    #ADM CENTRE RECEPTOR
    #
    administrativeCentreR = ET.SubElement(administrativeCentres, "AdministrativeCentre")
    ET.SubElement(administrativeCentreR, "CentreCode").text = invoice.processing_unit_final
    ET.SubElement(administrativeCentreR, "RoleTypeCode").text = "03"
    addressInSpainAC = ET.SubElement(administrativeCentreR, "AddressInSpain")
    #TODO: FIND HOW TO OBTAIN THIS INFORMATION
    ET.SubElement(addressInSpainAC, "Address") #WHICH ADDRESS TO USE?   
    ET.SubElement(addressInSpainAC, "PostCode").text = contract.address_contact.address.postal_code if contract and contract.address_contact else invoice.postal_code_final
    ET.SubElement(addressInSpainAC, "Town").text = contract.address_contact.address.city.name.upper() if contract and contract.address_contact else invoice.city_final.upper()
    ET.SubElement(addressInSpainAC, "Province").text = contract.address_contact.address.province.name.upper() if contract and contract.address_contact else invoice.province_final.upper()
    ET.SubElement(addressInSpainAC, "CountryCode").text = "ESP"
    ET.SubElement(administrativeCentreR, "CentreDescription")
    
    #LEGAL ENTITY
    #if invoice.customer_is_juridic:
    legalEntityBP = ET.SubElement(buyerParty, "LegalEntity")
    ET.SubElement(legalEntityBP, "CorporateName").text = invoice.customer_final
    """ registrationDataBP = ET.SubElement(legalEntityBP, "RegistrationData")
    ET.SubElement(registrationDataBP, "Book")
    ET.SubElement(registrationDataBP, "RegisterOfCompaniesLocation")
    ET.SubElement(registrationDataBP, "Sheet")
    ET.SubElement(registrationDataBP, "Folio")
    ET.SubElement(registrationDataBP, "Section")
    ET.SubElement(registrationDataBP, "Volume")
    ET.SubElement(registrationDataBP, "AdditionalRegistrationData") """
    if country.iso_code == 'ES':
        addressInSpainAC = ET.SubElement(legalEntityBP, "AddressInSpain")
        ET.SubElement(addressInSpainAC, "Address").text = invoice.address_final.upper()
        ET.SubElement(addressInSpainAC, "PostCode").text = invoice.postal_code_final
        ET.SubElement(addressInSpainAC, "Town").text = invoice.city_final.upper()
        ET.SubElement(addressInSpainAC, "Province").text = invoice.province_final.upper()
        ET.SubElement(addressInSpainAC, "CountryCode").text = "ESP"
    else:
        overseasAddressAC = ET.SubElement(legalEntityBP, "OverseasAddress")
        ET.SubElement(overseasAddressAC, "Address").text = invoice.address_final.upper()
        ET.SubElement(overseasAddressAC, "PostCodeAndTown").text = f"{invoice.postal_code_final} {invoice.city_final.upper()}".upper()
        ET.SubElement(overseasAddressAC, "Province").text = invoice.province_final.upper()
        ET.SubElement(overseasAddressAC, "CountryCode").text = country.iso_code
    # end if
    #
    #   INVOICES
    #
    invoices = ET.SubElement(root, "Invoices", {"xmlns": ""})
    invoiceEL = ET.SubElement(invoices, "Invoice")
    #
    #   INVOICES: INVOICE HEADER
    #
    
    invoiceHeader = ET.SubElement(invoiceEL, "InvoiceHeader")
    ET.SubElement(invoiceHeader, "InvoiceNumber").text = invoice.serie_final
    #ET.SubElement(invoiceHeader, "InvoiceSeriesCode").text = invoice.serie_final
    ET.SubElement(invoiceHeader, "InvoiceDocumentType").text = invoice.serie_token_final
    #TODO: INVOICE CLASS
    ET.SubElement(invoiceHeader, "InvoiceClass").text = invoice.invoice_class_token_final if invoice.invoice_class else "OO"
    #
    #   INVOICES: INVOICE ISSUE DATA
    #
    invoiceIssueData = ET.SubElement(invoiceEL, "InvoiceIssueData")
    ET.SubElement(invoiceIssueData, "IssueDate").text = str(invoice.issue_date)
    ET.SubElement(invoiceIssueData, "OperationDate").text = reading.reading_date.strftime('%Y-%m-%d') if reading else str(invoice.issue_date)
    """ placeOfIssue = ET.SubElement(invoiceIssueData, "PlaceOfIssue")
    ET.SubElement(placeOfIssue, "PostCode").text = 'CODI POSTAL DE???'
    ET.SubElement(placeOfIssue, "PlaceOfIssueDescription").text = "ADREÇA EMPRESA" """
    invoicingPeriod = ET.SubElement(invoiceIssueData, "InvoicingPeriod")
    # CHECK WHAT ISSUE DATE IS AGAINST START DATE
    ET.SubElement(invoicingPeriod, "StartDate").text = reading.previous_reading.reading_date.strftime('%Y-%m-%d') if reading and reading.previous_reading else str(invoice.issue_date)
    ET.SubElement(invoicingPeriod, "EndDate").text = reading.reading_date.strftime('%Y-%m-%d') if reading else str(invoice.due_date)
    # ADD/CHECK CURRENCY
    ET.SubElement(invoiceIssueData, "InvoiceCurrencyCode").text = 'EUR'
    ET.SubElement(invoiceIssueData, "TaxCurrencyCode").text = 'EUR'
    # CHECK CURRENT LANGUAGE
    ET.SubElement(invoiceIssueData, "LanguageName").text = "ca" #CHANGE SETTINGS LATER
    #
    #   INVOICES: TAXES OUTPUTS
    #
    taxesOutputs = ET.SubElement(invoiceEL, "TaxesOutputs")
    for tax_base in taxes_base:
        tax = ET.SubElement(taxesOutputs, "Tax")
        #01: IVA, 02: IPSI, 03: IGIC, 04: IRPF, 05: ALTRE
        #DE MOMENT EN MANTENIM TAXES DE TYPE 01
        ET.SubElement(tax, "TaxTypeCode").text = '01'
        ET.SubElement(tax, "TaxRate").text = "{:.2f}".format(float(tax_base))
        taxableBase = ET.SubElement(tax, "TaxableBase")
        ET.SubElement(taxableBase, "TotalAmount").text = "{:.2f}".format(float(taxes_base.get(tax_base)))
        taxAmount = ET.SubElement(tax, "TaxAmount")
        ET.SubElement(taxAmount, "TotalAmount").text = "{:.2f}".format(float(taxes.get(tax_base)))
    
    """ taxesWithheld = ET.SubElement(invoice, "TaxesWithheld")
    #FOR TAXES
    taxW = ET.SubElement(taxesWithheld, "Tax")
    ET.SubElement(taxW, "TaxTypeCode").text = '???'
    ET.SubElement(taxW, "TaxRate").text = '???'
    taxableBase = ET.SubElement(taxW, "TaxableBase")
    ET.SubElement(taxableBase, "TotalAmount").text = '???'
    taxAmount = ET.SubElement(taxW, "TaxAmount")
    ET.SubElement(taxAmount, "TotalAmount").text = '???' """
    #
    #   INVOICES: INVOICE TOTALS
    #
    invoiceTotals = ET.SubElement(invoiceEL, "InvoiceTotals")
    ET.SubElement(invoiceTotals, "TotalGrossAmount").text = "{:.2f}".format(subtotal)
    ET.SubElement(invoiceTotals, "TotalGrossAmountBeforeTaxes").text = "{:.2f}".format(subtotal)
    ET.SubElement(invoiceTotals, "TotalTaxOutputs").text = "{:.2f}".format(total-subtotal)
    # CHECK IF IT'S ALWAYS 0.00
    ET.SubElement(invoiceTotals, "TotalTaxesWithheld").text = '0.00'
    ET.SubElement(invoiceTotals, "InvoiceTotal").text = "{:.2f}".format(total)
    ET.SubElement(invoiceTotals, "TotalOutstandingAmount").text = "{:.2f}".format(total)
    ET.SubElement(invoiceTotals, "TotalExecutableAmount").text = "{:.2f}".format(total)
    
    #
    #   INVOICES: ITEMS
    #
    items = ET.SubElement(invoiceEL, "Items")
    for line_index, line_item in enumerate(invoice_line_items):
        invoiceLine = ET.SubElement(items, "InvoiceLine")
        """ if contract:
            ET.SubElement(invoiceLine, "IssuerContractReference").text=contract.token
        else:
            ET.SubElement(invoiceLine, "IssuerContractReference")
        # CHECK WHAT ISSUER TRANSACTION REFERENCE COULD BE
        ET.SubElement(invoiceLine, "IssuerTransactionReference")
        if contract:
            ET.SubElement(invoiceLine, "ReceiverContractReference").text=contract.token
        else:
            ET.SubElement(invoiceLine, "ReceiverContractReference")
        ET.SubElement(invoiceLine, "ReceiverTransactionReference")
        ET.SubElement(invoiceLine, "FileReference") """
        if person and person.records.filter(year=payment_data.year).first():
            ET.SubElement(invoiceLine, "FileReference").text = person.records.filter(year=payment_data.year).first().e_record
        # DESCRIPTION EX: (B00000000) CANON AIGUA (ACA)-CANON D'ÚS INDUSTRIAL GENERAL-CANON
        item_description = f"{line_item.product_name} {line_item.price_rate_name if line_item.price_rate_name else ''}".strip()
        # El número de factura encapçala la descripció de la primera línia: és el text que
        # els ajuntaments arrosseguen al concepte de la transferència (a l'AOC hi surt el seu
        # codi de registre, no el nostre número), i així es pot conciliar l'ingrés.
        if line_index == 0:
            item_description = f"{get_einvoice_invoice_reference(invoice)} {item_description}".strip()
        ET.SubElement(invoiceLine, "ItemDescription").text = item_description
        quantity_einvoice = get_einvoice_line_quantity(line_item)
        
        ET.SubElement(invoiceLine, "Quantity").text = str(round_ceil(float(quantity_einvoice))) # get_einvoice_line_quantity(line_item)
        #TODO: DO RESEARCH ('Tipos-de-medida-de-unidad-uncefact')
        # ET.SubElement(invoiceLine, "UnitOfMeasure").text = "01" if line_item.units == 1 else "33"
        if round_ceil(float(quantity_einvoice) * line_item.price_unit) == line_item.price:
            unit_price_without_tax = line_item.price_unit
        else:
            unit_price_without_tax = float(Decimal(str(line_item.price / float(quantity_einvoice))).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
        ET.SubElement(invoiceLine, "UnitPriceWithoutTax").text = "{:.6f}".format(unit_price_without_tax)
            
        ET.SubElement(invoiceLine, "TotalCost").text = "{:.6f}".format(round(line_item.price,2))
        ET.SubElement(invoiceLine, "GrossAmount").text = "{:.6f}".format(round(line_item.price,2))
        taxesOutputsIL = ET.SubElement(invoiceLine, "TaxesOutputs")
        taxIL = ET.SubElement(taxesOutputsIL, "Tax")
        ET.SubElement(taxIL, "TaxTypeCode").text = "01"
        ET.SubElement(taxIL, "TaxRate").text = "{:.2f}".format(line_item.tax.percent)
        taxableBaseIL = ET.SubElement(taxIL, "TaxableBase")
        ET.SubElement(taxableBaseIL, "TotalAmount").text = "{:.2f}".format(round(line_item.price,2))
        taxAmountIL = ET.SubElement(taxIL, "TaxAmount")
        ET.SubElement(taxAmountIL, "TotalAmount").text = "{:.2f}".format(round((line_item.price/100 * line_item.tax.percent),2))
        #TODO: ADDITIONAL INFO
        # ET.SubElement(taxIL, "AdditionalLineItemInformation").text = f"Propietari: {main_company.name} CIF: {main_company.vat}"
        """ if line_item.tax.percent == 0:
            specialTaxableEvent = ET.SubElement(invoiceLine, "SpecialTaxableEvent")
            ET.SubElement(specialTaxableEvent, "SpecialTaxableEventCode").text = "01"
            ET.SubElement(specialTaxableEvent, "SpecialTaxableEventCode") """
    #
    #   INVOICES: PAYMENT DETAILS
    #
    if invoice.payment_type_token_final == direct_debit_token:
        paymentDetails = ET.SubElement(invoiceEL, "PaymentDetails")
        installment = ET.SubElement(paymentDetails, "Installment")
        #TODO: InstallmentDueDate company bank???
        ET.SubElement(installment, "InstallmentDueDate").text = str(invoice.due_date)
        ET.SubElement(installment, "InstallmentAmount").text = "{:.2f}".format(total)
        #02: Domiciliat 03: Transferència bancària 13: Especials 14: Compensació
        ET.SubElement(installment, "PaymentMeans").text = "02"
        accountToBeDebited = ET.SubElement(installment, "AccountToBeDebited")
        ET.SubElement(accountToBeDebited, "IBAN").text = invoice.payment_bank_final
    elif invoice.payment_type_token_final == bank_transfer_token:
        paymentDetails = ET.SubElement(invoiceEL, "PaymentDetails")
        installment = ET.SubElement(paymentDetails, "Installment")
        ET.SubElement(installment, "InstallmentDueDate").text = str(invoice.due_date)
        ET.SubElement(installment, "InstallmentAmount").text = "{:.2f}".format(total)
        ET.SubElement(installment, "PaymentMeans").text = "04"
        accountToBeCredited = ET.SubElement(installment, "AccountToBeCredited")
        ET.SubElement(accountToBeCredited, "IBAN").text = company_bank.iban
    
    #
    #   INVOICES: ADDITIONAL DATA
    #
    # additionalDataText = getAdditionalDataText(invoice, contract)
    additionalData = ET.SubElement(invoiceEL, "AdditionalData")
    #TODO: CHECK WHAT THIS ADDITIONAL INFO SHOULD BE
    related_documents = ET.SubElement(additionalData, "RelatedDocuments")
    attachment = ET.SubElement(related_documents, "Attachment")
    ET.SubElement(attachment, "AttachmentCompressionAlgorithm").text = "NONE"
    ET.SubElement(attachment, "AttachmentFormat").text = "pdf"
    ET.SubElement(attachment, "AttachmentEncoding").text = "BASE64"
    ET.SubElement(attachment, "AttachmentDescription").text = f"{invoice.serie_final.replace('/', '')}.pdf"
    _, _, pdf_buffer = generate_report_invoice_pdf(invoice, None, None, False)

    # Attach the raw PDF (no ZIP compression)
    pdf_bytes = pdf_buffer.getvalue()
    ET.SubElement(attachment, "AttachmentData").text = base64.b64encode(pdf_bytes).decode('utf-8')
    
    additional_information = get_einvoice_invoice_reference(invoice)
    if reading:
        if reading.previous_reading:
            additional_information += f" {invoice.consumption} M3 DESDE {reading.previous_reading.reading_date.strftime('%d/%m/%Y')} FINS A {reading.reading_date.strftime('%d/%m/%Y')}. COMPTADOR {reading.meter.code}. REF.: {contract.token if contract else invoice.customer_token_final}"
        else:
            additional_information += f" {invoice.consumption} M3. COMPTADOR {reading.meter.code}. REF.: {contract.token if contract else invoice.customer_token_final}"
    ET.SubElement(additionalData, "InvoiceAdditionalInformation").text = additional_information
    xml_string = ET.tostring(root, encoding='utf-8', xml_declaration=False).decode('utf-8')
    xml_string = '<?xml version="1.0" encoding="utf-8"?>\n' + xml_string
    
    return xml_string
    

def getAdditionalDataText(invoice, contract):

    messages = Message.objects.filter(invoices=invoice)

    if contract:
        additionalDataText = f"<contrato>{contract.token}</contrato>"
    else:
        additionalDataText = ""
    #TODO: PERIODICITAT A INVOICE?
    additionalDataText += f"<periodicidad>MENSUAL</periodicidad>"
    #get today in year and month like 2025/02
    today = datetime.now().strftime('%Y%m')
    additionalDataText += f"<periodo>{today}</periodo>"
    if contract and contract.supply_point_default:
        additionalDataText += f"<direccionSuministro>{contract.supply_point_default.address.street.name}, {contract.supply_point_default.address.street_number.token}, {contract.supply_point_default.address.postal_code}, {contract.supply_point_default.address.city.name}</direccionSuministro>"
        additionalDataText += f"<datosAdicionales></datosAdicionales>"
        additionalDataText += f"<numeroContador>{contract.supply_point_default.meter.code}</numeroContador>"
        additionalDataText += f"<calibre>{contract.supply_point_default.meter.caliber.token}</calibre>"

    """ if invoice.reading_last:
        additionalDataText += f"<fechaLecturaAnterior>{invoice.reading_last.reading_date}</fechaLecturaAnterior>"
        additionalDataText += f"<lecturaAnterior>{invoice.reading_last.reading_value}</lecturaAnterior>"

    if invoice.reading:
        additionalDataText += f"<fechaLecturaActual>{invoice.reading.reading_date}</fechaLecturaActual>"
        additionalDataText += f"<lecturaActual>{invoice.reading.reading_value}</lecturaActual>" """
        
    #TODO IMPORTANTE CHECKEA SI SE PUEDEN METER MAS LECTURAS, SI NO JUNTALAS EN UNA
    if invoice.readings and invoice.readings.count() > 0:
        for reading in invoice.readings.all():
            if reading.previous_reading:
                additionalDataText += f"<fechaLecturaAnterior>{reading.previous_reading.reading_date}</fechaLecturaAnterior>"
                additionalDataText += f"<lecturaAnterior>{reading.previous_reading.reading_value}</lecturaAnterior>"
            additionalDataText += f"<fechaLectura>{reading.reading_date}</fechaLectura>"
            additionalDataText += f"<lectura>{reading.reading_value}</lectura>"

    additionalDataText += f"<consumo>{invoice.consumption}</consumo>"

    additionalDataText += f"<bloqueComunicaciones>"
    if messages.exists():
        additionalDataText += f"<mensajesGenerados>"
        for message in messages:
            additionalDataText += f"<texto>{message.content}</texto>"
        additionalDataText += f"</mensajesGenerados>"

    #text mensajeGastoMedio, costeLitro, costeDiario
    additionalDataText += f"<mensajeGastoMedio><texto></texto></mensajeGastoMedio>"
    additionalDataText += f"<mensajeEstadistico><costeLitro></costeLitro><costeDiario></costeDiario></mensajeEstadistico>"

    additionalDataText += f"</bloqueComunicaciones>"

    #last distance i media?
    """ 
    <bloqueEstadisticas>
    <last>250</last>
    <distance>50</distance>
    <media>141,00</media>
    <valores>
    <periodo>
    <etiqueta>09/24</etiqueta>
    <consumo>130</consumo>
    </periodo>
    <periodo>
    <etiqueta>10/24</etiqueta>
    <consumo>169</consumo>
    </periodo>
    <periodo>
    <etiqueta>11/24</etiqueta>
    <consumo>137</consumo>
    </periodo>
    <periodo>
    <etiqueta>12/24</etiqueta>
    <consumo>127</consumo>
    </periodo>
    <periodo>
    <etiqueta>01/25</etiqueta>
    <consumo>137</consumo>
    </periodo>
    <periodo>
    <etiqueta>02/25</etiqueta>
    <consumo>146</consumo>
    </periodo>
    </valores>
    </bloqueEstadisticas>
    """
    return additionalDataText
    