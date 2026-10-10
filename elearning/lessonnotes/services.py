"""
Business logic for Teacher Lesson Notes: workflow, filtering, reporting.
Views stay thin and call into here.
"""
import csv
import io

from django.contrib.auth import get_user_model
from django.core.exceptions import FieldDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max, Q
from django.utils import timezone

from .models import LessonNote, LessonNoteEvent

Status = LessonNote.Status
Action = LessonNoteEvent.Action

# decision key (from the review form) -> (new status, audit action)
DECISIONS = {
    'approve': (Status.APPROVED, Action.APPROVED),
    'request_changes': (Status.REVISION, Action.REVISION),
}


def log_event(note, actor, action, remark=''):
    return LessonNoteEvent.objects.create(note=note, actor=actor, action=action, remark=remark)


# ---------------------------------------------------------------- workflow
@transaction.atomic
def create_note(note, teacher):
    note.teacher = teacher
    note.status = Status.SUBMITTED
    note.save()
    log_event(note, teacher, Action.SUBMITTED)
    return note


@transaction.atomic
def update_note(note, actor):
    """Teacher edits their note. Approved notes are locked; a note with
    requested changes goes back to the reviewer when the teacher saves it."""
    if note.status == Status.APPROVED:
        raise PermissionDenied('Approved lesson notes are locked.')
    resubmitting = note.status == Status.REVISION
    if resubmitting:
        note.status = Status.SUBMITTED
    note.save()
    log_event(note, actor, Action.RESUBMITTED if resubmitting else Action.EDITED)
    return note


@transaction.atomic
def review_note(note, reviewer, decision, remark=''):
    """School decision on a note: 'approve' or 'request_changes'."""
    if decision not in DECISIONS:
        raise ValidationError('Unknown decision.')
    if note.teacher_id == reviewer.id and not reviewer.is_superuser:
        raise PermissionDenied('You cannot review your own lesson note. Ask another reviewer.')
    remark = (remark or '').strip()
    if decision == 'request_changes' and not remark:
        raise ValidationError('Tell the teacher what needs to change.')

    note = LessonNote.objects.select_for_update().get(pk=note.pk)
    status, action = DECISIONS[decision]
    note.status = status
    note.reviewed_by = reviewer
    note.reviewed_at = timezone.now()
    note.review_remark = remark
    note.save()
    log_event(note, reviewer, action, remark)
    return note


# ---------------------------------------------------------------- queries
def filter_notes(qs, data):
    """Apply the (already validated) filter-form data to a LessonNote queryset."""
    q = (data.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q) | Q(subject_name__icontains=q)
            | Q(teacher__first_name__icontains=q) | Q(teacher__last_name__icontains=q)
            | Q(teacher__username__icontains=q)
        )
    for key, field in (('status', 'status'), ('term', 'term'), ('session', 'academic_session'),
                       ('standard', 'standard'), ('week', 'week'), ('teacher', 'teacher')):
        value = data.get(key)
        if value not in (None, ''):
            qs = qs.filter(**{field: value})
    return qs


def status_counts(qs):
    return qs.aggregate(
        total=Count('pk'),
        submitted=Count('pk', filter=Q(status=Status.SUBMITTED)),
        revision=Count('pk', filter=Q(status=Status.REVISION)),
        approved=Count('pk', filter=Q(status=Status.APPROVED)),
    )


def _teacher_scope():
    """Active teachers (via the Teacher profile if it exists) + anyone who has submitted a note."""
    User = get_user_model()
    has_notes = Q(pk__in=LessonNote.objects.values('teacher'))
    try:
        User._meta.get_field('teacher')  # reverse link from the Teacher profile model
    except FieldDoesNotExist:
        return has_notes
    return has_notes | Q(teacher__isnull=False, is_active=True)


def teacher_summary(session='', term=''):
    """One row per teacher with their note counts (zero rows included, so the
    school can see who has NOT submitted)."""
    User = get_user_model()
    scope = Q()
    if session:
        scope &= Q(elearning_lesson_notes__academic_session=session)
    if term:
        scope &= Q(elearning_lesson_notes__term=term)

    def counted(extra=None):
        cond = scope if extra is None else scope & extra
        return Count('elearning_lesson_notes', filter=cond if cond else None, distinct=True)

    return (
        User.objects.filter(_teacher_scope())
        .annotate(
            total=counted(),
            awaiting=counted(Q(elearning_lesson_notes__status=Status.SUBMITTED)),
            revision=counted(Q(elearning_lesson_notes__status=Status.REVISION)),
            approved=counted(Q(elearning_lesson_notes__status=Status.APPROVED)),
            last_submitted=Max('elearning_lesson_notes__submitted_at', filter=scope if scope else None),
        )
        .order_by('-awaiting', 'first_name', 'username')
    )


# ---------------------------------------------------------------- export
def _csv_safe(value):
    """Stop spreadsheet formula injection (=, +, -, @ at the start of a cell)."""
    if isinstance(value, str) and value[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + value
    return value


def notes_csv_bytes(qs):
    """CSV with a UTF-8 BOM so Excel opens accents/symbols correctly."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['Teacher', 'Class', 'Subject', 'Session', 'Term', 'Week', 'Title', 'File type',
                     'Status', 'Submitted', 'Reviewed by', 'Reviewed on', 'Reviewer remark', 'Link'])
    for n in qs.select_related('teacher', 'standard', 'reviewed_by').iterator():
        writer.writerow([_csv_safe(v) for v in (
            n.teacher_display, str(n.standard), n.subject_name, n.academic_session,
            n.get_term_display(), n.week, n.title, n.kind_label, n.get_status_display(),
            timezone.localtime(n.submitted_at).strftime('%Y-%m-%d %H:%M'),
            (n.reviewed_by.get_full_name() or n.reviewed_by.get_username()) if n.reviewed_by else '',
            timezone.localtime(n.reviewed_at).strftime('%Y-%m-%d %H:%M') if n.reviewed_at else '',
            n.review_remark, n.safe_link,
        )])
    return buf.getvalue().encode('utf-8-sig')