from django.urls import include, path
from rest_framework import routers

from .views.fraud_view import FraudViewSet
from .views.fraud_status_view import FraudStatusViewSet
from .views.fraud_report_view import FraudReportViewSet
from .views.fraud_documentation_view import FraudDocumentationViewSet
from .views.fraud_image_view import FraudImageViewSet
from .views.fraud_observation_view import FraudObservationViewSet
from .views.fraud_type_view import FraudTypeViewSet

router = routers.DefaultRouter()

router.register(r'fraud', FraudViewSet)
router.register(r'fraud-status', FraudStatusViewSet)
router.register(r'fraud-type', FraudTypeViewSet)
router.register(r'fraud-report', FraudReportViewSet)
router.register(r'fraud-documentation', FraudDocumentationViewSet)
router.register(r'fraud-image', FraudImageViewSet)
router.register(r'fraud-observation', FraudObservationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]