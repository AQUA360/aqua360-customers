from django.urls import include, path
from rest_framework import routers

from documentmanager.views_export.generic_export_view import GenericExportView

from verifactu.views import VerifactuNotificationViewSet, VerifactuBatchViewSet

router = routers.DefaultRouter()
router.register(r'notification', VerifactuNotificationViewSet)
router.register(r'batch', VerifactuBatchViewSet)

urlpatterns = [
    path('invoice/export/', GenericExportView.as_view(entity='verifactu_invoice'), name='verifactu-invoice-export'),
    path('', include(router.urls)),
]

