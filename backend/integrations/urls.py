from django.urls import path

from integrations.inbound.signing.views import SigningCallbackView

urlpatterns = [
    path("callback/", SigningCallbackView.as_view(), name="signing-callback"),
]
