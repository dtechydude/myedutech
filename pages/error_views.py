
from django.shortcuts import render


def bad_request(request, exception=None):
    """Handle HTTP 400 errors."""
    return render(
        request,
        "errors/400.html",
        status=400,
    )


def permission_denied(request, exception=None):
    """Handle HTTP 403 errors."""
    return render(
        request,
        "errors/403.html",
        status=403,
    )


def page_not_found(request, exception=None):
    """Handle HTTP 404 errors."""
    return render(
        request,
        "errors/404.html",
        status=404,
    )


def server_error(request):
    """Handle HTTP 500 errors."""
    return render(
        request,
        "errors/500.html",
        status=500,
    )


def csrf_failure(request, reason=""):
    """
    Provide a friendly page when Django rejects a CSRF request.
    Do not expose the internal failure reason to the user.
    """
    return render(
        request,
        "errors/403.html",
        {
            "csrf_error": True,
        },
        status=403,
    )
