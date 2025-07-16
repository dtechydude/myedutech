from django import template
from datetime import timedelta, date

register = template.Library()

@register.filter
def timesince_range(start_date, end_date):
    """
    Generates a list of dates between start_date and end_date (inclusive).
    Usage: {% for d in start_date|timesince_range:end_date %}
    """
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        return []

    delta = end_date - start_date
    dates = []
    for i in range(delta.days + 1):
        dates.append(start_date + timedelta(days=i))
    return dates