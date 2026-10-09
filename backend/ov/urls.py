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
    CreateReadingOVView,
    ContractsListOVView,
    ContractDetailByTokenOVView,
    InvoiceDetailByTokenOVView,
    MeterDetailByTokenOVView,
    ConsumptionHistoryOVView,
    ConsumptionDownloadOVView,
    ConsumptionsDownloadOVView,
    BillingPeriodsOVView,
    SepaDocumentUploadView,
    CancelDirectDebitView,
    ContactDataOVView,
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
    # /ov/invoices/?contract_token=<token>
    path("invoices/", BillingContractInvoicesOVView.as_view(), name="invoices-ov"),
    # /ov/invoice/?contract_token=<token>&invoice_token=<token>
    path("invoice/", BillingContractInvoiceOVView.as_view(), name="invoice-ov"),
    # post -> body
    path("invoice/paid/", InvoicePaidView.as_view(), name="invoice-paid-ov"),
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
    # /ov/procedures/<contract_token>/upload-sepa-signed/
    path(
        "procedures/<str:contract_token>/upload-sepa-signed/",
        SepaDocumentUploadView.as_view(),
        name="upload-sepa-signed-ov",
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
]

