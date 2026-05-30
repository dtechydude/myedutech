"""
KwikSchools — Prep Report Card Services
========================================
Single source of truth for all business logic in the prep_reports app.
Views, signals, and tests import from here — never inline logic elsewhere.

Confirmed model relationships (do not change field names below):
─────────────────────────────────────────────────────────────────
staff.Teacher
    user               = OneToOneField(User)          reverse: user.teacher
    standards_assigned = ManyToManyField(Standard)
    subjects_taught    = ManyToManyField(Subject)
    active             = BooleanField

curriculum.Standard
    form_teacher       = ForeignKey(Teacher, related_name='form_class')

curriculum.Session
    is_current         = BooleanField

curriculum.Term
    is_current         = BooleanField
    session            = ForeignKey(Session)
─────────────────────────────────────────────────────────────────
"""

from collections import defaultdict

from django.db import transaction
from django.db.models import Q
from django.core.exceptions import PermissionDenied

from .models import (
    PrepClass,
    PrepReportCard,
    PrepSkillEntry,
    PrepDomainRating,
    PrepDomainTraitTemplate,
    PrepSubjectSkill,
    RatingScale,
    PrepAcademicPeriod,
    RatingColumn,
)


# ═══════════════════════════════════════════════════════════════════
# SECTION 1 — Internal helper
# ═══════════════════════════════════════════════════════════════════

def _get_teacher(user):
    """
    Safely resolves a User → Teacher instance.

    Teacher.user is a OneToOneField with no related_name, so Django
    creates the reverse accessor as  user.teacher.

    Returns the Teacher or None (never raises).
    Also returns None when the teacher's  active  flag is False,
    treating inactive staff as having no permissions.
    """
    try:
        teacher = user.teacher          # OneToOneField reverse accessor
    except Exception:
        return None

    # Inactive staff have no prep-report permissions
    if not teacher.active:
        return None

    return teacher


# ═══════════════════════════════════════════════════════════════════
# SECTION 2 — Permission helpers
# ═══════════════════════════════════════════════════════════════════

def user_can_edit_report(user, report_card):
    """
    Can this user view or save entries on this report card?

    Allowed when ANY of:
      • user.is_superuser
      • user.is_staff
      • user is an active Teacher whose standards_assigned includes
        the report card's Standard
    """
    if user.is_superuser or user.is_staff:
        return True

    teacher = _get_teacher(user)
    if teacher is None:
        return False

    return teacher.standards_assigned.filter(
        pk=report_card.prep_class.standard_id
    ).exists()


def user_can_edit_domain_ratings(user, report_card):
    """
    Can this user enter psychomotor / affective domain ratings?

    Allowed when ANY of:
      • user.is_superuser
      • user.is_staff
      • user is an active Teacher AND that Teacher is the form_teacher
        of the report card's Standard
        (Standard.form_teacher FK → Teacher, related_name='form_class')
    """
    if user.is_superuser or user.is_staff:
        return True

    teacher = _get_teacher(user)
    if teacher is None:
        return False

    standard = report_card.prep_class.standard

    return (
        standard.form_teacher_id is not None
        and standard.form_teacher_id == teacher.pk
    )


def user_can_enter_subject_skills(user, report_card, subject):
    """
    Can this user tick skill columns for the given subject on this card?

    Allowed when ALL of:
      1. user.is_superuser OR user.is_staff  (bypass)
      OR
      2. user is an active Teacher
         AND subject is in teacher.subjects_taught
         AND report card's Standard is in teacher.standards_assigned
    """
    if user.is_superuser or user.is_staff:
        return True

    teacher = _get_teacher(user)
    if teacher is None:
        return False

    teaches_this_subject = teacher.subjects_taught.filter(
        pk=subject.pk
    ).exists()

    assigned_to_this_class = teacher.standards_assigned.filter(
        pk=report_card.prep_class.standard_id
    ).exists()

    return teaches_this_subject and assigned_to_this_class


# ═══════════════════════════════════════════════════════════════════
# SECTION 3 — Report card creation
# ═══════════════════════════════════════════════════════════════════

@transaction.atomic
def create_report_card(student, prep_class, period, created_by, rating_scale=None):
    """
    Creates one PrepReportCard and pre-populates blank rows for:
      • PrepSkillEntry  — one per active skill for this class
      • PrepDomainRating — one per trait in PrepDomainTraitTemplate

    Idempotent: returns the existing card unchanged if already present.
    """
    if rating_scale is None:
        rating_scale = RatingScale.objects.filter(is_default=True).first()
        if not rating_scale:
            raise ValueError(
                "No default rating scale is configured. "
                "Go to Admin → Prep Reports → Rating Scales and mark one as default."
            )

    card, created = PrepReportCard.objects.get_or_create(
        student=student,
        prep_class=prep_class,
        period=period,
        defaults={
            'rating_scale': rating_scale,
            'created_by': created_by,
            'status': 'draft',
        },
    )

    if created:
        _populate_card(card, prep_class, created_by)

    return card


def _populate_card(card, prep_class, created_by):
    """
    Pre-populate blank skill entries and domain rating rows for a new card.
    Uses bulk_create with ignore_conflicts so re-runs are safe.
    """
    # Skills: those with no prep_class restriction (global) OR
    # explicitly assigned to this prep_class
    skills = PrepSubjectSkill.objects.filter(
        is_active=True,
    ).filter(
        Q(prep_class=prep_class) | Q(prep_class__isnull=True)
    )

    PrepSkillEntry.objects.bulk_create(
        [
            PrepSkillEntry(
                report_card=card,
                skill=skill,
                entered_by=created_by,
            )
            for skill in skills
        ],
        ignore_conflicts=True,
    )

    # Domain trait templates: global (no prep_class) OR for this prep_class
    templates = PrepDomainTraitTemplate.objects.filter(
        Q(prep_class=prep_class) | Q(prep_class__isnull=True)
    ).order_by('domain', 'order')

    PrepDomainRating.objects.bulk_create(
        [
            PrepDomainRating(
                report_card=card,
                domain=t.domain,
                trait_name=t.trait_name,
                order=t.order,
            )
            for t in templates
        ],
        ignore_conflicts=True,
    )


@transaction.atomic
def bulk_create_report_cards_for_class(prep_class, period, created_by, rating_scale=None):
    """
    Creates report cards for every active student enrolled in prep_class.
    Returns (created_count, skipped_count).
    """
    from students.models import Student  # local import — avoids circular deps

    if rating_scale is None:
        rating_scale = RatingScale.objects.filter(is_default=True).first()
        if not rating_scale:
            raise ValueError("No default rating scale configured.")

    students_qs = Student.objects.filter(
        current_class=prep_class.standard,
        is_active=True,
    )

    created_count = 0
    skipped_count = 0

    for student in students_qs:
        card, was_created = PrepReportCard.objects.get_or_create(
            student=student,
            prep_class=prep_class,
            period=period,
            defaults={
                'rating_scale': rating_scale,
                'created_by': created_by,
                'status': 'draft',
            },
        )
        if was_created:
            _populate_card(card, prep_class, created_by)
            created_count += 1
        else:
            skipped_count += 1

    return created_count, skipped_count


# ═══════════════════════════════════════════════════════════════════
# SECTION 4 — Saving entries
# ═══════════════════════════════════════════════════════════════════

@transaction.atomic
def save_subject_skill_entries(user, report_card, subject, skill_data, subject_comment=""):
    """
    Persists the teacher's column ticks for one subject block.

    Parameters
    ----------
    user            : request.user
    report_card     : PrepReportCard instance
    subject         : curriculum.Subject instance
    skill_data      : dict  { skill_id (int) : column_id (int | None) }
    subject_comment : optional free-text comment for the subject block

    Raises PermissionDenied if the teacher is not assigned to both
    this subject AND this class.
    """
    if not user_can_enter_subject_skills(user, report_card, subject):
        raise PermissionDenied(
            f"You are not assigned to teach '{subject.name}' "
            f"in {report_card.prep_class.standard}. "
            f"Contact the administrator if this is incorrect."
        )

    first_row = True
    for skill_id, column_id in skill_data.items():
        # Validate the column belongs to this card's rating scale
        column = None
        if column_id:
            try:
                column = RatingColumn.objects.get(
                    pk=column_id,
                    scale=report_card.rating_scale,
                )
            except RatingColumn.DoesNotExist:
                pass   # silently ignore invalid column ids

        entry, _ = PrepSkillEntry.objects.get_or_create(
            report_card=report_card,
            skill_id=skill_id,
        )
        entry.selected_column = column
        entry.entered_by = user
        # Subject comment stored on the first skill row only
        if first_row:
            entry.subject_comment = subject_comment
            first_row = False
        entry.save()


@transaction.atomic
def save_domain_ratings(user, report_card, ratings_data):
    """
    Saves psychomotor / affective domain ratings.

    Parameters
    ----------
    ratings_data : list of dicts  [{'id': <int>, 'rating_text': '<str>'}]

    Only the form teacher of the class (or admin/staff) may call this.
    """
    if not user_can_edit_domain_ratings(user, report_card):
        raise PermissionDenied(
            "Only the form teacher of this class can enter "
            "psychomotor and affective domain ratings."
        )

    for item in ratings_data:
        PrepDomainRating.objects.filter(
            pk=item['id'],
            report_card=report_card,   # safety: never update another card's rows
        ).update(rating_text=item.get('rating_text', '').strip())


# ═══════════════════════════════════════════════════════════════════
# SECTION 5 — Workflow transitions
# ═══════════════════════════════════════════════════════════════════

def submit_report_card(user, report_card):
    """Draft → Submitted. Only the teacher assigned to the class may submit."""
    if report_card.status != 'draft':
        raise ValueError("Only draft report cards can be submitted for approval.")
    if not user_can_edit_report(user, report_card):
        raise PermissionDenied("You are not authorised to submit this report card.")
    report_card.status = 'submitted'
    report_card.save(update_fields=['status', 'updated_at'])


def approve_report_card(user, report_card):
    """Submitted → Approved. Admin / staff only."""
    if not (user.is_superuser or user.is_staff):
        raise PermissionDenied("Only admin or staff can approve report cards.")
    report_card.status = 'approved'
    report_card.approved_by = user
    report_card.save(update_fields=['status', 'approved_by', 'updated_at'])


def publish_report_card(user, report_card):
    """Approved → Published (visible to parents). Admin / staff only."""
    if not (user.is_superuser or user.is_staff):
        raise PermissionDenied("Only admin or staff can publish report cards.")
    report_card.status = 'published'
    report_card.save(update_fields=['status', 'updated_at'])


# ═══════════════════════════════════════════════════════════════════
# SECTION 6 — Template context builder
# ═══════════════════════════════════════════════════════════════════

def build_report_card_context(report_card):
    """
    Builds the full context dict consumed by both the edit template and
    the PDF render. Groups skill entries by subject name; splits domain
    ratings into psychomotor and affective buckets.
    """
    columns = list(report_card.rating_scale.columns.order_by('order'))

    entries = (
        report_card.skill_entries
        .select_related('skill__subject', 'selected_column', 'entered_by')
        .order_by('skill__subject__name', 'skill__order')
    )

    subjects = defaultdict(lambda: {'comment': '', 'skills': []})
    for entry in entries:
        subj_name = entry.skill.subject.name
        # Store the first non-empty subject comment found
        if not subjects[subj_name]['comment'] and entry.subject_comment:
            subjects[subj_name]['comment'] = entry.subject_comment
        subjects[subj_name]['skills'].append({
            'entry':              entry,
            'skill':              entry.skill,
            'selected_column_id': entry.selected_column_id,
        })

    psychomotor = list(
        report_card.domain_ratings
        .filter(domain='psychomotor')
        .order_by('order')
    )
    affective = list(
        report_card.domain_ratings
        .filter(domain='affective')
        .order_by('order')
    )

    return {
        'report_card':         report_card,
        'columns':             columns,
        'subjects_data':       dict(subjects),
        'psychomotor_ratings': psychomotor,
        'affective_ratings':   affective,
        'student':             report_card.student,
        'period':              report_card.period,
        'prep_class':          report_card.prep_class,
    }


# ═══════════════════════════════════════════════════════════════════
# SECTION 7 — Dashboard / navigation helpers
# ═══════════════════════════════════════════════════════════════════

def get_teacher_prep_classes(user):
    """
    Returns the PrepClass queryset this user may work with.

    Superuser / staff → all active prep classes.
    Teacher           → only prep classes whose Standard appears in
                        teacher.standards_assigned.
    Anyone else       → empty queryset.
    """
    if user.is_superuser or user.is_staff:
        return PrepClass.objects.filter(is_active=True).select_related('standard')

    teacher = _get_teacher(user)
    if teacher is None:
        return PrepClass.objects.none()

    assigned_standard_ids = teacher.standards_assigned.values_list('id', flat=True)

    return PrepClass.objects.filter(
        is_active=True,
        standard_id__in=assigned_standard_ids,
    ).select_related('standard')


def get_teacher_prep_subjects(user, prep_class):
    """
    Returns the Subject queryset a user may score for the given prep_class.

    Superuser / staff → all subjects that have skills for this class.
    Teacher           → intersection of subjects_taught and the above.
    Anyone else       → empty queryset.
    """
    from curriculum.models import Subject

    # Subjects that have at least one PrepSubjectSkill for this class
    # (either explicitly assigned or globally available)
    base_qs = Subject.objects.filter(
        prep_skills__isnull=False,
    ).filter(
        Q(prep_skills__prep_class=prep_class) |
        Q(prep_skills__prep_class__isnull=True)
    ).distinct()

    if user.is_superuser or user.is_staff:
        return base_qs

    teacher = _get_teacher(user)
    if teacher is None:
        return Subject.objects.none()

    # Restrict to what this teacher is actually assigned to teach
    taught_ids = teacher.subjects_taught.values_list('id', flat=True)
    return base_qs.filter(id__in=taught_ids)
