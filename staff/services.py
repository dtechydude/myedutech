# apps/staff/services.py

from django.utils import timezone

from .models import StaffAttendance


def mark_teacher_check_in(teacher, user=None):

    today = timezone.localdate()
    current_time = timezone.localtime().time()

    attendance, created = StaffAttendance.objects.get_or_create(
        teacher=teacher,
        date=today,
        defaults={
            'check_in_time': current_time,
            'status': 'present',
            'marked_by': user
        }
    )

    if not created and not attendance.check_in_time:
        attendance.check_in_time = current_time

    # Example late logic (after 8:00 AM)
    late_threshold = timezone.datetime.strptime(
        "08:00",
        "%H:%M"
    ).time()

    if current_time > late_threshold:
        attendance.is_late = True
        attendance.status = 'late'

    attendance.save()

    return attendance


def mark_teacher_check_out(teacher):

    today = timezone.localdate()

    attendance = StaffAttendance.objects.filter(
        teacher=teacher,
        date=today
    ).first()

    if attendance:
        attendance.check_out_time = timezone.localtime().time()
        attendance.save()

    return attendance