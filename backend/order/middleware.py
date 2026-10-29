# Aquest middleware no està registrat a MIDDLEWARE: es reutilitza el
# thread-local de contract.middleware perquè tot el codi llegeixi el mateix
# usuari (el de la petició o el de qui ha encuat la tasca de Celery)
from contract.middleware import get_current_user, set_current_user, UserMiddleware  # noqa: F401
