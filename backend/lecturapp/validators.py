from django.contrib.auth.models import User
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from auth.validators import validate_user_password


def validate_operator_password(password, operator=None, username=None, name=None, surname=None):
    """
    Valida la contrasenya d'un operari de l'app (ReadingOperator) amb les mateixes regles que els
    usuaris de l'API: validadors de Django, mínim 8 caràcters i almenys un número.
    Els valors que no es passen es prenen de l'operari (si n'hi ha), perquè el validador de
    similitud compari la contrasenya amb les dades finals. Llança el ValidationError de Django.
    """
    def value(given, attr):
        if given is not None:
            return given
        return getattr(operator, attr, '') or ''

    # Usuari sense desar, només perquè els validadors de Django en llegeixin els atributs
    user = User(
        username=value(username, 'username'),
        first_name=value(name, 'name'),
        last_name=value(surname, 'surname'),
    )
    validate_user_password(password, user, is_superuser=False)


def check_operator_password(password, field='password', **kwargs):
    """Com validate_operator_password, però retorna l'error al camp `field` com a error de DRF."""
    try:
        validate_operator_password(password, **kwargs)
    except DjangoValidationError as error:
        raise serializers.ValidationError({field: list(error.messages)})
