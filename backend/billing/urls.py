from django.urls import include, path
from rest_framework import routers

from billing.views.billing_preinvoices_assign_readings_view import BillingPreInvoicesAssignReadingsViewSet
from billing.views.billing_readings_view import BillingReadingsViewSet
from billing.views.config_aca_view import ConfigAcaViewSet
from billing.views.update_config_aca_view import UpdateConfigAcaView
from billing.views.joined_payment_observation_view import JoinedPaymentObservationViewSet
from billing.views.joined_payment_status_view import JoinedPaymentStatusViewSet
from billing.views.joined_payment_view import JoinedPaymentViewSet
from billing.views.payment_movement_view import PaymentMovementViewSet
from billing.views.payment_remittance_return_view import PaymentRemittanceReturnViewSet
from billing.views.reading_by_batch_csv_export_view import ReadingByBatchCSVExportView
from billing.views.reading_batch_supply_points_csv_export_view import ReadingBatchSupplyPointsCSVExportView
from billing.views.estimated_bag_movement_view import EstimatedBagMovementViewSet
from billing.views.generate_payment_doc_view import GeneratePaymentDocDownloadViewSet
from billing.views.invoice_view import InvoiceViewSet
from billing.views.invoice_manage_massively_view import InvoiceManageMassivelyViewSet
from billing.views.payment_doc_view import PaymentDocDownloadViewSet
from billing.views.payment_proof_view import PaymentProofDownloadViewSet
from billing.views.payment_remittance_status_view import PaymentRemittanceStatusViewSet
from billing.views.payment_remittance_view import PaymentRemittanceViewSet
from billing.views.reading_batch_estimate_view import ReadingBatchEstimateViewSet
from billing.views.reading_batch_setup_view import ReadingBatchSetupViewSet
from billing.views.reading_batch_template_view import ReadingBatchTemplateViewSet
from billing.views.general_payment_sepa_document_view import GeneralPaymentSepaDocumentViewSet
from billing.views.remote_reading_alert_type_view import RemoteReadingAlertViewSet
from billing.views.sepa_pdf_view import SepaPDFDownloadViewSet
from billing.views.contract_sepa_pdf_view import ContractSepaPDFView
from documentmanager.views_export.generic_export_view import GenericExportView

from .views.reading_view import ReadingViewSet, ReadingDetailViewSet
from .views.reading_document_view import ReadingDocumentViewSet
from .views.reading_batch_view import ReadingBatchViewSet
from .views.billing_batch_view import BillingBatchViewSet
from .views.billing_batch_generate_view import BillingBatchDocumentsView, BillingQueueListView, BillingQueueStatusView, BillingQueueActionView
from .views.reading_batch_status_view import ReadingBatchStatusViewSet
from .views.billing_batch_status_view import BillingBatchStatusViewSet
from .views.reading_alert_type_view import ReadingAlertViewSet
from .views.reader_alert_view import ReaderAlertViewSet
from .views.estimated_bag_view import EstimatedBagViewSet
from .views.biller_view import BillerViewSet
# from .views.billing_batch_template_view import BillingBatchTemplateViewSet
from .views.billing_status_view import BillingStatusViewSet
from .views.billing_view import BillingViewSet, BillingRoutesView, BillingBadgesView, StartBillingView
from .views.invoice_status_view import InvoiceStatusViewSet
from .views.invoice_warning_view import InvoiceWarningViewSet
from .views.invoice_type_view import InvoiceTypeViewSet
from .views.invoice_category_view import InvoiceCategoryViewSet
from .views.invoice_serie_view import InvoiceSerieViewSet
from .views.invoice_sequence_view import InvoiceSequenceViewSet
from .views.invoice_line_item_view import InvoiceLineItemViewSet
from .views.invoice_template_view import InvoiceTemplateViewSet
from .views.general_payment_view import GeneralPaymentViewSet
from .views.payment_view import PaymentViewSet
from .views.payment_status_view import PaymentStatusViewSet
from .views.value_objects_view import BankRNDDocumentViewSet, InvoiceSuppressionReasonViewSet, RejectMotiveTypeViewSet, RejectMotiveViewSet, InvoiceClassViewSet
from .views.commitment_deposit_view import CommitmentDepositViewSet
from .views.commitment_deposit_status_view import CommitmentDepositStatusViewSet
from .views.commitment_deposit_observation_view import CommitmentDepositObservationViewSet
from .views.payment_commitment_view import PaymentCommitmentViewSet
from .views.payment_commitment_status_view import PaymentCommitmentStatusViewSet
from .views.message_view import MessageViewSet
from .views.message_condition_view import MessageConditionViewSet
from .views.document_SEPA_view import DocumentSEPAViewSet
from .views.document_SEPA_line_view import DocumentSEPALineViewSet
from .views.reading_batch_generate_view import ReadingBatchSummaryView, ReadingBatchRevertView
from .views.billing_batch_generate_view import BillingBatchSummaryView
from .views.exclude_reading_view import ExcludeReadingView
from .views.exclude_billing_view import ExcludeBillingView
from .views.invoice_generate_temporary_pdf_view import InvoiceGenerateTemporaryPDFView
from .views.invoice_contract_generate_view import InvoiceContractGenerateView
from .views.invoice_connection_generate_view import InvoiceConnectionGenerateView
from .views.manage_new_budget_line_view import ManageNewBudgetLineView
from .views.generate_invoice_budget_view import GenerateInvoiceBudgetView
from .views.sepa_payment_document_generate_view import SEPAPaymentDocumentGenerateViewSet, SEPAPaymentInvoicesViewSet, SEPAPaymentAnomaliesViewSet, SEPAPaymentFilesPreviewViewSet
from .views.payment_remittance_regenerate_sepa_view import PaymentRemittanceRegenerateSepaView
from .views.epayment_document_generate_view import EPaymentDocumentGenerateViewSet
from .views.detailed_billing_document_generate_view import DetailedBillingDocumentGenerateView
from .views.generate_sgttxs_document_view import GenerateSgtTxsDocumentView
from .views.commitment_deposit_pdf_view import CommitmentDepositPDFDownloadViewSet
from .views.billing_invoices_view import BillingInvoicesViewSet, BillingInvoicesSummaryViewSet, BillingInvoicesPdfViewSet
from .views.invoice_mark_reviewed_range_view import InvoiceMarkReviewedRangeView
from .views.invoice_reviewed_range_preview_view import InvoiceReviewedRangePreviewView
from .views.billing_batch_regenerate_view import BillingBatchRegenerateView
from .views.billing_regenerate_pdfs_view import BillingRegeneratePDFsView, BillingRegeneratePDFsStatusView
from .views.wincen_export_view import WinCenExportView, WinCenExportStatusView
from .views.billing_preinvoices_summary_view import BillingPreInvoicesSummaryViewSet
from .views.billing_preinvoices_summary_xls_view import BillingPreInvoicesSummaryXLSViewSet
from .views.invoice_pdf_view import InvoiceReportPDFDownloadViewSet
from .views.invoice_send_email_view import InvoiceSendEmailView
from .views.sepa_document_send_email_view import SepaDocumentSendEmailView
from .views.invoice_generate_pdf_view import InvoiceGeneratePDFViewSet
from .views.return_sepa_document import ReturnSEPADocument
from .views.sepa_xsd_validate_view import SepaXsdValidateView
from .views.bank_rnd_view import BankRNDDocumentView
from .views.manage_deliquency_view import ManageDeliquencyViewSet
from .views.manage_commitment_deposit_request_view import ManageCommitmentDepositRequestViewSet
from .views.billing_data_ov_view import BillingDataOVView
from .views.billing_contract_invoices_ov_view import *
from .views.invoice_budget_view import InvoiceBudgetView
from .views.payment_type_view import PaymentTypeViewSet
from .views.contract_estimation_view import ContractEstimationView
from .views.invoice_clavegueram_export_view import InvoiceClavegueramExcelExportView
from .views.exclude_invoice_view import ExcludeInvoiceView
from .views.smart_metering_meter_reading_view import SmartMeteringMeterReadingView

router = routers.DefaultRouter()

router.register(r'reading', ReadingViewSet, basename='reading')
router.register(r'reading-document', ReadingDocumentViewSet)
router.register(r'reading-detail', ReadingDetailViewSet, basename='reading-detail')
router.register(r'reading-batch', ReadingBatchViewSet)
router.register(r'billing-batch', BillingBatchViewSet)
router.register(r'reading-batch-status', ReadingBatchStatusViewSet)
router.register(r'billing-batch-status', BillingBatchStatusViewSet)
router.register(r'reading-alert-type', ReadingAlertViewSet)
router.register(r'reader-alert', ReaderAlertViewSet)
router.register(r'remote-reading-alert', RemoteReadingAlertViewSet)

router.register(r'estimated-bag', EstimatedBagViewSet)
router.register(r'estimated-bag-movement', EstimatedBagMovementViewSet)

router.register(r'biller', BillerViewSet)
router.register(r'reading-batch-template', ReadingBatchTemplateViewSet)
# router.register(r'billing-batch-template', BillingBatchTemplateViewSet)
router.register(r'billing-status', BillingStatusViewSet)
router.register(r'billing', BillingViewSet)

router.register(r'invoice', InvoiceViewSet)
router.register(r'invoice-status', InvoiceStatusViewSet)
router.register(r'invoice-warnings', InvoiceWarningViewSet)
router.register(r'invoice-type', InvoiceTypeViewSet)
router.register(r'invoice-category', InvoiceCategoryViewSet)
router.register(r'invoice-serie', InvoiceSerieViewSet)
router.register(r'invoice-sequence', InvoiceSequenceViewSet)
router.register(r'invoice-line-item', InvoiceLineItemViewSet)
router.register(r'invoice-template', InvoiceTemplateViewSet)
router.register(r'invoice-suppression-reason', InvoiceSuppressionReasonViewSet)
router.register(r'invoice-class', InvoiceClassViewSet)
router.register(r'payment-type', PaymentTypeViewSet, basename='payment-type')

router.register(r'general-payment', GeneralPaymentViewSet)
router.register(r'general-payment-sepa-document', GeneralPaymentSepaDocumentViewSet)
router.register(r'payment', PaymentViewSet)
router.register(r'payment-status', PaymentStatusViewSet)
router.register(r'payment-movement', PaymentMovementViewSet)
router.register(r'payment-remittance', PaymentRemittanceViewSet)
router.register(r'payment-remittance-status', PaymentRemittanceStatusViewSet)
router.register(r'payment-remittance-return', PaymentRemittanceReturnViewSet)
router.register(r'joined-payment', JoinedPaymentViewSet)
router.register(r'joined-payment-status', JoinedPaymentStatusViewSet)
router.register(r'joined-payment-observation', JoinedPaymentObservationViewSet)


router.register(r'reject-motive', RejectMotiveViewSet)
router.register(r'reject-motive-type', RejectMotiveTypeViewSet)

router.register(r'commitment-deposit', CommitmentDepositViewSet)
router.register(r'commitment-deposit-status', CommitmentDepositStatusViewSet)
router.register(r'commitment-deposit-observation', CommitmentDepositObservationViewSet)
router.register(r'payment-commitment', PaymentCommitmentViewSet)
router.register(r'payment-commitment-status', PaymentCommitmentStatusViewSet)

router.register(r'message', MessageViewSet)
router.register(r'message-condition', MessageConditionViewSet)

router.register(r'document-sepa', DocumentSEPAViewSet)
router.register(r'document-sepa-line', DocumentSEPALineViewSet)
router.register(r'reading-batch-summary', ReadingBatchSummaryView, basename='reading-batch-summary')

router.register(r'bank-rnd-document', BankRNDDocumentViewSet)
router.register(r'config-aca', ConfigAcaViewSet)

urlpatterns = [
    path('config-aca/update/', UpdateConfigAcaView.as_view(http_method_names=['post']), name='update-config-aca'),
    path('invoice/manage-massively-paid/', InvoiceManageMassivelyViewSet.as_view(), name='invoice-manage-massively-paid'),
    path('reading/exclude/', ExcludeReadingView.as_view(http_method_names=['put']), name='exclude-reading'),
    path('exclude/', ExcludeBillingView.as_view(http_method_names=['post']), name='exclude-billing'),
    path('invoice/exclude/', ExcludeInvoiceView.as_view(http_method_names=['post']), name='exclude-invoice'),
    path('invoice/mark-reviewed-range/', InvoiceMarkReviewedRangeView.as_view(http_method_names=['post']), name='invoice-mark-reviewed-range'),
    path('invoice/reviewed-range-preview/', InvoiceReviewedRangePreviewView.as_view(http_method_names=['post']), name='invoice-reviewed-range-preview'),
    path('invoice/export/', GenericExportView.as_view(entity='invoice'), name='invoice-export'),
    path('biller/export/', GenericExportView.as_view(entity='biller'), name='biller-export'),
    path('billing/export/', GenericExportView.as_view(entity='billing'), name='billing-export'),
    path('commitment-deposit/export/', GenericExportView.as_view(entity='commitment_deposit'), name='commitment-deposit-export'),
    path('invoice-template/export/', GenericExportView.as_view(entity='invoice_template'), name='invoice-template-export'),
    path('joined-payment/export/', GenericExportView.as_view(entity='joined_payment'), name='joined-payment-export'),
    path('message/export/', GenericExportView.as_view(entity='billing_message'), name='billing-message-export'),
    path('payment/export/', GenericExportView.as_view(entity='payment'), name='payment-export'),
    path('reading-batch/export/', GenericExportView.as_view(entity='reading_batch'), name='reading-batch-export'),
    path('reading-batch-template/export/', GenericExportView.as_view(entity='reading_batch_template'), name='reading-batch-template-export'),
    path('payment-remittance/export/', GenericExportView.as_view(entity='payment_remittance'), name='payment-remittance-export'),
    path('payment-remittance-return/export/', GenericExportView.as_view(entity='payment_remittance_return'), name='payment-remittance-return-export'),
    path('', include(router.urls)),
    path('reading-batch/setup/<int:id>/', ReadingBatchSetupViewSet.as_view({'get': 'retrieve'}), name='reading-batch-setup'),
    path('reading-batch/estimate-readings/<int:id>/', ReadingBatchEstimateViewSet.as_view({'put': 'estimate_readings'}), name='reading-batch-estimate-readings'),
    path('reading-batch/<int:id>/revert/', ReadingBatchRevertView.as_view(http_method_names=['post']), name='reading-batch-revert'),
    path('billing-batch/summary', BillingBatchSummaryView.as_view(http_method_names=['post','get']), name='billing-batch-summary'),
    path('billing-routes', BillingRoutesView.as_view(http_method_names=['get']), name='billing-routes'),
    path('badges/', BillingBadgesView.as_view(http_method_names=['get']), name='billing-badges'),
    path('billing-batch/documents/<int:billing_id>/', BillingBatchDocumentsView.as_view(http_method_names=['put']), name='billing-documents'),
    path('billing-queue/', BillingQueueListView.as_view(), name='billing-queue-list'),
    path('billing-queue/<int:queue_item_id>/', BillingQueueStatusView.as_view(), name='billing-queue-status'),
    path('billing-queue/<int:queue_item_id>/action/', BillingQueueActionView.as_view(), name='billing-queue-action'),
    # path('readings', ReadingsViewSet.as_view(http_method_names=['post']), name='readings'),
    #path('invoice/generate', InvoiceGenerateView.as_view(http_method_names=['put']), name='invoice-generate'),
    path('invoice/temporary-pdf/<int:id>/', InvoiceGenerateTemporaryPDFView.as_view(http_method_names=['get']), name='invoice-generate-temporary-pdf'),
    path('invoice/contract-generate/<int:contract_request_id>/', InvoiceContractGenerateView.as_view(http_method_names=['put']), name='invoice-contract-generate'),
    path('invoice/connection-generate/<int:connection_request_id>/', InvoiceConnectionGenerateView.as_view(http_method_names=['put']), name='invoice-connection-generate'),
    path('manage-new-budget-line/', ManageNewBudgetLineView.as_view(http_method_names=['post']), name='manage-new-budget-line'),
    path('generate-invoice-budget/', GenerateInvoiceBudgetView.as_view(http_method_names=['post']), name='generate-invoice-budget'),
    path('sepa-document-generate/', SEPAPaymentDocumentGenerateViewSet.as_view(http_method_names=['put']), name='sepa-document-generate'),
    path('sepa-document-generate/invoices/', SEPAPaymentInvoicesViewSet.as_view(http_method_names=['put', 'post']), name='sepa-document-generate-invoices'),
    path('sepa-document-generate/anomalies/', SEPAPaymentAnomaliesViewSet.as_view(http_method_names=['put']), name='sepa-document-generate-anomalies'),
    path('sepa-document-generate/files/', SEPAPaymentFilesPreviewViewSet.as_view(http_method_names=['put']), name='sepa-document-generate-files'),
    path('payment-remittance/<int:id>/sepa-document-generate/', PaymentRemittanceRegenerateSepaView.as_view(http_method_names=['post']), name='payment-remittance-regenerate-sepa'),
    path('sepa/download/<int:id>/', SepaPDFDownloadViewSet.as_view(), name='download-sepa-pdf'),
    path('contract/<int:contract_id>/sepa/', ContractSepaPDFView.as_view(), name='billing-contract-sepa-pdf'),
    path('sepa-document/<int:id>/send-email/', SepaDocumentSendEmailView.as_view(http_method_names=['post']), name='sepa-document-send-email'),
    path('download-payment-doc/<int:id>/', PaymentDocDownloadViewSet.as_view(), name='download-payment-doc-pdf'),
    path('generate-payment-doc/<int:id>/', GeneratePaymentDocDownloadViewSet.as_view(), name='generate-payment-doc-pdf'),
    path('generate-payment-proof/', PaymentProofDownloadViewSet.as_view(), name='generate-payment-proof'),
    path('einvoice-document-generate/', EPaymentDocumentGenerateViewSet.as_view(http_method_names=['put', 'post']), name='einvoice-document-generate'),
    path('fd-document-generate/', DetailedBillingDocumentGenerateView.as_view(http_method_names=['put']), name='fd-document-generate'),
    path('sgttxs-document-generate/', GenerateSgtTxsDocumentView.as_view(http_method_names=['put']), name='sgttxs-document-generate'),
    path('commitment-deposit-document-generate/<int:id>/', CommitmentDepositPDFDownloadViewSet.as_view(http_method_names=['get']), name='fd-document-generate'),
    path('billing/<int:id>/readings', BillingReadingsViewSet.as_view(http_method_names=['get']), name='billing-readings'),
    path('billing/<int:id>/invoices', BillingInvoicesViewSet.as_view(http_method_names=['get']), name='billing-invoices'),
    path('billing/<int:id>/invoices/summary', BillingInvoicesSummaryViewSet.as_view(http_method_names=['get']), name='billing-invoices-summary'),
    path('billing/<int:id>/recalculate', BillingBatchRegenerateView.as_view(http_method_names=['post']), name='billing-invoices-recalculate'),
    path('billing/<int:id>/regenerate-pdfs', BillingRegeneratePDFsView.as_view(http_method_names=['post']), name='billing-regenerate-pdfs'),
    path('billing/regenerate-pdfs/status/<str:task_id>/', BillingRegeneratePDFsStatusView.as_view(http_method_names=['get']), name='billing-regenerate-pdfs-status'),
    path('billing/<int:id>/wincen-export', WinCenExportView.as_view(http_method_names=['post']), name='billing-wincen-export'),
    path('billing/wincen-export/status/<int:queue_item_id>/', WinCenExportStatusView.as_view(http_method_names=['get']), name='billing-wincen-export-status'),
    path('billing/pre-invoices/<int:id>/summary', BillingPreInvoicesSummaryViewSet.as_view(http_method_names=['get']), name='billing-preinvoices-summary'),
    path('billing/pre-invoices/<int:id>/assign-readings', BillingPreInvoicesAssignReadingsViewSet.as_view(http_method_names=['post']), name='billing-preinvoices-assign-readings'),
    path('billing/pre-invoices/<int:id>/summary/xls', BillingPreInvoicesSummaryXLSViewSet.as_view(http_method_names=['get']), name='billing-preinvoices-summary-xls'),
    path('download-invoice/<int:id>/', InvoiceReportPDFDownloadViewSet.as_view(), name='download-invoice-pdf'),
    path('invoice/<int:id>/send-email/', InvoiceSendEmailView.as_view(http_method_names=['post']), name='invoice-send-email'),
    path('download-template/', InvoiceGeneratePDFViewSet.as_view(http_method_names=['post']), name='download-template-pdf'),
    path('sepa-return/', ReturnSEPADocument.as_view(http_method_names=['put']), name='sepa-return'),
    path('sepa-validate/', SepaXsdValidateView.as_view(http_method_names=['post']), name='sepa-validate'),
    path('bank-return/', BankRNDDocumentView.as_view(http_method_names=['put', 'post']), name='bank-return'),
    path('get-deliquency/', ManageDeliquencyViewSet.as_view(http_method_names=['post']), name='manage-deliquency'),
    path('get-commitment-data/', ManageCommitmentDepositRequestViewSet.as_view(http_method_names=['post']), name='manage-commitment-deposit-request'),
    path('batch/<int:id>/pdf', BillingInvoicesPdfViewSet.as_view(http_method_names=['get']), name='billing-invoices-pdf'),
    path('start/', StartBillingView.as_view(http_method_names=['get']), name='start_billing'),
    
    path('contract-estimation/', ContractEstimationView.as_view(), name='contract-estimation'),
    path('smart-metering/meter-reading/', SmartMeteringMeterReadingView.as_view(), name='smart-metering-meter-reading'),
    # Nova URL per exportació CSV de lectures per batch
    path('reading/by-batch/csv-export/', ReadingByBatchCSVExportView.as_view(), name='reading-by-batch-csv-export'),
    # Exportació CSV de SupplyPoints de les Routes d'un ReadingBatch (+ lectura + contractes)
    path(
        'reading/by-batch/supply-points/csv-export/',
        ReadingBatchSupplyPointsCSVExportView.as_view(),
        name='reading-by-batch-supply-points-csv-export',
    ),
    
    path('invoice-budget/<int:id>/', InvoiceBudgetView.as_view(), name='invoice-budget-detail'),
    
    # Nova URL per exportació excel de clavegueram
    path('invoice/clavegueram/excel-export/', InvoiceClavegueramExcelExportView.as_view(), name='invoice-clavegueram-excel-export'),

    #Oficina Virtual
    path('contract-consumption-ov/<str:contract_token>/', ContractConsumptionOVView.as_view(), name='billing-contract-consumption-ov'),
    path('billing-data-ov/<str:contract_token>/', BillingDataOVView.as_view(), name='billing-data-ov'),
    path('contract-invoices-ov/<str:contract_token>/', BillingContractInvoicesOVView.as_view(), name='billing-contract-invoices-ov'),
    path('contract-invoices-ov/unpaid/<str:contract_token>/', BillingContractInvoicesOVUnpaidView.as_view(), name='billing-contract-invoices-ov-unpaid'),
    path('contract-invoice-ov/<str:contract_token>/<str:invoice_token>/', BillingContractInvoiceOVView.as_view(), name='billing-contract-invoice-ov'),
    path('contract-invoice-ov/pdf/<str:contract_token>/<str:invoice_token>/', BillingContractInvoiceOVPDFView.as_view(), name='billing-contract-invoice-ov-pdf'),
]