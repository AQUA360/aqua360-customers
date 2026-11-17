from django.urls import path

from .views import GMAOLoginView, GMAOPropertySearchView

urlpatterns = [
    path("auth/login/", GMAOLoginView.as_view(), name="gmao-inbound-login"),
    path(
        "properties/",
        GMAOPropertySearchView.as_view(),
        name="gmao-inbound-properties",
    ),
]
