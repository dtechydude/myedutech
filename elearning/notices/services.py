"""
In-app notification service shared by the elearning and lesson-note features.

`notify()` is the ONLY place notifications are created. If the school later
adds SMS/email/push, or a project-wide notification module, change it here.
"""
import logging

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Notification

logger = logging.getLogger(__name__)

TITLE_MAX, MESSAGE_MAX, URL_MAX = 120, 255, 300


def safe_url(url):
    """Only internal paths are allowed — blocks external sites and javascript: links."""
    url = (url or '').strip()
    if url.startswith('/') and not url.startswith('//') and '\\' not in url:
        return url[:URL_MAX]
    return ''


def notify(recipients, category, title, message='', url='', dedupe_key=''):
    """
    Create one notification per distinct, active recipient. Returns how many
    were created. It never raises: a notification problem must not break the
    action (publishing a lesson, approving a note) that triggered it.
    """
    try:
        users = {u.pk for u in recipients if u is not None and u.is_active}
        if dedupe_key and users:
            already = Notification.objects.filter(
                recipient_id__in=users, dedupe_key=dedupe_key).values_list('recipient_id', flat=True)
            users -= set(already)
        if not users:
            return 0
        rows = [Notification(recipient_id=pk, category=category, title=(title or '')[:TITLE_MAX],
                             message=(message or '')[:MESSAGE_MAX], url=safe_url(url),
                             dedupe_key=dedupe_key[:100]) for pk in users]
        with transaction.atomic():  # savepoint: a DB error cannot poison the caller's transaction
            Notification.objects.bulk_create(rows)
        return len(rows)
    except Exception:  # noqa: BLE001
        logger.exception('Could not create notifications')
        return 0


# ------------------------------------------------------------ who to notify
def students_of_class(standard):
    """Users of ENROLLED (active) students in a class — the same people who can log in."""
    Student = apps.get_model('students', 'Student')
    manager = Student.objects
    students = manager.enrolled() if hasattr(manager, 'enrolled') else manager.filter(student_status='active')
    return get_user_model().objects.filter(
        is_active=True, student__in=students.filter(current_class=standard))


def reviewers(exclude=None):
    """School management (staff / superusers)."""
    users = get_user_model().objects.filter(is_active=True).filter(Q(is_staff=True) | Q(is_superuser=True))
    return users.exclude(pk=exclude.pk) if exclude is not None else users


# ------------------------------------------------------------ reading/updating
def unread_count(user):
    return Notification.objects.filter(recipient=user, is_read=False).count()


def recent(user, limit=5):
    return list(Notification.objects.filter(recipient=user)[:limit])


def mark_all_read(user):
    return Notification.objects.filter(recipient=user, is_read=False).update(
        is_read=True, read_at=timezone.now())