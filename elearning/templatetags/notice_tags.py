import logging

from django import template

from ..notices import services

logger = logging.getLogger(__name__)
register = template.Library()


@register.inclusion_tag('elearning/notices/_bell.html', takes_context=True)
def notice_bell(context, limit=5, icon='fa-graduation-cap'):
    """
    Notification dropdown for the portal header. Renders an <li>, so place it
    inside the header's <ul class="navbar-nav header-right">:

        {% load notice_tags %}
        {% notice_bell %}                      {# or {% notice_bell icon="fa-bell" %} #}

    It sits in a page shared by every screen, so it fails safe: if anything goes
    wrong (e.g. migrations not applied yet) it renders nothing instead of breaking pages.
    """
    request = context.get('request')
    user = context.get('user') or getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'show': False}
    try:
        return {
            'show': True,
            'icon': icon,
            'unread': services.unread_count(user),
            'items': services.recent(user, limit),
            'next': request.get_full_path() if request else '',
            'csrf_token': context.get('csrf_token', ''),
        }
    except Exception:  # noqa: BLE001
        logger.exception('Notification bell could not be rendered')
        return {'show': False}