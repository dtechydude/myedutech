# finance/templatetags/finance_extras.py
from decimal import Decimal, InvalidOperation

from django import template
from django.conf import settings

register = template.Library()

CURRENCY_SYMBOL = getattr(settings, 'FINANCE_CURRENCY_SYMBOL', '₦')


@register.filter
def currency(value):
    """Formats a number as currency, e.g. 125000.5 -> '₦125,000.50'."""
    try:
        value = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    formatted = f"{value:,.2f}"
    return f"{CURRENCY_SYMBOL}{formatted}"


@register.filter
def sum_field(queryset, field_name):
    """Sums an arbitrary field/attribute across an iterable of objects or dicts."""
    total = Decimal('0.00')
    for item in queryset:
        value = item.get(field_name) if isinstance(item, dict) else getattr(item, field_name, None)
        if value is not None:
            total += Decimal(value)
    return total


@register.filter
def status_badge_class(status):
    """Maps a status string to a Bootstrap badge color class."""
    mapping = {
        'paid': 'bg-success', 'completed': 'bg-success', 'approved': 'bg-success', 'processed': 'bg-success',
        'partial': 'bg-warning text-dark', 'pending': 'bg-warning text-dark',
        'overdue': 'bg-danger', 'failed': 'bg-danger', 'rejected': 'bg-danger', 'cancelled': 'bg-secondary',
        'issued': 'bg-primary', 'draft': 'bg-secondary', 'refunded': 'bg-info text-dark',
    }
    return mapping.get(str(status).lower(), 'bg-secondary')


@register.filter
def get_item(dictionary, key):
    """Allows `{{ mydict|get_item:some_var }}` lookups in templates."""
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def percentage(value, total):
    try:
        value = Decimal(value)
        total = Decimal(total)
        if total == 0:
            return "0.0"
        return f"{(value / total * 100):.1f}"
    except (InvalidOperation, TypeError, ValueError, ZeroDivisionError):
        return "0.0"


@register.simple_tag
def multiply(a, b):
    try:
        return Decimal(a) * Decimal(b)
    except (InvalidOperation, TypeError, ValueError):
        return 0
