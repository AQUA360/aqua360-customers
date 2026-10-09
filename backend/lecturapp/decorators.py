from functools import wraps
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import ReadingOperator, Token
import json

def lecturapp_auth_required(view_func):
    """
    Custom decorator to authenticate ReadingOperator users using tokens
    """
    @csrf_exempt
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        print("CUSTOM AUTH")
        # Try to get request from args
        request = None
        
        # For ViewSet methods: (self, request, *args, **kwargs)
        if len(args) > 1 and hasattr(args[1], 'META'):
            request = args[1]
        # For function-based views: (request, *args, **kwargs)
        elif len(args) > 0 and hasattr(args[0], 'META'):
            request = args[0]
        else:
            raise Exception("Could not find request object in arguments")
        
        token = None
        
        # Only try to parse JSON if content-type is JSON (not multipart/form-data)
        if request.method == 'POST' and request.content_type and 'application/json' in request.content_type:
            try:
                data = json.loads(request.body)
                token = data.get('token')
            except (json.JSONDecodeError, AttributeError):
                pass
        
        # Check for token in headers
        if not token:
            token = request.headers.get('X-App-Token')
        
        print(f"Token: {token}")
        
        # Authenticate the user using token
        if token:
            operator = Token.get_operator_from_token(token)
            if operator and operator.is_active:
                # Add the authenticated operator to the request
                request.lecturapp_operator = operator
                return view_func(*args, **kwargs)
        
        # Authentication failed
        return JsonResponse({
            'error': 'Authentication required',
            'message': 'Valid authentication token is required'
        }, status=401)
    
    return wrapper

def get_authenticated_operator(request):
    """
    Helper function to get the authenticated operator from request
    """
    return getattr(request, 'lecturapp_operator', None) 