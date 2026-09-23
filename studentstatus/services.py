"""
Business logic for student status management.

Views and forms never write Student.student_status directly — they call
change_student_status(), which validates, saves and audit-logs in one
transaction.

Login blocking is derived from Student.student_status at request time (see
middleware.py and backends.py). Nothing is copied onto the User account, so
there is no second flag to fall out of sync: change the status back to
"active" — from anywhere, including Django admin — and access returns.
"""
from django.core.exceptions import PermissionDenied
from django.db import transaction

from students.models import Student

from .constants import (
    ACTIVE, ASSIGNABLE_STATUSES, LOGIN_BLOCKED_STATUSES, PROTECTED_STATUSES,
    STATUS_LABELS,
)
from .models import StudentStatusLog
from .permissions import is_status_admin


class StatusChangeError(Exception):
    """A status change was refused for a business-rule reason (safe to show to the admin)."""


def _label(status):
    return STATUS_LABELS.get(status, status)


def change_student_status(*, student_id, new_status, changed_by, reason='', ip_address=None):
    """
    Change a student's status and record it in the audit log.

    Raises PermissionDenied if `changed_by` is not an administrator, and
    StatusChangeError for invalid or disallowed changes.
    """
    if not is_status_admin(changed_by):
        raise PermissionDenied("Only administrators can change a student's status.")

    if new_status not in ASSIGNABLE_STATUSES:
        raise StatusChangeError("That status cannot be set from this page.")

    reason = (reason or '').strip()
    if new_status != ACTIVE and not reason:
        raise StatusChangeError("A reason is required when restricting a student's access.")

    with transaction.atomic():
        try:
            # Row lock so two admins cannot race on the same student.
            student = Student.objects.select_for_update().get(pk=student_id)
        except Student.DoesNotExist:
            raise StatusChangeError("Student not found.")

        old_status = student.student_status

        if old_status in PROTECTED_STATUSES:
            raise StatusChangeError(
                f"{student.get_full_name()} is {_label(old_status).lower()}. "
                "Graduation is managed in the graduation module, not here."
            )
        if old_status == new_status:
            raise StatusChangeError(
                f"{student.get_full_name()} is already {_label(new_status).lower()}."
            )

        # update_fields keeps this a one-column write and still fires post_save
        # signals other modules may rely on.
        student.student_status = new_status
        student.save(update_fields=['student_status'])

        log = StudentStatusLog.objects.create(
            student=student,
            student_name=student.get_full_name(),
            student_usn=student.USN,
            old_status=old_status,
            new_status=new_status,
            reason=reason,
            changed_by=changed_by,
            changed_by_name=changed_by.get_full_name() or changed_by.get_username(),
            ip_address=ip_address,
        )
    return log


# ---------------------------------------------------------------------------
# Login-block lookups (used by middleware.py and backends.py)
# ---------------------------------------------------------------------------

def get_login_block_status(user):
    """
    Returns the blocking status (e.g. 'suspended') if this logged-in user is a
    student who must not access the portal, otherwise None.
    Staff and superusers are never blocked, so an admin can't be locked out
    by a stray student record.
    """
    if not getattr(user, 'is_authenticated', False) or user.is_staff or user.is_superuser:
        return None
    status = (
        Student.objects.filter(user_id=user.pk)
        .values_list('student_status', flat=True)
        .first()
    )
    return status if status in LOGIN_BLOCKED_STATUSES else None


def get_login_block_status_for_username(username):
    """Same check, by username, for use before a login succeeds."""
    if not username:
        return None
    status = (
        Student.objects.filter(
            user__username__iexact=username,
            user__is_staff=False,
            user__is_superuser=False,
        )
        .values_list('student_status', flat=True)
        .first()
    )
    return status if status in LOGIN_BLOCKED_STATUSES else None