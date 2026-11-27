from django.db import DatabaseError, connection


class SetPostgresUserMiddleware:
    """
    Middleware to set PostgreSQL session variable with current user ID.
    Useful for:
    - PostgreSQL Row-Level Security (RLS) policies
    - Database-level audit triggers
    - Tracking user context in database functions
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set the user ID BEFORE processing the request
        if hasattr(request, 'user') and request.user is not None and request.user.is_authenticated:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('myapp.user_id', %s, false)",
                    [str(request.user.id)]
                )
        else:
            # Clear the config for unauthenticated users
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('myapp.user_id', '', false)"
                )
        
        try:
            return self.get_response(request)
        finally:
            # La variable és de sessió (els triggers d'auditoria la llegeixen a cada sentència,
            # i fora d'una transacció una variable local desapareixeria): s'esborra en acabar,
            # també si la vista falla, perquè una connexió reutilitzada no arrossegui l'usuari
            # d'aquesta petició a la següent.
            self._clear_user()

    @staticmethod
    def _clear_user():
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('myapp.user_id', '', false)")
        except DatabaseError:
            # Connexió trencada o transacció avortada: el servidor la descarta igualment
            pass

