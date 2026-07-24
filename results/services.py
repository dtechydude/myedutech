from .models import SessionReportComments, Score, MotorAbilityScore
from curriculum.models import Standard, SchoolIdentity
from django.db.models import Sum, Avg, Q, Count # Import Q for complex queries if needed
from .utils import get_overall_remark, get_subject_remark, get_grade
from attendance.models import Attendance




def get_student_standard_for_session(student, terms_in_session):
    """
    Best-effort historical standard: the class the student was actually in
    during this session, derived from their Score records (snapshotted per
    term, same source as Student.get_class_history()). Falls back to the
    student's current class if no scores exist yet for this session.
    """
    from results.models import Score

    historical_standard_id = (
        Score.objects
        .filter(student=student, term__in=terms_in_session)
        .exclude(standard__isnull=True)
        .values_list('standard', flat=True)
        .first()
    )
    if historical_standard_id:
        return Standard.objects.filter(id=historical_standard_id).first()

    return student.current_class


def get_or_create_session_comment(student, session, standard=None, user=None):
    """
    Single source of truth for fetching/creating a student's session
    comment record. Looked up by (student, session) ONLY — standard is
    stored for reference and refreshed if stale, never part of the
    lookup key, so admin/report-card/bulk-page never create duplicates.
    """
    comment_obj, created = SessionReportComments.objects.get_or_create(
        student=student,
        session=session,
        defaults={'standard': standard, 'created_by': user}
    )
    if standard is not None and comment_obj.standard_id != standard.id:
        comment_obj.standard = standard
        comment_obj.save(update_fields=['standard'])
    return comment_obj


# Bulk Print Session Report Card
def build_session_report_context(student, session, user=None):
    """
    INDEPENDENT, read-only builder for a single student's session report
    data. Duplicates the computation in StudentSessionReportCardView.get()
    intentionally, rather than calling into it, so that view remains
    completely untouched. Used only by the bulk print/download feature.

    Returns None if the session has no terms defined (mirrors the existing
    view's early-exit behavior), so the caller can skip that student.
    """
    terms_in_session = session.terms.all().order_by('start_date')
    if not terms_in_session.exists():
        return None

    subject_cumulative_data = Score.objects.filter(
        student=student,
        term__in=terms_in_session
    ).values('subject__name', 'subject__id').annotate(
        cumulative_total_score=Sum('total_score'),
        active_term_count=Count('term', filter=Q(total_score__isnull=False))
    ).order_by('subject__name')

    report_data = []
    overall_effective_average_sum = 0
    subjects_counted_for_overall_average = 0

    for item in subject_cumulative_data:
        subject_id = item['subject__id']
        subject_name = item['subject__name']
        cumulative_score_raw = item['cumulative_total_score']
        active_term_count = item['active_term_count']

        term_scores_for_subject = {}
        for term in terms_in_session:
            try:
                score_inst = Score.objects.get(student=student, subject__id=subject_id, term=term)
                term_scores_for_subject[term.name] = score_inst.total_score if score_inst.total_score is not None else 'N/A'
            except Score.DoesNotExist:
                term_scores_for_subject[term.name] = 'N/A'

        effective_subject_average = None
        if cumulative_score_raw is not None and active_term_count > 0:
            effective_subject_average = cumulative_score_raw / active_term_count
            overall_effective_average_sum += effective_subject_average
            subjects_counted_for_overall_average += 1

        report_data.append({
            'subject': subject_name,
            'term_scores': term_scores_for_subject,
            'cumulative_total_score': f"{cumulative_score_raw:.2f}" if cumulative_score_raw is not None else 'N/A',
            'effective_subject_average': f"{effective_subject_average:.2f}" if effective_subject_average is not None else 'N/A',
            'grade': get_grade(effective_subject_average),
            'remark': get_subject_remark(effective_subject_average),
        })

    overall_session_average = None
    overall_remark = "No scores recorded for this session."
    if subjects_counted_for_overall_average > 0:
        overall_session_average = overall_effective_average_sum / subjects_counted_for_overall_average
        overall_remark = get_overall_remark(overall_session_average)

    motor_ability_scores = MotorAbilityScore.objects.filter(student=student, term__session=session)
    agg_motor = motor_ability_scores.aggregate(
        avg_honesty=Avg('honesty'), avg_politeness=Avg('politeness'),
        avg_neatness=Avg('neatness'), avg_cooperation=Avg('cooperation'),
        avg_obedience=Avg('obedience'), avg_attentiveness=Avg('attentiveness'),
        avg_punctuality=Avg('punctuality'), avg_perseverance=Avg('perseverance'),
        avg_emotional_stability=Avg('emotional_stability'), avg_attitude=Avg('attitude'),
        avg_leadership=Avg('leadership'), avg_physical_education=Avg('physical_education'),
        avg_games=Avg('games'), avg_musical=Avg('musical'),
        avg_handwriting=Avg('handwriting'), avg_reading=Avg('reading'),
        avg_verbal_fluency=Avg('verbal_fluency'), avg_handling_tools=Avg('handling_tools'),
    )
    processed_motor = {k: (round(min(v, 5)) if v is not None else 0) for k, v in agg_motor.items()}

    attendance_records = Attendance.objects.filter(
        student=student,
        date__gte=session.start_date,
        date__lte=session.end_date
    )
    total_school_days = attendance_records.count()
    days_present = attendance_records.filter(present=True).count()
    days_absent = attendance_records.filter(present=False).count()

    student_standard = get_student_standard_for_session(student, terms_in_session)
    session_comment = get_or_create_session_comment(student, session, student_standard, user=user)

    try:
        school_identity = SchoolIdentity.objects.first()
    except Exception:
        school_identity = None

    return {
        'student': student,
        'session': session,
        'terms_in_session': terms_in_session,
        'report_data': report_data,
        'overall_session_average': f"{overall_session_average:.2f}" if overall_session_average is not None else 'N/A',
        'overall_remark': overall_remark,
        'aggregated_motor_abilities': processed_motor,
        'school_identity': school_identity,
        'total_school_days': total_school_days,
        'days_present': days_present,
        'days_absent': days_absent,
        'session_comment': session_comment,
    }