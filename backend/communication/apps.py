from django.apps import AppConfig


class CommunicationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'communication'
    def ready(self):
        import communication.signals
        from communication.utils.send_errors import patch_httperror_add_note

        # Perquè els errors de Microsoft Graph arribin amb el codi real a Python 3.10.
        patch_httperror_add_note()
