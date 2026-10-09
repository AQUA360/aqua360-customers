from django.urls import include, path
from rest_framework import routers

from documentmanager.views_export.generic_export_view import GenericExportView

from claimrequest.views.vulnerability_request_type_view import VulnerabilityRequestTypeViewSet
from .views.claim_request_template_view import ClaimRequestTemplateViewSet
from .views.claim_request_step_template_view import ClaimRequestStepTemplateViewSet
from .views.claim_request_view import ClaimRequestViewSet, ClaimRequestContractsViewSet, MarkContractsVulnerableViewSet
from .views.claim_step_view import ClaimRequestStepViewSet
from .views.claim_request_status_view import ClaimRequestStatusViewSet
from .views.claim_document_type_view import ClaimDocumentTypeViewSet
from .views.vulnerability_request_view import VulnerabilityRequestViewSet
from .views.vulnerability_request_status_view import VulnerabilityRequestStatusViewSet
from .views.vulnerability_request_documentation_view import VulnerabilityRequestDocumentationViewSet
from .views.vulnerability_request_observation_view import VulnerabilityRequestObservationViewSet
from .views.claim_manage_view import ClaimManageViewSet, ExcludeContractViewSet
from .views.claim_request_excel_generate_view import ClaimRequestExcelGenerateViewSet
from .views.claim_document_pdf_view import ClaimDocumentPDFDownloadViewSet
from .views.massive_termination_contract_view import MassiveTerminationContractViewSet
from .views.vulnerability_request_massive_view import MassiveVulnerabilityRequestViewSet

router = routers.DefaultRouter()
router.register(r'claim-request-template', ClaimRequestTemplateViewSet)
router.register(r'claim-request-step-template', ClaimRequestStepTemplateViewSet)

router.register(r'claim-request', ClaimRequestViewSet)
router.register(r'claim-request-step', ClaimRequestStepViewSet)

router.register(r'claim-request-status', ClaimRequestStatusViewSet)
router.register(r'claim-request-contracts', ClaimRequestContractsViewSet, basename='claim-request-contracts')

router.register(r'claim-document-type', ClaimDocumentTypeViewSet)

router.register(r'vulnerability-request', VulnerabilityRequestViewSet)
router.register(r'vulnerability-request-status', VulnerabilityRequestStatusViewSet)
router.register(r'vulnerability-request-type', VulnerabilityRequestTypeViewSet)
router.register(r'vulnerability-request-documentation', VulnerabilityRequestDocumentationViewSet)
router.register(r'vulnerability-request-observation', VulnerabilityRequestObservationViewSet)


urlpatterns = [
    # Ha d'anar abans d'`include(router.urls)`: el router registra `claim-request/<pk>/`
    # amb un patró de pk genèric que, si es col·loca abans, capturaria "export" com a pk.
    path('claim-request/export/', GenericExportView.as_view(entity='claim_request'), name='claim-request-export'),
    path('', include(router.urls)),
    path('claim-request-data/', ClaimManageViewSet.as_view(http_method_names=['get', 'post']), name='manage-claims'),
    path('claim-request/<int:id>/steps/', ClaimRequestStepViewSet.as_view({'get': 'retrieve'})),
    path('claim-request/<int:id>/contracts/', ClaimRequestContractsViewSet.as_view({'get': 'retrieve'})),
    path('claim-request/excel/<int:id>/', ClaimRequestExcelGenerateViewSet.as_view()),
    path('claim-request-manage/mark-contracts-vulnerable/', MarkContractsVulnerableViewSet.as_view(http_method_names=['post']), name='mark-contracts-vulnerable'),
    path('claim-request-manage/exclude-contract/', ExcludeContractViewSet.as_view(http_method_names=['post']), name='exclude-contract'),
    path('claim-request-manage/massive-termination-contract/', MassiveTerminationContractViewSet.as_view(http_method_names=['post']), name='massive-termination-contract'),
    path('download-claim-document/<int:id>/', ClaimDocumentPDFDownloadViewSet.as_view(), name='download-claim-doc-pdf'),
    path('claim-request-excel-generate/<int:id>/', ClaimRequestExcelGenerateViewSet.as_view(), name='claim-request-excel-generate'),
    path('vulnerability-request-massive-manage/', MassiveVulnerabilityRequestViewSet.as_view(http_method_names=['post']), name='massive-vulnerability-request'),
] 