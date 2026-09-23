# attendance/eligibility.py
"""
Single source of truth for which students may appear in / be recorded by
attendance screens. Kept in its own module (no view or form imports) so
views.py and forms.py can both use it without a circular import.

"inactive" students stay eligible; graduated, dropped, expelled and
suspended students do not. Existing attendance rows are never deleted —
they are simply hidden from the live attendance screens.
"""
from students.models import Student

ATTENDANCE_EXCLUDED_STATUSES = ('graduated', 'dropped', 'expelled', 'suspended')


def attendance_eligible_students(queryset=None):
    """
    Returns only students who can take part in attendance.
    Pass an existing Student queryset to narrow it, or nothing to start
    from all students.
    """
    if queryset is None:
        queryset = Student.objects.all()
    return queryset.exclude(student_status__in=ATTENDANCE_EXCLUDED_STATUSES)


def is_attendance_eligible(student):
    """Single-student check, used by the scan and CSV import flows."""
    return student.student_status not in ATTENDANCE_EXCLUDED_STATUSES