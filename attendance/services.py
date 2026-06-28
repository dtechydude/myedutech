from attendance.models import (
    Attendance,
    AttendanceSummary,
    AttendanceConfiguration
)


def get_student_attendance(
    student,
    session,
    term
):
    """
    Returns attendance data.

    Priority:
    Manual Attendance Summary
    Daily Attendance Records
    """

    manual = AttendanceSummary.objects.filter(
        student=student,
        session=session,
        term=term
    ).first()

    if manual:

        return {
            'days_present': manual.days_present,
            'days_absent': manual.days_absent,
            'total_days': manual.total_school_days,
            'attendance_percentage':
                manual.attendance_percentage,
            'source': 'manual'
        }

    records = Attendance.objects.filter(
        student=student,
        date__gte=term.start_date,
        date__lte=term.end_date
    )

    days_present = records.filter(
        present=True
    ).count()

    days_absent = records.filter(
        present=False
    ).count()

    total_days = (
        days_present +
        days_absent
    )

    percentage = 0

    if total_days > 0:

        percentage = round(
            (
                days_present /
                total_days
            ) * 100,
            2
        )

    return {
        'days_present': days_present,
        'days_absent': days_absent,
        'total_days': total_days,
        'attendance_percentage': percentage,
        'source': 'daily'
    }


# helper function
def attendance_context(
    student,
    session,
    term
):

    attendance = get_student_attendance(
        student,
        session,
        term
    )

    return {

        'days_present':
            attendance['days_present'],

        'days_absent':
            attendance['days_absent'],

        'total_days':
            attendance['total_days'],

        'percent_present':
            attendance['attendance_percentage'],

        'attendance_source':
            attendance['source'],
    }