from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "integrations"

    def ready(self):
        # Avisos de sortida que depenen de senyals (vegeu outbound/webhooks/signals.py)
        import integrations.outbound.webhooks.signals  # noqa: F401
