from rest_framework.throttling import UserRateThrottle

# Límits dels correus que s'envien des de les vistes de factures i mandats SEPA: el correu
# surt de l'adreça de l'empresa, i sense límit seria un relé per a missatges arbitraris.
MAX_EMAIL_RECIPIENTS = 5
MAX_EMAIL_SUBJECT_LENGTH = 200
MAX_EMAIL_BODY_LENGTH = 5000


class InvoiceEmailThrottle(UserRateThrottle):
    """Límit d'enviaments de correu per usuari (el comptador és per procés, com els de l'OV)."""

    scope = 'invoice_email'
    rate = '60/hour'


def email_payload_error(emails, subject, body):
    """Missatge d'error si el destinatari, l'assumpte o el cos passen dels límits; si no, None."""
    if len(emails) > MAX_EMAIL_RECIPIENTS:
        return f"Es poden indicar com a màxim {MAX_EMAIL_RECIPIENTS} adreces."
    if subject is not None and len(str(subject)) > MAX_EMAIL_SUBJECT_LENGTH:
        return f"L'assumpte pot tenir com a màxim {MAX_EMAIL_SUBJECT_LENGTH} caràcters."
    if body is not None and len(str(body)) > MAX_EMAIL_BODY_LENGTH:
        return f"El missatge pot tenir com a màxim {MAX_EMAIL_BODY_LENGTH} caràcters."
    return None
