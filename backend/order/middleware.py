import threading
import logging
from django.contrib.auth.models import AnonymousUser

_thread_locals = threading.local()

def get_current_user():
    user = getattr(_thread_locals, 'user', None)
    if isinstance(user, AnonymousUser):
        return None
    return user

class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # print("CurrentUserMiddleware: Processing request.")
        _thread_locals.user = request.user
        # print(f"Current user set to: {request.user} (Authenticated: {request.user.is_authenticated})")
        response = self.get_response(request)
        # print("CurrentUserMiddleware: Response generated.")
        return response
    