from django.utils.http import content_disposition_header


def attachment_disposition(filename, default='document'):
    """Capçalera Content-Disposition d'un adjunt amb el nom net: sense cometes ni salts de
    línia injectats i amb la codificació correcta dels noms amb accents."""
    return content_disposition_header(True, (filename or default).replace('\r', '').replace('\n', ''))
