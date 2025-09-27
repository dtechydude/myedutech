from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def sum_balance(queryset):
    """
    Calculates the sum of the 'balance' field for all objects in a queryset.
    """
    total = Decimal('0.00')
    for item in queryset:
        # Use .get('balance') to safely access the annotated field,
        # or use item.balance for objects with the attribute.
        balance_value = getattr(item, 'balance', Decimal('0.00'))
        if balance_value is not None:
            total += balance_value
    return total