from rest_framework import mixins
from rest_framework.response import Response
from rest_framework import status
from django.http import JsonResponse
from .models import Token
import json


class LecturappAuthMixin:
    """
    Mixin to handle lecturapp authentication for ViewSets
    """
    
    def dispatch(self, request, *args, **kwargs):
        """Override dispatch to add authentication"""
        # Authenticate the user using token
        token = None
        
        if request.method == 'POST':
            try:
                data = json.loads(request.body)
                token = data.get('token')
            except (json.JSONDecodeError, AttributeError):
                pass
        
        # Check for token in headers
        if not token:
            token = request.headers.get('X-App-Token')
        
        # Authenticate the user using token
        if token:
            operator = Token.get_operator_from_token(token)
            if operator and operator.is_active:
                # Add the authenticated operator to the request
                request.lecturapp_operator = operator
                return super().dispatch(request, *args, **kwargs)
        
        # Authentication failed
        return JsonResponse({
            'error': 'Authentication required',
            'message': 'Valid authentication token is required'
        }, status=401) 