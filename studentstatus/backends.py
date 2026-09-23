"""
Login guard: stops blocked students from signing in at all.

This is NOT a full authentication backend — it never authenticates anyone.
It only vetoes: if the username belongs to a student whose status blocks
access, it raises PermissionDenied, which makes Django stop trying other
backends and reject the login. For everyone else it returns None so the
normal backend (ModelBackend) carries on as usual.

It intentionally has no get_user(): Django's test client and login() pick
the first backend that defines get_user() to store in the session, and that
must stay ModelBackend.
"""
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from .constants import block_message
from .services import get_login_block_status_for_username


class StudentStatusGuardBackend:
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)

        status = get_login_block_status_for_username(username)
        if status:
            if request is not None:
                messages.error(request, block_message(status), fail_silently=True)
            raise PermissionDenied
        return None