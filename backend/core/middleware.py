import threading

_thread_locals = threading.local()


def get_current_user():
    """Retrieve the current request user from thread-local storage.
    Used by Django signal handlers to identify who triggered a model change
    without needing access to the HTTP request context.
    """
    return getattr(_thread_locals, 'user', None)


class CurrentUserMiddleware:
    """
    Middleware that stores the authenticated user in thread-local storage.
    This allows Django ORM signals (pre_save, post_save) to access the
    current user for audit logging without being passed the request object.

    Must be placed AFTER AuthenticationMiddleware in MIDDLEWARE settings.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = getattr(request, 'user', None)
        response = self.get_response(request)
        # Clean up to prevent user bleed between requests in the same thread
        _thread_locals.user = None
        return response
