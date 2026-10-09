from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import AnonymousUser
from .models import ReadingOperator

class ReadingOperatorAuthBackend(BaseBackend):
    """
    Custom authentication backend for ReadingOperator model
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        
        try:
            operator = ReadingOperator.objects.get(username=username, is_active=True)
            if operator.check_password(password):
                return operator
        except ReadingOperator.DoesNotExist:
            return None
        
        return None

    def get_user(self, user_id):
        try:
            return ReadingOperator.objects.get(pk=user_id, is_active=True)
        except ReadingOperator.DoesNotExist:
            return None 