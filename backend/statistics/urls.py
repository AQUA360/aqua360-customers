from django.urls import include, path
from rest_framework import routers
from .views.reports_views import (
    ReportAccountingValuesSummary,
    ReportAquaRemittanceSummary,
    ReportBillingActiveProducts,
    ReportBillingModel347,
    ReportBillingSummary,
    ReportNoRegisterAcaBilling,
    ReportRegisterBillingSummary,
    ReportWalletSummary,
    ReportWalletBankList,
    ReportWalletBankSummary,
    ReportDetailedBillingSummary,
    ReportBillingSummaryBySupplyType,
    ReportBillingSummaryByRates,
    ReportBillingTaxesSummary,
    ReportBillingDetailedConsumptionSummary,
    ReportOrderTimeSummary,
    ReportRecaptacioSummary,
    ReportCobramentsSummary,
    ReportRecaptacioConceptesSummary,
    ReportClavegueramInvoicesSummary,
    ReportBillingTaxesDetailedSummary,
    ReportWalletBankDetailedSummary,
    ReportWalletUnpaidDetailedSummary,
    ReportWalletUnpaidSummary,
    ReportWalletAllUnpaidSummary,
    ReportWalletCashDetailedSummary,
    ReportACASummary,
    ReportBailsReport,
    ReportIncasolLiquidation,
    ReportMiniRegisterBillingSummary,
    ReportBillingSummaryByPerson,
    ReportContractsExport,
    ReportContractInvoiceReadingSummary,
    ReportContractTerminationExport,
    ReportContractTariffsExport,
    ReportGeneralBillingSummary,
    ReportDetailedTypologyPeriodicity,
    ReportDetailedConcept,
    ReportNonTariffIncome,
    ReportSubscriberEvolution,
    ReportSocialTariffEvolution,
    ReportClaimResponseTime,
    ReportManagementVolume,
    ReportTotalCustomersDebtSummary,
    ReportSgtTxt,
    ReportPendingInvoicesValuesReport,
    ReportGeneralAccounting
)
from .views.billing_report_view import BillingReportViewSet
from .views.general_report_view import GeneralReportViewSet
from .views.report_type_view import ReportTypeViewSet
from .views.accounting_code_view import AccountingCodeViewSet
from .views.accounting_value_view import AccountingValueViewSet
from .views.billing_consumption_view import BillingConsumptionViewSet
from .views.reading_batch_export_column_view import ReadingBatchExportColumnViewSet
from .views.reading_batch_import_template_view import ReadingBatchImportTemplateViewSet
from .views.reading_batch_import_column_view import ReadingBatchImportColumnViewSet
from .views.available_report_view import AvailableReportViewSet, ReportQueueListView, ReportQueueStatusView, ReportQueueActionView
from .views.update_statistics_view import TriggerDailyConsumptionUpdate, TriggerBillingConsumptionBackfill, TaskStatusView
from .views.summary_statistics_view import ConsumptionSummaryByUseType, BillingSummaryByUseType
from .views.daily_activity_view import DailyActivitySummaryView, ReportDailyActivitySummary
from .views.daily_document_status_view import DailyDocumentStatusViewSet
from .views.daily_document_template_view import DailyDocumentTemplateViewSet
from .views.daily_document_view import DailyDocumentViewSet

router = routers.DefaultRouter()

router.register(r'general-report', GeneralReportViewSet)
router.register(r'billing-report', BillingReportViewSet)
router.register(r'report-type', ReportTypeViewSet)
router.register(r'accounting-code', AccountingCodeViewSet)
router.register(r'accounting-value', AccountingValueViewSet)
router.register(r'billing-consumption', BillingConsumptionViewSet)
router.register(r'reading-batch-export-column', ReadingBatchExportColumnViewSet)
router.register(r'reading-batch-import-template', ReadingBatchImportTemplateViewSet)
router.register(r'reading-batch-import-column', ReadingBatchImportColumnViewSet)
router.register(r'available-reports', AvailableReportViewSet)
router.register(r'daily-document-status', DailyDocumentStatusViewSet)
router.register(r'daily-document-template', DailyDocumentTemplateViewSet)
router.register(r'daily-document', DailyDocumentViewSet)

urlpatterns = [
  path('', include(router.urls)),
  path('report-queue/', ReportQueueListView.as_view(), name='report-queue-list'),
  path('report-queue/<int:queue_item_id>/', ReportQueueStatusView.as_view(), name='report-queue-status'),
  path('report-queue/<int:queue_item_id>/action/', ReportQueueActionView.as_view(), name='report-queue-action'),
  path('billing/<int:id>/active-products', ReportBillingActiveProducts.as_view(http_method_names=['get']), name='report-billing-active-products'),
  path('billing/summary', ReportBillingSummary.as_view(http_method_names=['post']), name='report-billing-summary'),
  path('billing/wallet-summary', ReportWalletSummary.as_view(http_method_names=['post']), name='wallet-summary'),
  path('billing/wallet-bank-list', ReportWalletBankList.as_view(http_method_names=['post']), name='wallet-bank-list'),
  path('billing/wallet-bank-summary', ReportWalletBankSummary.as_view(http_method_names=['post']), name='wallet-bank-summary'),
  path('billing/wallet-cash-detailed-summary', ReportWalletCashDetailedSummary.as_view(http_method_names=['post']), name='wallet-cash-summary'),
  path('billing/wallet-unpaid-detailed-summary', ReportWalletUnpaidDetailedSummary.as_view(http_method_names=['post']), name='wallet-unpaid-detailed-summary'),
  path('billing/wallet-unpaid-summary', ReportWalletUnpaidSummary.as_view(http_method_names=['post']), name='wallet-unpaid-summary'),
  path('billing/wallet-all-unpaid-summary', ReportWalletAllUnpaidSummary.as_view(http_method_names=['post']), name='wallet-all-unpaid-summary'),
  path('billing/wallet-bank-detailed-summary', ReportWalletBankDetailedSummary.as_view(http_method_names=['post']), name='wallet-bank-detailed-summary'),
  path('billing/detailed-summary', ReportDetailedBillingSummary.as_view(http_method_names=['post']), name='report-detailed-billing-summary'),
  path('billing/register-billing-summary', ReportRegisterBillingSummary.as_view(http_method_names=['post']), name='report-register-billing-summary'),
  path('billing/mini-register-billing-summary', ReportMiniRegisterBillingSummary.as_view(http_method_names=['post']), name='report-mini-register-billing-summary'),
  path('billing/by-supply-type', ReportBillingSummaryBySupplyType.as_view(http_method_names=['post']), name='report-billing-summary-by-supply-type'),
  path('billing/by-rates', ReportBillingSummaryByRates.as_view(http_method_names=['post']), name='report-billing-summary-by-rates'),
  path('billing/taxes', ReportBillingTaxesSummary.as_view(http_method_names=['post']), name='report-billing-summary-taxes'),
  path('billing/aca-summary', ReportACASummary.as_view(http_method_names=['post']), name='report-billing-summary-taxes'),
  path('billing/taxes-detailed', ReportBillingTaxesDetailedSummary.as_view(http_method_names=['post']), name='report-billing-summary-taxes-detailed'),
  path('billing/detailed-consumption-summary', ReportBillingDetailedConsumptionSummary.as_view(http_method_names=['post']), name='report-billing-detailed-consumption-summary'),
  path('billing/order-time-summary', ReportOrderTimeSummary.as_view(http_method_names=['post']), name='report-order-time-summary'),
  path('billing/account-summary', ReportAccountingValuesSummary.as_view(http_method_names=['post']), name='report-accounting-summary'),
  path('billing/aqua-remittance-summary', ReportAquaRemittanceSummary.as_view(http_method_names=['post']), name='aqua-remittance-summary'),
  path('billing/bails-report', ReportBailsReport.as_view(http_method_names=['post']), name='bails-report'),
  path('billing/incasol-liquidation-report', ReportIncasolLiquidation.as_view(http_method_names=['post']), name='incasol-liquidation-report'),
  path('billing/summary-by-person', ReportBillingSummaryByPerson.as_view(http_method_names=['post']), name='report-billing-summary-by-person'),
  path('billing/model-347', ReportBillingModel347.as_view(http_method_names=['post']), name='report-billing-347'),
  path('billing/recaptacio-summary', ReportRecaptacioSummary.as_view(http_method_names=['post']), name='report-recaptacio-summary'),
  path('billing/cobraments-summary', ReportCobramentsSummary.as_view(http_method_names=['post']), name='report-cobraments-summary'),
  path('billing/recaptacio-conceptes-summary', ReportRecaptacioConceptesSummary.as_view(http_method_names=['post']), name='report-recaptacio-conceptes-summary'),
  path('billing/clavegueram-invoices-summary', ReportClavegueramInvoicesSummary.as_view(http_method_names=['post']), name='report-clavegueram-invoices-summary'),
  path('billing/total-customers-debt-summary', ReportTotalCustomersDebtSummary.as_view(http_method_names=['post']), name='report-total-customers-debt-summary'),
  path('billing/no-aca-register-billing-summary', ReportNoRegisterAcaBilling.as_view(http_method_names=['post']), name='no-aca-register-billing-summary'),
  path('billing/sgt-txt-report', ReportSgtTxt.as_view(http_method_names=['post']), name='report-sgt-txt-report'),
  path('billing/general-accounting-report', ReportGeneralAccounting.as_view(http_method_names=['post']), name='report-general-accounting-report'),
  path('billing/pending-invoices-values-report', ReportPendingInvoicesValuesReport.as_view(http_method_names=['post']), name='report-pending-invoices-values-report'),
  path(
      'contracts/export/',
      ReportContractsExport.as_view(http_method_names=['post']),
      name='report-contracts-export',
  ),
  # Alias sense barra final (evita 404 si el client no envia trailing slash)
  path(
      'contracts/export',
      ReportContractsExport.as_view(http_method_names=['post']),
  ),
  path(
      'contracts/pricerates/export/',
      ReportContractTariffsExport.as_view(http_method_names=['post']),
      name='report-contracts-pricerates-export',
  ),
  path(
      'contracts/pricerates/export',
      ReportContractTariffsExport.as_view(http_method_names=['post']),
  ),
  path(
      'contracts/invoice-reading-summary/export/',
      ReportContractInvoiceReadingSummary.as_view(http_method_names=['post']),
      name='report-contract-invoice-reading-summary',
  ),
  path(
      'contracts/invoice-reading-summary/export',
      ReportContractInvoiceReadingSummary.as_view(http_method_names=['post']),
  ),
  path(
      'contracts/termination-reading-invoice/export/',
      ReportContractTerminationExport.as_view(http_method_names=['post']),
      name='report-contract-termination-reading-invoice',
  ),
  path(
      'contracts/termination-reading-invoice/export',
      ReportContractTerminationExport.as_view(http_method_names=['post']),
  ),
  path('billing/general-billing-summary', ReportGeneralBillingSummary.as_view(http_method_names=['post']), name='report-general-billing-summary'),
  path('billing/detailed-typology-periodicity', ReportDetailedTypologyPeriodicity.as_view(http_method_names=['post']), name='report-detailed-typology-periodicity'),
  path('billing/detailed-concept', ReportDetailedConcept.as_view(http_method_names=['post']), name='report-detailed-concept'),
  path('billing/non-tariff-income', ReportNonTariffIncome.as_view(http_method_names=['post']), name='report-non-tariff-income'),
  path('billing/subscriber-evolution', ReportSubscriberEvolution.as_view(http_method_names=['post']), name='report-subscriber-evolution'),
  path('billing/social-tariff-evolution', ReportSocialTariffEvolution.as_view(http_method_names=['post']), name='report-social-tariff-evolution'),
  path('billing/claim-response-time', ReportClaimResponseTime.as_view(http_method_names=['post']), name='report-claim-response-time'),
  path('billing/management-volume', ReportManagementVolume.as_view(http_method_names=['post']), name='report-management-volume'),
  path('billing/daily-activity-summary', ReportDailyActivitySummary.as_view(http_method_names=['post']), name='report-daily-activity-summary'),

  path('update-daily-consumption', TriggerDailyConsumptionUpdate.as_view(), name='trigger-daily-consumption'),
  path('update-billing-backfill', TriggerBillingConsumptionBackfill.as_view(), name='trigger-billing-backfill'),
  path('task-status/<str:task_id>/', TaskStatusView.as_view(), name='task-status'),
  
  # Resums per frontal
  path('summary-consumption-by-use', ConsumptionSummaryByUseType.as_view(), name='summary-consumption-by-use'),
  path('summary-billing-by-use', BillingSummaryByUseType.as_view(), name='summary-billing-by-use'),
  path('daily-activity-summary', DailyActivitySummaryView.as_view(), name='daily-activity-summary'),
]
