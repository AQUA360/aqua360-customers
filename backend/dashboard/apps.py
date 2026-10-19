from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'

    def ready(self):
        """Import card modules to register the available dashboard cards."""
        # Registra les cards disponibles
        from . import cards  # noqa: F401
