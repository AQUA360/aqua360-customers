from django.urls import include, path
from rest_framework import routers

from documentmanager.views_export.generic_export_view import GenericExportView

from .views.order_observation_view import OrderObservationViewSet
from .views.order_status_view import OrderStatusViewSet
from .views.order_priority_view import OrderPriorityViewSet 
from .views.order_type_view import OrderTypeViewSet
from .views.order_reason_view import OrderReasonViewSet
from .views.order_report_view import OrderReportViewSet
from .views.order_report_document_view import OrderReportDocumentViewSet
from .views.order_view import OrderViewSet
from .views.operator_view import OperatorViewSet
from .views.order_complete_view import CompleteOrderView
from .views.order_complete_view import InvalidateOrderView
from .views.claim_request_order_view import ClaimRequestOrderView
from .views.order_pdf_view import OrderReportPDFDownloadViewSet




router = routers.DefaultRouter()

router.register(r'order-observation', OrderObservationViewSet)
router.register(r'order-status', OrderStatusViewSet)
router.register(r'order-type', OrderTypeViewSet)
router.register(r'order-reason', OrderReasonViewSet)
router.register(r'order-report', OrderReportViewSet)
router.register(r'order-report-document', OrderReportDocumentViewSet)
router.register(r'order', OrderViewSet)
router.register(r'operator', OperatorViewSet)
router.register(r'order-priority', OrderPriorityViewSet)
urlpatterns = [
    # Han d'anar abans d'`include(router.urls)`: el router registra `<recurs>/<pk>/`
    # amb un patró de pk genèric que, si es col·loca abans, capturaria "export" com a pk.
    path('order/export/', GenericExportView.as_view(entity='order'), name='order-export'),
    path('order-type/export/', GenericExportView.as_view(entity='order_type'), name='order-type-export'),
    path('', include(router.urls)),
    path('order/<int:order_id>/complete', CompleteOrderView.as_view(http_method_names=['put']), name='complete-order'),
    path('claim-request-order/<str:type_token>/', ClaimRequestOrderView.as_view(http_method_names=['post']), name='claim-request-order'),
    path('invalidate-order/<int:order_id>/', InvalidateOrderView.as_view(http_method_names=['put']), name='invalidate-order'),
    path('download-order/<int:id>/', OrderReportPDFDownloadViewSet.as_view(http_method_names=['get']), name='download-order-pdf'),
]