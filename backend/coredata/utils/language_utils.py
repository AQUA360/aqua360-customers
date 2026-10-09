from functools import wraps

from django.conf import settings
from django.utils import translation


def use_default_language(func):
    """
    Executa la funció amb l'idioma configurat al .env (settings.LANGUAGE_CODE),
    ignorant l'idioma de la petició. Pensat per a informes i exportacions
    (Excel/CSV), perquè surtin sempre en el mateix idioma que els generats
    en tasques de Celery.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with translation.override(settings.LANGUAGE_CODE):
            return func(*args, **kwargs)
    return wrapper
