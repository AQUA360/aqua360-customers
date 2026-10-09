from django.urls import include, path
from rest_framework import routers

from contract.views.contract_tenant_change_document_type_view import ContractTenantChangeDocumentTypeViewSet
from documentmanager.views_export.generic_export_view import GenericExportView

from billing.views.piggy_bank_get_related_data_view import PiggyBankGetRelatedDataViewSet
from billing.views.piggy_bank_handle_balance_view import PiggyBankHandleBalanceViewSet
from contract.views.aca_document_view import ACADocumentViewSet
from contract.views.aca_document_change_view import ACADocumentChangeViewSet
from contract.views.aca_document_status_view import ACADocumentStatusViewSet
from contract.views.aca_bonification_view import ACABonificationRequestViewSet
from contract.views.bail_view import BailViewSet
from contract.views.contract_request_finalize_view import FinalizeContractRequestView
from contract.views.contract_request_finalize_in_place_view import FinalizeContractRequestInPlaceView
from contract.views.contract_request_view import ContractRequestCreateContractView
from contract.views.contract_pdf_view import ReportPDFDownloadViewSet
from contract.views.contract_tenant_change_view import ContractTenantChangeViewSet
from contract.views.contract_surrogation_document_view import ContractSurrogationDocumentViewSet
from contract.views.contract_surrogation_document_type_view import ContractSurrogationDocumentTypeViewSet
from contract.views.contract_termination_request_observation_view import ContractTerminationRequestObservationViewSet
from contract.views.close_contract_termination_request_view import CloseContractTerminationRequestViewSet
from contract.views.bail_type_view import BailTypeViewSet
from contract.views.bonification_view import BonificationViewSet
from contract.views.contract_category_view import ContractCategoryViewSet
from contract.views.contract_client_type_view import ContractClientTypeViewSet
from contract.views.contract_observation_view import ContractObservationViewSet
from contract.views.contract_request_status_view import ContractRequestStatusViewSet
from contract.views.contract_request_type_view import ContractRequestTypeViewSet
from contract.views.contract_request_view import ContractRequestViewSet
from contract.views.contract_status_view import ContractStatusViewSet
from contract.views.contract_use_type_view import ContractUseTypeViewSet
from contract.views.contract_view import ContractViewSet
from contract.views.general_invoice_view import GeneralInvoiceViewSet
from contract.views.piggy_bank_movement_view import PiggyBankMovementViewSet
from contract.views.piggy_bank_view import PiggyBankViewSet
from contract.views.variable_view import VariableViewSet
from contract.views.bonification_type_view import BonificationTypeViewSet
from contract.views.bonification_type_documentation_type_view import BonificationTypeDocumentationTypeViewSet
from contract.views.contract_representative_type_view import ContractRepresentativeTypeViewSet
from contract.views.variable_type_view import VariableTypeViewSet
from contract.views.contract_representative_view import ContractRepresentativeViewSet
from contract.views.contract_request_documentation_type_view import ContractRequestDocumentationTypeViewSet
from contract.views.contract_payment_view import ContractPaymentViewSet
from contract.views.contract_payment_type_view import PaymentTypeViewSet
from contract.views.contract_surrogation_type_view import ContractSurrogationTypeViewSet
from contract.views.contract_surrogation_view import ContractSurrogationViewSet
from contract.views.contract_termination_request_status_view import ContractTerminationRequestStatusViewSet
from contract.views.contract_termination_request_type_view import ContractTerminationRequestTypeViewSet
from contract.views.contract_termination_request_view import ContractTerminationRequestViewSet
from contract.views.contract_clause_view import ContractClauseViewSet
from contract.views.clause_template_view import ClauseTemplateViewSet
from contract.views.contract_request_observation_view import ContractRequestObservationViewSet
from contract.views.bonification_documentation_view import BonificationDocumentationViewSet
from contract.views.contract_request_documentation_view import ContractRequestDocumentationViewSet
from contract.views.contract_data_change_view import ContractDataChangeViewSet
from contract.views.bail_status_view import BailStatusViewSet
from contract.views.bail_return_view import BailReturnViewSet
from contract.views.contract_debt_management_view import ContractDebtManagementViewSet
from contract.views.contract_manage_massively_view import ContractManageMassivelyViewSet
from contract.views.contract_create_view import ContractCreateView
from contract.views.contract_ov_view import ContractOVView
from contract.views.contract_ov_billing_view import ContractOVBillingView
from contract.views.contract_documentation_type_view import ContractDocumentationTypeViewSet
from contract.views.consumption_management_view import ConsumptionManagementViewSet
from contract.views.contract_use_aca_view import ContractUseAcaView

router = routers.DefaultRouter()

router.register(r'bail', BailViewSet)
router.register(r'bail-type', BailTypeViewSet)
router.register(r'bail-status', BailStatusViewSet)
router.register(r'bonification', BonificationViewSet)
router.register(r'bonification-documentation', BonificationDocumentationViewSet)
router.register(r'bonification-type-documentation-type', BonificationTypeDocumentationTypeViewSet)
router.register(r'bonification-type', BonificationTypeViewSet)

router.register(r'piggy-bank', PiggyBankViewSet)
router.register(r'piggy-bank-movement', PiggyBankMovementViewSet)

router.register(r'contract-payment-type', PaymentTypeViewSet)
router.register(r'contract-payment', ContractPaymentViewSet)

router.register(r'contract-request-documentation-type', ContractRequestDocumentationTypeViewSet)
router.register(r'contract-documentation-type', ContractDocumentationTypeViewSet)
router.register(r'contract-request-documentation', ContractRequestDocumentationViewSet)
router.register(r'contract-request-observation', ContractRequestObservationViewSet)
router.register(r'contract-request-status', ContractRequestStatusViewSet)
router.register(r'contract-request-type', ContractRequestTypeViewSet)
router.register(r'contract-request', ContractRequestViewSet)

router.register(r'general-invoice', GeneralInvoiceViewSet)

router.register(r'contract-data-change', ContractDataChangeViewSet)
router.register(r'contract-tenant-change', ContractTenantChangeViewSet)
router.register(r'contract-tenant-change-document-type', ContractTenantChangeDocumentTypeViewSet)

router.register(r'contract-surrogation', ContractSurrogationViewSet)
router.register(r'contract-surrogation-type', ContractSurrogationTypeViewSet)
router.register(r'contract-surrogation-document', ContractSurrogationDocumentViewSet)
router.register(r'contract-surrogation-document-type', ContractSurrogationDocumentTypeViewSet)

router.register(r'contract-termination-request-observation', ContractTerminationRequestObservationViewSet)
router.register(r'contract-termination-request-status', ContractTerminationRequestStatusViewSet)
router.register(r'contract-termination-request-type', ContractTerminationRequestTypeViewSet)
router.register(r'contract-termination-request', ContractTerminationRequestViewSet)

router.register(r'contract-clauses', ContractClauseViewSet)
router.register(r'clause-template', ClauseTemplateViewSet)

router.register(r'contract-debt-management', ContractDebtManagementViewSet)
router.register(r'contract-use-type', ContractUseTypeViewSet)
router.register(r'contract-category', ContractCategoryViewSet)
router.register(r'contract-client-type', ContractClientTypeViewSet)
router.register(r'contract-status', ContractStatusViewSet)
router.register(r'contract-representative-type', ContractRepresentativeTypeViewSet)
router.register(r'contract-observation', ContractObservationViewSet)
router.register(r'contract-representative', ContractRepresentativeViewSet)
router.register(r'contract', ContractViewSet, basename='contract')
router.register(r'consumption-management', ConsumptionManagementViewSet, basename='consumption-management')

router.register(r'variable-type', VariableTypeViewSet)
router.register(r'variable', VariableViewSet)
router.register(r'aca-document', ACADocumentViewSet)
router.register(r'aca-document-change', ACADocumentChangeViewSet)
router.register(r'aca-document-status', ACADocumentStatusViewSet)
router.register(r'aca-bonification-request', ACABonificationRequestViewSet, basename='aca-bonification-request')

urlpatterns = [
    # Han d'anar abans d'`include(router.urls)`: el router registra `<recurs>/<pk>/`
    # amb un patró de pk genèric que, si es col·loca abans, capturaria "export" com a pk.
    path('bail/export/', GenericExportView.as_view(entity='bail'), name='bail-export'),
    path('contract-request/export/', GenericExportView.as_view(entity='contract_request'), name='contract-request-export'),
    path('contract-termination-request/export/', GenericExportView.as_view(entity='contract_termination_request'), name='contract-termination-request-export'),
    path('', include(router.urls)),
    path('download/<int:id>/', ReportPDFDownloadViewSet.as_view(), name='download-contract-pdf'),
    path('bail/return/<int:id>/', BailReturnViewSet.as_view(http_method_names=['put']), name='bail-return'),
    path('contract-termination-request/close/<int:id>', CloseContractTerminationRequestViewSet.as_view(http_method_names=['put']), name='close-contract-termination-request'),
    path('contract-request/contract-create/<int:id>', ContractRequestCreateContractView.as_view(http_method_names=['put']), name='contract-create'),
    path('contract-request/finalize/<int:contract_request_id>/', FinalizeContractRequestView.as_view(), name='finalize_contract_request'),
    path('contract-request/finalize-in-place/<int:contract_request_id>/', FinalizeContractRequestInPlaceView.as_view(), name='finalize_contract_request_in_place'),
    path('contract-request/contract-create/<int:contract_request_id>/', ContractCreateView.as_view(), name='contract_create'),
    path('contract-manage/', ContractManageMassivelyViewSet.as_view(), name='contract-manage-massively'),
    path('contract-use-aca/', ContractUseAcaView.as_view(), name='contract-use-aca'),
    path('piggy-bank-get-related-data/', PiggyBankGetRelatedDataViewSet.as_view(http_method_names=['get']), name='piggy-bank-get-related-data'),
    path('piggy-bank-handle-balance/', PiggyBankHandleBalanceViewSet.as_view(http_method_names=['post']), name='piggy-bank-handle-balance'),
    #Oficina Virtual
    path('contract-ov/<str:contract_token>/', ContractOVView.as_view(), name='contract-ov'),
    path('contract-ov/billing/<str:contract_token>/', ContractOVBillingView.as_view(), name='contract-ov-billing'),
]