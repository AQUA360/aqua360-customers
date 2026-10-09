from django.apps import AppConfig


class ClaimrequestConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'claimrequest'

    def ready(self):
        import claimrequest.signals
