from coredata.models import ConfigProject

DOCUMENT_SIGN_ENABLED_TOKEN = 'DOCUMENT_SIGN_ENABLED'

# Prefix per a l'`external_reference` de les sessions de signatura de `DocumentSign`,
# per evitar col·lisions amb l'id numèric d'altres entitats (p. ex. ContractRequest)
# que també poden usar el mateix id com a referència.
DOCUMENT_SIGN_REFERENCE_PREFIX = 'docsign-'


def is_document_sign_enabled():
    """
    Retorna si la funcionalitat de signatura de documents (OTP) està habilitada,
    segons el valor del ConfigProject amb token `DOCUMENT_SIGN_ENABLED`.
    """
    config = ConfigProject.objects.filter(token=DOCUMENT_SIGN_ENABLED_TOKEN).first()
    if not config or not config.value:
        return False
    return config.value.lower() == 'true'
