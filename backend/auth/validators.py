from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext


MIN_LENGTH = 8


def _has_special(password):
    return any(not c.isalnum() and not c.isspace() for c in password)


def validate_user_password(password, user, is_superuser):
    """
    Validadors de Django (AUTH_PASSWORD_VALIDATORS) i, a més:
    - tothom: mínim 8 caràcters i almenys un número;
    - superusuaris: també almenys una lletra i un caràcter especial (ni lletra, ni número, ni espai).
    """
    errors = []
    try:
        validate_password(password, user)
    except ValidationError as error:
        errors.extend(error.error_list)

    extra = [
        (len(password) >= MIN_LENGTH, 'password_too_short',
         gettext("The password must have at least %(min_length)d characters.") % {'min_length': MIN_LENGTH}),
        (any(c.isdigit() for c in password), 'password_no_number',
         gettext("The password must contain at least one number.")),
    ]
    if is_superuser:
        extra += [
            (any(c.isalpha() for c in password), 'password_no_letter',
             gettext("The password must contain at least one letter.")),
            (_has_special(password), 'password_no_special',
             gettext("The password must contain at least one special character.")),
        ]
    # No repetim l'error de longitud si Django ja l'ha donat
    codes = {e.code for e in errors}
    errors.extend(ValidationError(message, code=code) for ok, code, message in extra if not ok and code not in codes)
    if errors:
        raise ValidationError(errors)
