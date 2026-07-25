from attendance.models import (
    Attendance,
    AttendanceSummary,
    AttendanceConfiguration
)


# def get_student_attendance(
#     student,
#     session,
#     term
# ):
#     """
#     Returns attendance data.

#     Priority:
#     Manual Attendance Summary
#     Daily Attendance Records
#     """

#     manual = AttendanceSummary.objects.filter(
#         student=student,
#         session=session,
#         term=term
#     ).first()

#     if manual:

#         return {
#             'days_present': manual.days_present,
#             'days_absent': manual.days_absent,
#             'total_days': manual.total_school_days,
#             'attendance_percentage':
#                 manual.attendance_percentage,
#             'source': 'manual'
#         }

#     records = Attendance.objects.filter(
#         student=student,
#         date__gte=term.start_date,
#         date__lte=term.end_date
#     )

#     days_present = records.filter(
#         present=True
#     ).count()

#     days_absent = records.filter(
#         present=False
#     ).count()

#     total_days = (
#         days_present +
#         days_absent
#     )

#     percentage = 0

#     if total_days > 0:

#         percentage = round(
#             (
#                 days_present /
#                 total_days
#             ) * 100,
#             2
#         )

#     return {
#         'days_present': days_present,
#         'days_absent': days_absent,
#         'total_days': total_days,
#         'attendance_percentage': percentage,
#         'source': 'daily'
#     }


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



# Get Term Total
from curriculum.services import get_term_calendar_school_days


def get_term_total_school_days(term):
    """
    Uniform total school days for a term, independent of any one student.
    Priority: manual AttendanceConfiguration entry, else auto-calculated
    from the term's calendar minus weekends/public holidays. No longer
    falls back to counting attendance records taken — that produced a
    different (unfair) number depending on which teacher/class it was.
    """
    config = AttendanceConfiguration.objects.filter(
        session=term.session, term=term
    ).first()
    if config and config.total_school_days:
        return config.total_school_days
    return get_term_calendar_school_days(term)


def get_student_attendance(student, session, term):
    """
    Returns attendance data for one student, one term.

    total_school_days is ALWAYS the uniform figure from
    get_term_total_school_days() — manual per-student entry only ever
    supplies days_present; days_absent is always derived
    (total_school_days - days_present), never taken as independent raw
    input, so it can never drift out of sync with the configured total.

    has_data=False signals this term doesn't apply to the student at all
    (no override, no daily records) — e.g. they hadn't joined the school
    yet. Session-level aggregation uses this to skip the term entirely
    rather than unfairly counting it as fully absent.
    """
    total_school_days = get_term_total_school_days(term)

    manual = AttendanceSummary.objects.filter(
        student=student, session=session, term=term
    ).first()

    if manual:
        days_present = min(manual.days_present, total_school_days)
        days_absent = max(total_school_days - days_present, 0)
        return {
            'days_present': days_present,
            'days_absent': days_absent,
            'total_days': total_school_days,
            'attendance_percentage': round((days_present / total_school_days) * 100, 2) if total_school_days else 0,
            'source': 'manual',
            'has_data': True,
        }

    records = Attendance.objects.filter(
        student=student, date__gte=term.start_date, date__lte=term.end_date
    )
    if not records.exists():
        return {
            'days_present': 0, 'days_absent': 0, 'total_days': 0,
            'attendance_percentage': 0, 'source': 'none', 'has_data': False,
        }

    days_present = records.filter(present=True).count()
    days_absent = max(total_school_days - days_present, 0)

    return {
        'days_present': days_present,
        'days_absent': days_absent,
        'total_days': total_school_days,
        'attendance_percentage': round((days_present / total_school_days) * 100, 2) if total_school_days else 0,
        'source': 'daily',
        'has_data': True,
    }

# new services
def get_session_attendance(student, session):
    """
    Session-level aggregation. Only sums terms where has_data=True — a
    term the student wasn't enrolled for (e.g. joined in Term 2) is
    excluded entirely, from both the present-count and the total-days
    denominator. This is what makes it "fair": rather than dividing by a
    fixed 3 terms, the percentage is naturally weighted only by the days
    that actually applied to this student.
    """
    terms_in_session = session.terms.all().order_by('start_date')

    total_present = 0
    total_days = 0
    counted_terms = 0
    any_manual = False

    for term in terms_in_session:
        info = get_student_attendance(student, session, term)
        if not info['has_data']:
            continue
        total_present += info['days_present']
        total_days += info['total_days']
        counted_terms += 1
        if info['source'] == 'manual':
            any_manual = True

    total_absent = max(total_days - total_present, 0)
    percentage = round((total_present / total_days) * 100, 2) if total_days else 0

    return {
        'days_present': total_present,
        'days_absent': total_absent,
        'total_days': total_days,
        'attendance_percentage': percentage,
        'source': 'manual' if any_manual else 'daily',
        'terms_counted': counted_terms,
    }