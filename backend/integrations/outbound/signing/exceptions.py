class SigningApiError(Exception):
    pass


# Text que es desa a DocumentSign.error_report (i que veu l'usuari) quan falla el
# servei: el detall porta la resposta crua d'Aqua360 Sign i queda al log i al
# registre d'integracions.
SIGNING_SERVICE_ERROR = "Error de comunicació amb el servei de signatura."
