# attendance/templatetags/attendance_filters.py
from django import template
from datetime import date, timedelta

register = template.Library()

@register.filter
def timesince_range(start_date, end_date):
    """
    Generates a list of dates between start_date and end_date (inclusive).
    """
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        return [] # Return empty if inputs are not valid dates

    delta = end_date - start_date
    dates = []
    for i in range(delta.days + 1):
        dates.append(start_date + timedelta(days=i))
    return dates

@register.filter
def get_item(dictionary, key):
    """
    Allows dictionary lookups in Django templates using variable keys.
    Usage: {{ my_dict|get_item:my_key }}
    """
    if isinstance(dictionary, dict):
        # Handle accessing nested dictionary values
        if isinstance(key, str):
            # If the key is a string like 'student.present', split it
            parts = key.split('.')
            current_value = dictionary
            for part in parts:
                if isinstance(current_value, dict) and part in current_value:
                    current_value = current_value[part]
                elif hasattr(current_value, part): # Allow attribute access (e.g., student.id)
                    current_value = getattr(current_value, part)
                else:
                    return None # Or raise an error, depending on desired behavior
            return current_value
        else:
            return dictionary.get(key)
    elif hasattr(dictionary, '__iter__') and hasattr(dictionary, '__getitem__'):
        # For lists/tuples, try converting key to int
        try:
            return dictionary[int(key)]
        except (ValueError, IndexError):
            pass # Fall through if not a valid int or out of bounds
    return None