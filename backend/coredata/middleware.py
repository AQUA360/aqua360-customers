from django.db import connection


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
        
        response = self.get_response(request)
        
        # Optionally clear the config after request (though it's session-scoped)
        # This is optional since PostgreSQL session variables are automatically cleared
        # when the connection is closed
        
        return response

