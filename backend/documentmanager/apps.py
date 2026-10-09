from django.apps import AppConfig


class DocumentmanagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'documentmanager'

    def ready(self):
        from . import signals  # noqa: F401
