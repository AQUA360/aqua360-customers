from django.urls import include, path
from rest_framework import routers

from .views import *

router = routers.DefaultRouter()
router.register(r'connection-status', LogConnectionStatusViewSet)
router.register(r'connection-request-status', LogConnectionRequestStatusViewSet)
router.register(r'supply-cut-status', LogSupplyCutStatusViewSet)
router.register(r'supply-point-change', LogSupplyPointChangeViewSet)
router.register(r'contract-request-status', LogContractRequestStatusViewSet)
router.register(r'order-status', LogOrderStatusViewSet)
router.register(r'invoice-status', LogInvoiceChangeStatusViewSet)
router.register(r'invoice-data', LogInvoiceDataChangeViewSet)
router.register(r'contract-data', LogContractDataChangeViewSet, basename='contract-data')
router.register(r'bail-status', LogBailStatusViewSet)
router.register(r'contract-total-members', LogContractTotalMembersViewSet)
router.register(r'contract-phones', LogContractPhonesViewSet)
router.register(r'contract-bonifications-variables-change', LogContractBonificationsVariablesChangeViewSet)
router.register(r'contract-expired-bonifications-variables', LogContractExpiredBonificationsVariablesViewSet)
router.register(r'claim-request-contract-change', LogClaimRequestContractChangeViewSet)
router.register(r'commitment-deposit-movement', LogCommitmentDepositMovementViewSet)
router.register(r'payment-status', LogPaymentStatusChangeViewSet)
router.register(r'fraud-status', LogFraudStatusChangeViewSet)
router.register(r'incident-status', LogIncidentStatusChangeViewSet)
router.register(r'communication-status', LogCommunicationStatusChangeViewSet)
router.register(r'communication-process-status', LogCommunicationProcessStatusChangeViewSet)
router.register(r'reading-change', LogReadingChangeViewSet)
router.register(r'joined-payment-status', LogJoinedPaymentStatusChangeViewSet)
router.register(r'communication-change', LogCommunicationChangeViewSet)
router.register(r'product-change', LogProductChangeViewSet)
router.register(r'price-rate-change', LogPriceRateChangeViewSet)

urlpatterns = [
    path('ov_logs/', OVLogsAPIView.as_view(), name='ov_logs'),
    path('ov_logs/<str:log_id>/', OVLogsAPIView.as_view(), name='ov_log_detail'),
    path('', include(router.urls))
]
