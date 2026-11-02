from django.urls import path

from integrations.inbound.odoo.views import OdooBatchResultView

urlpatterns = [
    path(
        "batch-results/",
        OdooBatchResultView.as_view(),
        name="odoo-inbound-batch-results",
    ),
]
