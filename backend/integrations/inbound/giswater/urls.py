from django.urls import path

from .views import GiswaterContractReadingsView, GiswaterContractsView

urlpatterns = [
    path("contracts/", GiswaterContractsView.as_view(), name="giswater-inbound-contracts"),
    path(
        "contracts/<str:contract_token>/readings/",
        GiswaterContractReadingsView.as_view(),
        name="giswater-inbound-contract-readings",
    ),
]
