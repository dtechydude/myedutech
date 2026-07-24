# finance/permissions.py
"""
Centralized permission checks & decorators for the Finance app, so access
rules (who can record payments, approve expenses, view P&L, etc.) live in
one place instead of being re-implemented per view.

Wire these into your role/group setup. By default we key off Django's
built-in `is_staff` plus the model-level permissions created automatically
for every model in this app (e.g. `finance.add_payment`,
`finance.view_expense`, `finance.approve_expense` — the last one is a
custom permission declared below).
"""
from functools import wraps

from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages


def is_finance_staff(user):
    """Staff who can record payments/invoices/expenses (bursary/accounts office)."""
    return user.is_authenticated and (user.is_superuser or user.is_staff)


def is_finance_admin(user):
    """Elevated role that can approve expenses and view Profit & Loss."""
    return user.is_authenticated and (
        user.is_superuser or user.has_perm('finance.view_profit_loss')
    )


def is_parent(user):
    return user.is_authenticated and hasattr(user, 'parent')


def is_student_user(user):
    return user.is_authenticated and hasattr(user, 'student')


def finance_staff_required(view_func):
    """Decorator: only finance/bursary staff may access this view."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_finance_staff(request.user):
            messages.error(request, "You do not have permission to access the Finance module.")
            return redirect('pages:portal-home')
        return view_func(request, *args, **kwargs)
    return _wrapped


def finance_admin_required(view_func):
    """Decorator: only elevated finance admins may access this view (e.g. P&L, expense approval)."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_finance_admin(request.user):
            messages.error(request, "You need Finance Admin access to view this page.")
            return redirect('finance:dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


class CustomPermissions:
    """
    Custom, non-CRUD permissions referenced by the Meta.permissions of
    models in this app (see models.Meta additions if you extend them) and
    usable directly with @permission_required('finance.<codename>').
    """
    APPROVE_EXPENSE = 'finance.approve_expense'
    VIEW_PROFIT_LOSS = 'finance.view_profit_loss'
    GENERATE_INVOICES = 'finance.generate_invoices'
    EXPORT_FINANCIAL_REPORTS = 'finance.export_financial_reports'
