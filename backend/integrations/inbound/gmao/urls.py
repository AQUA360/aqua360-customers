from django.urls import path

from .views import GMAOPropertySearchView

urlpatterns = [
    path(
        "properties/",
        GMAOPropertySearchView.as_view(),
        name="gmao-inbound-properties",
    ),
]
