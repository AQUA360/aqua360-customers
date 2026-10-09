from threading import local
from django.contrib.auth.models import AnonymousUser

_thread_locals = local()

def get_current_user():
    user = getattr(_thread_locals, 'user', None)
    return user

def set_current_user(user):
    _thread_locals.user = user

class UserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            set_current_user(user)
        else:
            set_current_user(None)
            
        response = self.get_response(request)
        set_current_user(None)
        return response 