from django.urls import include, path
from rest_framework import routers

from integrations.views.send_batch_catalog_view import (
    SendBatchProviderViewSet,
    SendBatchSettingsView,
    SendBatchStatusViewSet,
    SendBatchTypeViewSet,
)
from integrations.views.send_batch_observation_view import SendBatchObservationViewSet
from integrations.views.send_batch_view import SendBatchViewSet

router = routers.DefaultRouter()
router.register(r"batch", SendBatchViewSet, basename="send-batch")
router.register(
    r"batch-observation",
    SendBatchObservationViewSet,
    basename="send-batch-observation",
)
router.register(r"provider", SendBatchProviderViewSet, basename="send-batch-provider")
router.register(r"type", SendBatchTypeViewSet, basename="send-batch-type")
router.register(r"status", SendBatchStatusViewSet, basename="send-batch-status")

urlpatterns = [
    path("settings/", SendBatchSettingsView.as_view(), name="send-batch-settings"),
    path("", include(router.urls)),
]
