from django.apps import AppConfig


class VerifactuConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'verifactu'
    def ready(self):
        import verifactu.signals

