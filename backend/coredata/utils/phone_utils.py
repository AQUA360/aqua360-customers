import re

# Pla de numeració espanyol: els mòbils són 6xx xxx xxx i 71x-74x xxx xxx; els
# fixos comencen per 8 o 9. La resta (70x numeració personal, 80x/90x tarifació
# especial...) no rep SMS.
SPANISH_MOBILE_RE = re.compile(r'^(6\d{8}|7[1-4]\d{7})$')
SPANISH_PREFIX = '34'


def normalize_phone(phone):
    """Deixa el telèfon només amb dígits i el prefix internacional amb '+'.

    Treu espais, guions, punts i parèntesis, i converteix el prefix '00' en '+'.
    Retorna '' si no queda cap dígit.
    """
    if not phone:
        return ''
    # Sense separadors ni parèntesis, perquè '(+34) 612...' també porti prefix.
    value = re.sub(r'[^\d+]', '', str(phone))
    international = value.startswith('+') or value.startswith('00')
    digits = re.sub(r'\D', '', value)
    if value.startswith('00'):
        digits = digits[2:]
    if not digits:
        return ''
    return f'+{digits}' if international else digits


def is_mobile_phone(phone):
    """Indica si el telèfon pot rebre SMS.

    Els números espanyols (sense prefix o amb +34/0034) han de ser mòbils. Dels
    estrangers no es pot saber si són fixos, i es donen per bons si tenen una
    llargada vàlida (E.164: de 8 a 15 dígits).
    """
    normalized = normalize_phone(phone)
    if not normalized:
        return False
    if normalized.startswith('+'):
        digits = normalized[1:]
        if not digits.startswith(SPANISH_PREFIX):
            return 8 <= len(digits) <= 15
        normalized = digits[len(SPANISH_PREFIX):]
    return bool(SPANISH_MOBILE_RE.match(normalized))


def to_broadcaster_format(phone):
    """Mòbil amb el prefix de país i sense '+' (34600000000), com l'espera Broadcaster.

    Sense prefix, el número es considera espanyol. Retorna '' si no pot rebre SMS.
    """
    if not is_mobile_phone(phone):
        return ''
    normalized = normalize_phone(phone)
    if normalized.startswith('+'):
        return normalized[1:]
    return f'{SPANISH_PREFIX}{normalized}'


def non_mobile_sms_phones(contact_ids, current_ids=()):
    """Telèfons que es volen afegir com a SMS i no són mòbils.

    Només es miren els contactes nous (no inclosos a `current_ids`): així un
    contracte amb un fix ja vinculat d'abans es pot continuar desant.
    """
    from coredata.models import PersonContact

    new_ids = set(contact_ids or []) - set(current_ids or [])
    if not new_ids:
        return []
    return [
        contact.phone or ''
        for contact in PersonContact.objects.filter(id__in=new_ids)
        if not is_mobile_phone(contact.phone)
    ]
