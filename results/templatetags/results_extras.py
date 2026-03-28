# schools/templatetags/schools_extras.py

from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Allows dictionary lookup by variable key in Django templates.
    Usage: {{ my_dict|get_item:my_key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None



@register.filter
def ordinal(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return value

    if 10 <= value % 100 <= 20:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(value % 10, 'th')

    return f"{value}{suffix}"
