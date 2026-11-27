from django.apps import apps
from rest_framework.permissions import BasePermission


def _all_ov_log_models():
    """Models que alimenten la pantalla de registres de l'OV: els registres del logger, els del
    contracte i les lectures (que l'OV marca amb origin='OV')."""
    logger_models = [m for m in apps.get_app_config('logger').get_models() if m.__name__.startswith('Log')]
    return logger_models + [
        apps.get_model('contract', 'ContractLog'),
        apps.get_model('contract', 'ContractObservation'),
        apps.get_model('contract', 'ContractDataChange'),
        apps.get_model('billing', 'Reading'),
    ]


def ov_log_models(user):
    """Només els models dels quals l'usuari té el permís de veure, igual que a la resta de
    registres: qui veu contractes veu els registres de contracte, i no els de factures."""
    return [
        model for model in _all_ov_log_models()
        if user.has_perm(f'{model._meta.app_label}.view_{model._meta.model_name}')
    ]


class CanViewSomeOVLog(BasePermission):
    """Autenticat i amb permís de veure almenys un dels models de registres de l'OV."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and ov_log_models(user))
