from django.urls import include, path
from rest_framework import routers

from integrations.views.send_batch_observation_view import SendBatchObservationViewSet
from integrations.views.send_batch_view import SendBatchViewSet

router = routers.DefaultRouter()
router.register(r"batch", SendBatchViewSet, basename="send-batch")
router.register(
    r"batch-observation",
    SendBatchObservationViewSet,
    basename="send-batch-observation",
)

urlpatterns = [
    path("", include(router.urls)),
]
