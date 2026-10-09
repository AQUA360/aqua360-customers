# Aquest middleware no està registrat a MIDDLEWARE: es reutilitza el
# thread-local de contract.middleware perquè els signals de service
# obtinguin l'usuari de la petició
from contract.middleware import get_current_user, set_current_user, UserMiddleware  # noqa: F401
