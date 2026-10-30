from django.urls import path
from .views import (
    ContractOVView,
    BillingDataOVView,
    BillingContractInvoicesOVView,
    BillingContractInvoiceOVView,
    UnpayedInvoicesOVView,
    BilledConsumptionsOVView,
    InvoicePDFView,
    BillingDataOVUpdateIBANView,
    InvoicePaidView,
    QuickPayOVView,
    PaymentReceiptOVView,
    InvoiceReturnRequestOVView,
    CreateReadingOVView,
    ContractsListOVView,
    ContractDetailByTokenOVView,
    ContractByNicView,
    InvoiceDetailByTokenOVView,
    MeterDetailByTokenOVView,
    ConsumptionHistoryOVView,
    ConsumptionDownloadOVView,
    ConsumptionsDownloadOVView,
    BillingPeriodsOVView,
    SepaDocumentUploadView,
    SepaDocumentDownloadView,
    CancelDirectDebitView,
    ContractProcedureOVView,
    ContractRequestStatusOVView,
    ContactDataOVView,
    PersonDataOVView,
    BatchInvoiceDownloadView,
    ContractStatusDictionaryOVView,
    PaymentTypeDictionaryOVView,
    InvoiceStatusDictionaryOVView,
    ProcedureTariffDictionaryOVView,
    PropertiesOVView,
)

urlpatterns = [
    # /ov/conatrct-detail/?contract_token=<token>
    path("contract-detail/", ContractOVView.as_view(), name="contract-ov"),
    # /ov/billing-data/?contract_token=<token>
    path(
        "billing-data/", BillingDataOVView.as_view(), name="billing-data-ov"
    ),  # Get and Post methods
    # /ov/billing-data/update-iban/?contract_token=<token>
    path(
        "billing-data/update-iban/",
        BillingDataOVUpdateIBANView.as_view(),
        name="update-iban-ov",
    ),  # Post method
    # /ov/contact-data/?contract_token=<token>
    path(
        "contact-data/",
        ContactDataOVView.as_view(),
        name="contact-data-ov",
    ),  # Get method
    # /ov/person-data/?dni=<DNI>
    path(
        "person-data/",
        PersonDataOVView.as_view(),
        name="person-data-ov",
    ),  # Get method
    # /ov/invoices/?contract_token=<token>
    path("invoices/", BillingContractInvoicesOVView.as_view(), name="invoices-ov"),
    # /ov/invoices/download/?contract_token=<token>  body: {invoice_tokens: [...]}
    path(
        "invoices/download/",
        BatchInvoiceDownloadView.as_view(),
        name="batch-invoice-download-ov",
    ),
    # /ov/invoice/?contract_token=<token>&invoice_token=<token>
    path("invoice/", BillingContractInvoiceOVView.as_view(), name="invoice-ov"),
    # post -> body
    path("invoice/paid/", InvoicePaidView.as_view(), name="invoice-paid-ov"),
    # post -> body {contract_number, invoice_number, amount}
    path("invoice/quick-pay/", QuickPayOVView.as_view(), name="quick-pay-ov"),
    # get -> ?contract_token=<token>&payment_token=<token>&dni=<DNI>
    path(
        "payment-receipt/",
        PaymentReceiptOVView.as_view(),
        name="payment-receipt-ov",
    ),
    # post -> body {invoice_token, contract_token, reason}
    path(
        "invoice/return-request/",
        InvoiceReturnRequestOVView.as_view(),
        name="invoice-return-request-ov",
    ),
    # here we can filter by statuses query param, comma separated like ? statuses=-3,1
    # e.g. with demo data the link will be like:
    # /ov/unpayed-invoices/?contract_token=<token>&statuses=<invoice_status_token>
    # ...&exc_payment_type_token=<payment_type_token>
    path(
        "unpayed-invoices/", UnpayedInvoicesOVView.as_view(), name="unpayed-invoices-ov"
    ),
    # /ov/billed-consumptions/?contract_token=<token>
    path(
        "billed-consumptions/",
        BilledConsumptionsOVView.as_view(),
        name="billed-consumptions-ov",
    ),
    # /ov/invoice-pdf/?contract_token=<token>&invoice_token=<token>
    path("invoice-pdf/", InvoicePDFView.as_view(), name="invoice-pdf-ov"),
    # /ov/create-reading/ POST body: {"reading_at": "YYYY-mm-dd", "contract": "<token>", "meter": "<token>", "reading": <value>}
    path("create-reading/", CreateReadingOVView.as_view(), name="create-reading-ov"),
    # /ov/consumptions/?contract_token=<token>[&date_from=&date_to=&page=&page_size=]
    path("consumptions/", ConsumptionHistoryOVView.as_view(), name="consumptions-ov"),
    # /ov/consumption/<id>/download/?contract_token=<token>[&format=pdf|csv]
    path(
        "consumption/<int:id>/download/",
        ConsumptionDownloadOVView.as_view(),
        name="consumption-download-ov",
    ),
    # /ov/consumptions/download/ POST body: {contract_token, reading_ids?, date_from?, date_to?, format?}
    path(
        "consumptions/download/",
        ConsumptionsDownloadOVView.as_view(),
        name="consumptions-download-ov",
    ),
    # /ov/billing-periods/?contract_token=<token>
    path("billing-periods/", BillingPeriodsOVView.as_view(), name="billing-periods-ov"),
    # /ov/contracts/?dni=<DNI>&estado=<status_token>&page=<n>&limit=<n>
    path("contracts/", ContractsListOVView.as_view(), name="contracts-ov"),
    # /ov/contract/by-nic/<nic>/   (nic conté «/» amb 1 o 2 barres, p. ex.
    # 12345/1234 o 012345/654321/12345678; <path:nic>
    # evita que el ruter retalli el NIC i acabi en 404 de ruta)
    path(
        "contract/by-nic/<path:nic>/",
        ContractByNicView.as_view(),
        name="contract-by-nic-ov",
    ),
    # /ov/contract/<token>/
    path(
        "contract/<str:token>/",
        ContractDetailByTokenOVView.as_view(),
        name="contract-detail-by-token-ov",
    ),
    # /ov/meter/<token>/
    path(
        "meter/<str:token>/",
        MeterDetailByTokenOVView.as_view(),
        name="meter-detail-by-token-ov",
    ),
    # /ov/procedures/contract/  POST body: alta de contracte (ContractRequest)
    # Ruta de dos segments; no entra en conflicte amb
    # procedures/<contract_token>/upload-sepa-signed/ (quatre segments).
    path(
        "procedures/contract/",
        ContractProcedureOVView.as_view(),
        name="contract-procedure-ov",
    ),
    # /ov/procedures/contract/<contract_request_token>/
    # Tres segments: no confon amb procedures/contract/ (dos segments) ni amb
    # procedures/<contract_token>/<accio>/ (quatre segments).
    path(
        "procedures/contract/<str:contract_request_token>/",
        ContractRequestStatusOVView.as_view(),
        name="contract-request-status-ov",
    ),
    # /ov/procedures/<contract_token>/upload-sepa-signed/
    path(
        "procedures/<str:contract_token>/upload-sepa-signed/",
        SepaDocumentUploadView.as_view(),
        name="upload-sepa-signed-ov",
    ),
    # /ov/procedures/<contract_token>/sepa-signed/
    path(
        "procedures/<str:contract_token>/sepa-signed/",
        SepaDocumentDownloadView.as_view(),
        name="sepa-signed-ov",
    ),
    # /ov/procedures/<contract_token>/cancel-direct-debit/
    path(
        "procedures/<str:contract_token>/cancel-direct-debit/",
        CancelDirectDebitView.as_view(),
        name="cancel-direct-debit-ov",
    ),
    # /ov/invoice/<token>/detail/
    path(
        "invoice/<str:token>/detail/",
        InvoiceDetailByTokenOVView.as_view(),
        name="invoice-detail-by-token-ov",
    ),
    # /ov/dictionary/contract-statuses/
    path(
        "dictionary/contract-statuses/",
        ContractStatusDictionaryOVView.as_view(),
        name="contract-statuses-dictionary-ov",
    ),
    # /ov/dictionary/payment-types/
    path(
        "dictionary/payment-types/",
        PaymentTypeDictionaryOVView.as_view(),
        name="payment-types-dictionary-ov",
    ),
    # /ov/dictionary/invoice-statuses/
    path(
        "dictionary/invoice-statuses/",
        InvoiceStatusDictionaryOVView.as_view(),
        name="invoice-statuses-dictionary-ov",
    ),
    # /ov/dictionary/procedure-tariffs/
    path(
        "dictionary/procedure-tariffs/",
        ProcedureTariffDictionaryOVView.as_view(),
        name="procedure-tariffs-dictionary-ov",
    ),
    # /ov/properties/?search=<text>
    path("properties/", PropertiesOVView.as_view(), name="properties-ov"),
]

