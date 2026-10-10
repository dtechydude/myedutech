from django import template

from ..services import resource_info

register = template.Library()


@register.simple_tag
def resource_link_info(url):
    """{% resource_link_info some_url as res %} -> dict or None."""
    return resource_info(url)