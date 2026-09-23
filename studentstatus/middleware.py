"""
Ends the session of any student whose status blocks portal access.

Runs on every request, so it also covers students who were ALREADY logged in
when an admin suspended / dropped / expelled / deactivated them, and any
status change made outside the front end (Django admin, batch graduation).
"""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.http import JsonResponse
from django.shortcuts import redirect, resolve_url

from .constants import block_message
from .services import get_login_block_status


class StudentStatusAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        status = get_login_block_status(user) if user is not None else None

        if status:
            message = block_message(status)
            logout(request)

            wants_json = (
                request.headers.get('x-requested-with') == 'XMLHttpRequest'
                or 'application/json' in request.headers.get('accept', '')
            )
            if wants_json:
                return JsonResponse({'status': 'error', 'message': message}, status=403)

            # Added AFTER logout() so the message survives the session flush.
            messages.error(request, message, fail_silently=True)
            return redirect(resolve_url(settings.LOGIN_URL))

        return self.get_response(request)