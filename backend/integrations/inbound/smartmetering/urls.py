from django.urls import path

from .views import SmartMeteringContractsView

urlpatterns = [
    path("contracts/", SmartMeteringContractsView.as_view(), name="smartmetering-inbound-contracts"),
]
