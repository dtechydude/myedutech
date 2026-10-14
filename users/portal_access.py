"""
Portal-access status for the "All Registered Users" page and its CSV export.

Django's `is_active` alone is misleading in this portal: a suspended, dropped,
expelled, inactive or graduated student (or a parent with no active children)
still has `is_active=True`, yet cannot log in. This module works out what each
account can REALLY do, using the same rules as the portal login blocking:

  * account switched off in the admin ........ Account disabled
  * superuser / staff (is_staff) / teacher ... allowed
  * student .................................. allowed only when student_status == 'active'
  * parent ................................... allowed only while at least one child is active

It is query-efficient: one extra query in total, no matter how many users.
"""
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Count

# reverse one-to-one relations from User that the listing needs
_ROLE_RELATIONS = ('profile', 'student', 'teacher', 'staff', 'parent')

_TONES = {                       # tone -> (text class, dot class)
    'success': ('text-success', 'bg-success'),
    'danger': ('text-danger', 'bg-danger'),
    'warning': ('text-warning', 'bg-warning'),
    'muted': ('text-muted', 'bg-secondary'),
}

# Student.student_status -> tone for a student who is blocked
_STUDENT_TONE = {'inactive': 'warning', 'graduated': 'muted'}   # anything else (suspended, dropped, expelled) -> danger


def _status(code, label, tone, can_login, reason=''):
    text_class, dot_class = _TONES[tone]
    return {'code': code, 'label': label, 'text_class': text_class, 'dot_class': dot_class,
            'can_login': can_login, 'reason': reason}


def portal_access(user, active_children=None):
    """
    What can this user really do in the portal? Returns a dict:
    code, label, text_class, dot_class, can_login, reason.
    `active_children` maps Parent pk -> number of ACTIVE children.
    """
    active_children = active_children or {}

    if not user.is_active:
        return _status('disabled', 'Account disabled', 'muted', False,
                       'Switched off in the admin panel (Active is unticked).')
    if user.is_superuser:
        return _status('superuser', 'Superuser', 'success', True)
    if user.is_staff:
        return _status('admin', 'Admin (Staff)', 'success', True)
    if getattr(user, 'teacher', None) is not None:
        return _status('teacher', 'Teacher', 'success', True)

    student = getattr(user, 'student', None)
    if student is not None:
        if student.student_status == 'active':
            return _status('student', 'Active (Student)', 'success', True)
        label = student.get_student_status_display()
        reason = ('Graduated students no longer have portal access.' if student.student_status == 'graduated'
                  else 'Cannot log in until the status is set back to Active.')
        return _status('student_blocked', f'Blocked \u2014 {label}',
                       _STUDENT_TONE.get(student.student_status, 'danger'), False, reason)

    parent = getattr(user, 'parent', None)
    if parent is not None:
        count = active_children.get(parent.pk, 0)
        if count:
            return _status('parent', 'Active (Parent)', 'success', True,
                           f'{count} active child{"ren" if count != 1 else ""}.')
        return _status('parent_blocked', 'Blocked \u2014 no active children', 'danger', False,
                       "A parent's login is blocked while none of their children is active.")

    if getattr(user, 'staff', None) is not None:
        return _status('staff', 'Staff', 'success', True)
    return _status('active', 'Active', 'success', True)


def active_children_by_parent():
    """{parent pk: number of active children} in ONE query."""
    Student = apps.get_model('students', 'Student')
    manager = Student.objects
    active = manager.enrolled() if hasattr(manager, 'enrolled') else manager.filter(student_status='active')
    rows = active.exclude(parent__isnull=True).values('parent').annotate(n=Count('pk'))
    return {row['parent']: row['n'] for row in rows}


def attach_portal_status(users):
    """Give every user a `.portal_status` dict (see portal_access) for the template/CSV."""
    counts = active_children_by_parent()
    for user in users:
        user.portal_status = portal_access(user, counts)
    return users


def role_relations(user_model=None):
    """Only the reverse relations that really exist on this project's User (safe for select_related)."""
    user_model = user_model or get_user_model()
    names = []
    for name in _ROLE_RELATIONS:
        try:
            field = user_model._meta.get_field(name)
        except FieldDoesNotExist:
            continue
        if field.one_to_one and field.auto_created and not field.concrete:
            names.append(name)
    return names


def users_for_listing():
    """All users with their profile/role records loaded in a single query (no N+1)."""
    User = get_user_model()
    return User.objects.select_related(*role_relations(User)).order_by('last_name', 'first_name')