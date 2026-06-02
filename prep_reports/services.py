# # """
# # KwikSchools — Prep Report Card Services
# # ========================================
# # Single source of truth for all business logic in the prep_reports app.
# # Views, signals, and tests import from here — never inline logic elsewhere.

# # Confirmed model relationships (do not change field names below):
# # ─────────────────────────────────────────────────────────────────
# # staff.Teacher
# #     user               = OneToOneField(User)          reverse: user.teacher
# #     standards_assigned = ManyToManyField(Standard)
# #     subjects_taught    = ManyToManyField(Subject)
# #     active             = BooleanField

# # curriculum.Standard
# #     form_teacher       = ForeignKey(Teacher, related_name='form_class')

# # curriculum.Session
# #     is_current         = BooleanField

# # curriculum.Term
# #     is_current         = BooleanField
# #     session            = ForeignKey(Session)
# # ─────────────────────────────────────────────────────────────────
# # """

# # from collections import defaultdict

# # from django.db import transaction
# # from django.db.models import Q
# # from django.core.exceptions import PermissionDenied

# # from .models import (
# #     PrepClass,
# #     PrepReportCard,
# #     PrepSkillEntry,
# #     PrepDomainRating,
# #     PrepDomainTraitTemplate,
# #     PrepSubjectSkill,
# #     RatingScale,
# #     PrepAcademicPeriod,
# #     RatingColumn,
# # )


# # # ═══════════════════════════════════════════════════════════════════
# # # SECTION 1 — Internal helper
# # # ═══════════════════════════════════════════════════════════════════

# # def _get_teacher(user):
# #     """
# #     Safely resolves a User → Teacher instance.

# #     Teacher.user is a OneToOneField with no related_name, so Django
# #     creates the reverse accessor as  user.teacher.

# #     Returns the Teacher or None (never raises).
# #     Also returns None when the teacher's  active  flag is False,
# #     treating inactive staff as having no permissions.
# #     """
# #     try:
# #         teacher = user.teacher          # OneToOneField reverse accessor
# #     except Exception:
# #         return None

# #     # Inactive staff have no prep-report permissions
# #     if not teacher.active:
# #         return None

# #     return teacher


# # # ═══════════════════════════════════════════════════════════════════
# # # SECTION 2 — Permission helpers
# # # ═══════════════════════════════════════════════════════════════════

# # def user_can_edit_report(user, report_card):
# #     """
# #     Can this user view or save entries on this report card?

# #     Allowed when ANY of:
# #       • user.is_superuser
# #       • user.is_staff
# #       • user is an active Teacher whose standards_assigned includes
# #         the report card's Standard
# #     """
# #     if user.is_superuser or user.is_staff:
# #         return True

# #     teacher = _get_teacher(user)
# #     if teacher is None:
# #         return False

# #     return teacher.standards_assigned.filter(
# #         pk=report_card.prep_class.standard_id
# #     ).exists()


# # def user_can_edit_domain_ratings(user, report_card):
# #     """
# #     Can this user enter psychomotor / affective domain ratings?

# #     Allowed when ANY of:
# #       • user.is_superuser
# #       • user.is_staff
# #       • user is an active Teacher AND that Teacher is the form_teacher
# #         of the report card's Standard
# #         (Standard.form_teacher FK → Teacher, related_name='form_class')
# #     """
# #     if user.is_superuser or user.is_staff:
# #         return True

# #     teacher = _get_teacher(user)
# #     if teacher is None:
# #         return False

# #     standard = report_card.prep_class.standard

# #     return (
# #         standard.form_teacher_id is not None
# #         and standard.form_teacher_id == teacher.pk
# #     )


# # def user_can_enter_subject_skills(user, report_card, subject):
# #     """
# #     Can this user tick skill columns for the given subject on this card?

# #     Allowed when ALL of:
# #       1. user.is_superuser OR user.is_staff  (bypass)
# #       OR
# #       2. user is an active Teacher
# #          AND subject is in teacher.subjects_taught
# #          AND report card's Standard is in teacher.standards_assigned
# #     """
# #     if user.is_superuser or user.is_staff:
# #         return True

# #     teacher = _get_teacher(user)
# #     if teacher is None:
# #         return False

# #     teaches_this_subject = teacher.subjects_taught.filter(
# #         pk=subject.pk
# #     ).exists()

# #     assigned_to_this_class = teacher.standards_assigned.filter(
# #         pk=report_card.prep_class.standard_id
# #     ).exists()

# #     return teaches_this_subject and assigned_to_this_class


# # # ═══════════════════════════════════════════════════════════════════
# # # SECTION 3 — Report card creation
# # # ═══════════════════════════════════════════════════════════════════

# # @transaction.atomic
# # def create_report_card(student, prep_class, period, created_by, rating_scale=None):
# #     """
# #     Creates one PrepReportCard and pre-populates blank rows for:
# #       • PrepSkillEntry  — one per active skill for this class
# #       • PrepDomainRating — one per trait in PrepDomainTraitTemplate

# #     Idempotent: returns the existing card unchanged if already present.
# #     """
# #     if rating_scale is None:
# #         rating_scale = RatingScale.objects.filter(is_default=True).first()
# #         if not rating_scale:
# #             raise ValueError(
# #                 "No default rating scale is configured. "
# #                 "Go to Admin → Prep Reports → Rating Scales and mark one as default."
# #             )

# #     card, created = PrepReportCard.objects.get_or_create(
# #         student=student,
# #         prep_class=prep_class,
# #         period=period,
# #         defaults={
# #             'rating_scale': rating_scale,
# #             'created_by': created_by,
# #             'status': 'draft',
# #         },
# #     )

# #     if created:
# #         _populate_card(card, prep_class, created_by)

# #     return card


# # def _populate_card(card, prep_class, created_by):
# #     """
# #     Pre-populate blank skill entries and domain rating rows for a new card.
# #     Uses bulk_create with ignore_conflicts so re-runs are safe.
# #     """
# #     # Skills: those with no prep_class restriction (global) OR
# #     # explicitly assigned to this prep_class
# #     skills = PrepSubjectSkill.objects.filter(
# #         is_active=True,
# #     ).filter(
# #         Q(prep_class=prep_class) | Q(prep_class__isnull=True)
# #     )

# #     PrepSkillEntry.objects.bulk_create(
# #         [
# #             PrepSkillEntry(
# #                 report_card=card,
# #                 skill=skill,
# #                 entered_by=created_by,
# #             )
# #             for skill in skills
# #         ],
# #         ignore_conflicts=True,
# #     )

# #     # Domain trait templates: global (no prep_class) OR for this prep_class
# #     templates = PrepDomainTraitTemplate.objects.filter(
# #         Q(prep_class=prep_class) | Q(prep_class__isnull=True)
# #     ).order_by('domain', 'order')

# #     PrepDomainRating.objects.bulk_create(
# #         [
# #             PrepDomainRating(
# #                 report_card=card,
# #                 domain=t.domain,
# #                 trait_name=t.trait_name,
# #                 order=t.order,
# #             )
# #             for t in templates
# #         ],
# #         ignore_conflicts=True,
# #     )


# # @transaction.atomic
# # def bulk_create_report_cards_for_class(prep_class, period, created_by, rating_scale=None):
# #     """
# #     Creates report cards for every active student enrolled in prep_class.
# #     Returns (created_count, skipped_count).
# #     """
# #     from students.models import Student  # local import — avoids circular deps

# #     if rating_scale is None:
# #         rating_scale = RatingScale.objects.filter(is_default=True).first()
# #         if not rating_scale:
# #             raise ValueError("No default rating scale configured.")

# #     students_qs = Student.objects.filter(
# #         current_class=prep_class.standard,
# #         is_active=True,
# #     )

# #     created_count = 0
# #     skipped_count = 0

# #     for student in students_qs:
# #         card, was_created = PrepReportCard.objects.get_or_create(
# #             student=student,
# #             prep_class=prep_class,
# #             period=period,
# #             defaults={
# #                 'rating_scale': rating_scale,
# #                 'created_by': created_by,
# #                 'status': 'draft',
# #             },
# #         )
# #         if was_created:
# #             _populate_card(card, prep_class, created_by)
# #             created_count += 1
# #         else:
# #             skipped_count += 1

# #     return created_count, skipped_count


# # # ═══════════════════════════════════════════════════════════════════
# # # SECTION 4 — Saving entries
# # # ═══════════════════════════════════════════════════════════════════

# # @transaction.atomic
# # def save_subject_skill_entries(user, report_card, subject, skill_data, subject_comment=""):
# #     """
# #     Persists the teacher's column ticks for one subject block.

# #     Parameters
# #     ----------
# #     user            : request.user
# #     report_card     : PrepReportCard instance
# #     subject         : curriculum.Subject instance
# #     skill_data      : dict  { skill_id (int) : column_id (int | None) }
# #     subject_comment : optional free-text comment for the subject block

# #     Raises PermissionDenied if the teacher is not assigned to both
# #     this subject AND this class.
# #     """
# #     if not user_can_enter_subject_skills(user, report_card, subject):
# #         raise PermissionDenied(
# #             f"You are not assigned to teach '{subject.name}' "
# #             f"in {report_card.prep_class.standard}. "
# #             f"Contact the administrator if this is incorrect."
# #         )

# #     first_row = True
# #     for skill_id, column_id in skill_data.items():
# #         # Validate the column belongs to this card's rating scale
# #         column = None
# #         if column_id:
# #             try:
# #                 column = RatingColumn.objects.get(
# #                     pk=column_id,
# #                     scale=report_card.rating_scale,
# #                 )
# #             except RatingColumn.DoesNotExist:
# #                 pass   # silently ignore invalid column ids

# #         entry, _ = PrepSkillEntry.objects.get_or_create(
# #             report_card=report_card,
# #             skill_id=skill_id,
# #         )
# #         entry.selected_column = column
# #         entry.entered_by = user
# #         # Subject comment stored on the first skill row only
# #         if first_row:
# #             entry.subject_comment = subject_comment
# #             first_row = False
# #         entry.save()


# # @transaction.atomic
# # def save_domain_ratings(user, report_card, ratings_data):
# #     """
# #     Saves psychomotor / affective domain ratings.

# #     Parameters
# #     ----------
# #     ratings_data : list of dicts  [{'id': <int>, 'rating_text': '<str>'}]

# #     Only the form teacher of the class (or admin/staff) may call this.
# #     """
# #     if not user_can_edit_domain_ratings(user, report_card):
# #         raise PermissionDenied(
# #             "Only the form teacher of this class can enter "
# #             "psychomotor and affective domain ratings."
# #         )

# #     for item in ratings_data:
# #         PrepDomainRating.objects.filter(
# #             pk=item['id'],
# #             report_card=report_card,   # safety: never update another card's rows
# #         ).update(rating_text=item.get('rating_text', '').strip())


# # # ═══════════════════════════════════════════════════════════════════
# # # SECTION 5 — Workflow transitions
# # # ═══════════════════════════════════════════════════════════════════

# # def submit_report_card(user, report_card):
# #     """Draft → Submitted. Only the teacher assigned to the class may submit."""
# #     if report_card.status != 'draft':
# #         raise ValueError("Only draft report cards can be submitted for approval.")
# #     if not user_can_edit_report(user, report_card):
# #         raise PermissionDenied("You are not authorised to submit this report card.")
# #     report_card.status = 'submitted'
# #     report_card.save(update_fields=['status', 'updated_at'])


# # def approve_report_card(user, report_card):
# #     """Submitted → Approved. Admin / staff only."""
# #     if not (user.is_superuser or user.is_staff):
# #         raise PermissionDenied("Only admin or staff can approve report cards.")
# #     report_card.status = 'approved'
# #     report_card.approved_by = user
# #     report_card.save(update_fields=['status', 'approved_by', 'updated_at'])


# # def publish_report_card(user, report_card):
# #     """Approved → Published (visible to parents). Admin / staff only."""
# #     if not (user.is_superuser or user.is_staff):
# #         raise PermissionDenied("Only admin or staff can publish report cards.")
# #     report_card.status = 'published'
# #     report_card.save(update_fields=['status', 'updated_at'])


# # # ═══════════════════════════════════════════════════════════════════
# # # SECTION 6 — Template context builder
# # # ═══════════════════════════════════════════════════════════════════

# # def build_report_card_context(report_card):
# #     """
# #     Builds the full context dict consumed by both the edit template and
# #     the PDF render. Groups skill entries by subject name; splits domain
# #     ratings into psychomotor and affective buckets.
# #     """
# #     columns = list(report_card.rating_scale.columns.order_by('order'))

# #     entries = (
# #         report_card.skill_entries
# #         .select_related('skill__subject', 'selected_column', 'entered_by')
# #         .order_by('skill__subject__name', 'skill__order')
# #     )

# #     subjects = defaultdict(lambda: {'comment': '', 'skills': []})
# #     for entry in entries:
# #         subj_name = entry.skill.subject.name
# #         # Store the first non-empty subject comment found
# #         if not subjects[subj_name]['comment'] and entry.subject_comment:
# #             subjects[subj_name]['comment'] = entry.subject_comment
# #         subjects[subj_name]['skills'].append({
# #             'entry':              entry,
# #             'skill':              entry.skill,
# #             'selected_column_id': entry.selected_column_id,
# #         })

# #     psychomotor = list(
# #         report_card.domain_ratings
# #         .filter(domain='psychomotor')
# #         .order_by('order')
# #     )
# #     affective = list(
# #         report_card.domain_ratings
# #         .filter(domain='affective')
# #         .order_by('order')
# #     )

# #     return {
# #         'report_card':         report_card,
# #         'columns':             columns,
# #         'subjects_data':       dict(subjects),
# #         'psychomotor_ratings': psychomotor,
# #         'affective_ratings':   affective,
# #         'student':             report_card.student,
# #         'period':              report_card.period,
# #         'prep_class':          report_card.prep_class,
# #     }


# # # ═══════════════════════════════════════════════════════════════════
# # # SECTION 7 — Dashboard / navigation helpers
# # # ═══════════════════════════════════════════════════════════════════

# # def get_teacher_prep_classes(user):
# #     """
# #     Returns the PrepClass queryset this user may work with.

# #     Superuser / staff → all active prep classes.
# #     Teacher           → only prep classes whose Standard appears in
# #                         teacher.standards_assigned.
# #     Anyone else       → empty queryset.
# #     """
# #     if user.is_superuser or user.is_staff:
# #         return PrepClass.objects.filter(is_active=True).select_related('standard')

# #     teacher = _get_teacher(user)
# #     if teacher is None:
# #         return PrepClass.objects.none()

# #     assigned_standard_ids = teacher.standards_assigned.values_list('id', flat=True)

# #     return PrepClass.objects.filter(
# #         is_active=True,
# #         standard_id__in=assigned_standard_ids,
# #     ).select_related('standard')


# # def get_teacher_prep_subjects(user, prep_class):
# #     """
# #     Returns the Subject queryset a user may score for the given prep_class.

# #     Superuser / staff → all subjects that have skills for this class.
# #     Teacher           → intersection of subjects_taught and the above.
# #     Anyone else       → empty queryset.
# #     """
# #     from curriculum.models import Subject

# #     # Subjects that have at least one PrepSubjectSkill for this class
# #     # (either explicitly assigned or globally available)
# #     base_qs = Subject.objects.filter(
# #         prep_skills__isnull=False,
# #     ).filter(
# #         Q(prep_skills__prep_class=prep_class) |
# #         Q(prep_skills__prep_class__isnull=True)
# #     ).distinct()

# #     if user.is_superuser or user.is_staff:
# #         return base_qs

# #     teacher = _get_teacher(user)
# #     if teacher is None:
# #         return Subject.objects.none()

# #     # Restrict to what this teacher is actually assigned to teach
# #     taught_ids = teacher.subjects_taught.values_list('id', flat=True)
# #     return base_qs.filter(id__in=taught_ids)



# """
# KwikSchools — Prep Report Card Services
# ========================================
# Single source of truth for all business logic in the prep_reports app.
# Views, signals, and tests import from here — never inline logic elsewhere.

# Confirmed model relationships (do not change field names below):
# ─────────────────────────────────────────────────────────────────
# staff.Teacher
#     user               = OneToOneField(User)          reverse: user.teacher
#     standards_assigned = ManyToManyField(Standard)
#     subjects_taught    = ManyToManyField(Subject)
#     active             = BooleanField

# curriculum.Standard
#     form_teacher       = ForeignKey(Teacher, related_name='form_class')

# curriculum.Session
#     is_current         = BooleanField

# curriculum.Term
#     is_current         = BooleanField
#     session            = ForeignKey(Session)
# ─────────────────────────────────────────────────────────────────
# """

# from collections import defaultdict

# from django.db import transaction
# from django.db.models import Q
# from django.core.exceptions import PermissionDenied

# from .models import (
#     PrepClass,
#     PrepReportCard,
#     PrepSkillEntry,
#     PrepDomainRating,
#     PrepDomainTraitTemplate,
#     PrepSubjectSkill,
#     RatingScale,
#     PrepAcademicPeriod,
#     RatingColumn,
# )


# # ═══════════════════════════════════════════════════════════════════
# # SECTION 1 — Internal helper
# # ═══════════════════════════════════════════════════════════════════

# def _get_teacher(user):
#     """
#     Safely resolves a User → Teacher instance.

#     Teacher.user is a OneToOneField with no related_name, so Django
#     creates the reverse accessor as  user.teacher.

#     Returns the Teacher or None (never raises).
#     Also returns None when the teacher's  active  flag is False,
#     treating inactive staff as having no permissions.
#     """
#     try:
#         teacher = user.teacher          # OneToOneField reverse accessor
#     except Exception:
#         return None

#     # Inactive staff have no prep-report permissions
#     if not teacher.active:
#         return None

#     return teacher


# # ═══════════════════════════════════════════════════════════════════
# # SECTION 2 — Permission helpers
# # ═══════════════════════════════════════════════════════════════════

# def user_can_edit_report(user, report_card):
#     """
#     Can this user view or save entries on this report card?

#     Allowed when ANY of:
#       • user.is_superuser
#       • user.is_staff
#       • user is an active Teacher whose standards_assigned includes
#         the report card's Standard
#     """
#     if user.is_superuser or user.is_staff:
#         return True

#     teacher = _get_teacher(user)
#     if teacher is None:
#         return False

#     return teacher.standards_assigned.filter(
#         pk=report_card.prep_class.standard_id
#     ).exists()


# def user_can_edit_domain_ratings(user, report_card):
#     """
#     Can this user enter psychomotor / affective domain ratings?

#     Allowed when ANY of:
#       • user.is_superuser
#       • user.is_staff
#       • user is an active Teacher AND that Teacher is the form_teacher
#         of the report card's Standard
#         (Standard.form_teacher FK → Teacher, related_name='form_class')
#     """
#     if user.is_superuser or user.is_staff:
#         return True

#     teacher = _get_teacher(user)
#     if teacher is None:
#         return False

#     standard = report_card.prep_class.standard

#     return (
#         standard.form_teacher_id is not None
#         and standard.form_teacher_id == teacher.pk
#     )


# def user_can_enter_subject_skills(user, report_card, subject):
#     """
#     Can this user tick skill columns for the given subject on this card?

#     Allowed when ALL of:
#       1. user.is_superuser OR user.is_staff  (bypass)
#       OR
#       2. user is an active Teacher
#          AND subject is in teacher.subjects_taught
#          AND report card's Standard is in teacher.standards_assigned
#     """
#     if user.is_superuser or user.is_staff:
#         return True

#     teacher = _get_teacher(user)
#     if teacher is None:
#         return False

#     teaches_this_subject = teacher.subjects_taught.filter(
#         pk=subject.pk
#     ).exists()

#     assigned_to_this_class = teacher.standards_assigned.filter(
#         pk=report_card.prep_class.standard_id
#     ).exists()

#     return teaches_this_subject and assigned_to_this_class


# # ═══════════════════════════════════════════════════════════════════
# # SECTION 3 — Report card creation
# # ═══════════════════════════════════════════════════════════════════

# @transaction.atomic
# def create_report_card(student, prep_class, period, created_by, rating_scale=None):
#     """
#     Creates one PrepReportCard and pre-populates blank rows for:
#       • PrepSkillEntry  — one per active skill for this class
#       • PrepDomainRating — one per trait in PrepDomainTraitTemplate

#     Idempotent: returns the existing card unchanged if already present.
#     """
#     if rating_scale is None:
#         rating_scale = RatingScale.objects.filter(is_default=True).first()
#         if not rating_scale:
#             raise ValueError(
#                 "No default rating scale is configured. "
#                 "Go to Admin → Prep Reports → Rating Scales and mark one as default."
#             )

#     card, created = PrepReportCard.objects.get_or_create(
#         student=student,
#         prep_class=prep_class,
#         period=period,
#         defaults={
#             'rating_scale': rating_scale,
#             'created_by': created_by,
#             'status': 'draft',
#         },
#     )

#     if created:
#         _populate_card(card, prep_class, created_by)

#     return card


# def _populate_card(card, prep_class, created_by):
#     """
#     Pre-populate blank skill entries and domain rating rows for a new card.
#     Uses bulk_create with ignore_conflicts so re-runs are safe.
#     """
#     # Skills: those with no prep_class restriction (global) OR
#     # explicitly assigned to this prep_class
#     skills = PrepSubjectSkill.objects.filter(
#         is_active=True,
#     ).filter(
#         Q(prep_class=prep_class) | Q(prep_class__isnull=True)
#     )

#     PrepSkillEntry.objects.bulk_create(
#         [
#             PrepSkillEntry(
#                 report_card=card,
#                 skill=skill,
#                 entered_by=created_by,
#             )
#             for skill in skills
#         ],
#         ignore_conflicts=True,
#     )

#     # Domain trait templates: global (no prep_class) OR for this prep_class
#     templates = PrepDomainTraitTemplate.objects.filter(
#         Q(prep_class=prep_class) | Q(prep_class__isnull=True)
#     ).order_by('domain', 'order')

#     PrepDomainRating.objects.bulk_create(
#         [
#             PrepDomainRating(
#                 report_card=card,
#                 domain=t.domain,
#                 trait_name=t.trait_name,
#                 order=t.order,
#             )
#             for t in templates
#         ],
#         ignore_conflicts=True,
#     )


# @transaction.atomic
# def bulk_create_report_cards_for_class(prep_class, period, created_by, rating_scale=None):
#     """
#     Creates report cards for every active student enrolled in prep_class.
#     Returns (created_count, skipped_count).
#     """
#     from students.models import Student  # local import — avoids circular deps

#     if rating_scale is None:
#         rating_scale = RatingScale.objects.filter(is_default=True).first()
#         if not rating_scale:
#             raise ValueError("No default rating scale configured.")

#     students_qs = Student.objects.filter(
#         current_class=prep_class.standard,
#         student_status='active',   # Student model uses student_status, not is_active
#     )

#     created_count = 0
#     skipped_count = 0

#     for student in students_qs:
#         card, was_created = PrepReportCard.objects.get_or_create(
#             student=student,
#             prep_class=prep_class,
#             period=period,
#             defaults={
#                 'rating_scale': rating_scale,
#                 'created_by': created_by,
#                 'status': 'draft',
#             },
#         )
#         if was_created:
#             _populate_card(card, prep_class, created_by)
#             created_count += 1
#         else:
#             skipped_count += 1

#     return created_count, skipped_count


# # ═══════════════════════════════════════════════════════════════════
# # SECTION 4 — Saving entries
# # ═══════════════════════════════════════════════════════════════════

# @transaction.atomic
# def save_subject_skill_entries(user, report_card, subject, skill_data, subject_comment=""):
#     """
#     Persists the teacher's column ticks for one subject block.

#     Parameters
#     ----------
#     user            : request.user
#     report_card     : PrepReportCard instance
#     subject         : curriculum.Subject instance
#     skill_data      : dict  { skill_id (int) : column_id (int | None) }
#     subject_comment : optional free-text comment for the subject block

#     Raises PermissionDenied if the teacher is not assigned to both
#     this subject AND this class.
#     """
#     if not user_can_enter_subject_skills(user, report_card, subject):
#         raise PermissionDenied(
#             f"You are not assigned to teach '{subject.name}' "
#             f"in {report_card.prep_class.standard}. "
#             f"Contact the administrator if this is incorrect."
#         )

#     first_row = True
#     for skill_id, column_id in skill_data.items():
#         # Validate the column belongs to this card's rating scale
#         column = None
#         if column_id:
#             try:
#                 column = RatingColumn.objects.get(
#                     pk=column_id,
#                     scale=report_card.rating_scale,
#                 )
#             except RatingColumn.DoesNotExist:
#                 pass   # silently ignore invalid column ids

#         entry, _ = PrepSkillEntry.objects.get_or_create(
#             report_card=report_card,
#             skill_id=skill_id,
#         )
#         entry.selected_column = column
#         entry.entered_by = user
#         # Subject comment stored on the first skill row only
#         if first_row:
#             entry.subject_comment = subject_comment
#             first_row = False
#         entry.save()


# @transaction.atomic
# def save_domain_ratings(user, report_card, ratings_data):
#     """
#     Saves psychomotor / affective domain ratings.

#     Parameters
#     ----------
#     ratings_data : list of dicts  [{'id': <int>, 'rating_text': '<str>'}]

#     Only the form teacher of the class (or admin/staff) may call this.
#     """
#     if not user_can_edit_domain_ratings(user, report_card):
#         raise PermissionDenied(
#             "Only the form teacher of this class can enter "
#             "psychomotor and affective domain ratings."
#         )

#     for item in ratings_data:
#         PrepDomainRating.objects.filter(
#             pk=item['id'],
#             report_card=report_card,   # safety: never update another card's rows
#         ).update(rating_text=item.get('rating_text', '').strip())


# # ═══════════════════════════════════════════════════════════════════
# # SECTION 5 — Workflow transitions
# # ═══════════════════════════════════════════════════════════════════

# def submit_report_card(user, report_card):
#     """Draft → Submitted. Only the teacher assigned to the class may submit."""
#     if report_card.status != 'draft':
#         raise ValueError("Only draft report cards can be submitted for approval.")
#     if not user_can_edit_report(user, report_card):
#         raise PermissionDenied("You are not authorised to submit this report card.")
#     report_card.status = 'submitted'
#     report_card.save(update_fields=['status', 'updated_at'])


# def approve_report_card(user, report_card):
#     """Submitted → Approved. Admin / staff only."""
#     if not (user.is_superuser or user.is_staff):
#         raise PermissionDenied("Only admin or staff can approve report cards.")
#     report_card.status = 'approved'
#     report_card.approved_by = user
#     report_card.save(update_fields=['status', 'approved_by', 'updated_at'])


# def publish_report_card(user, report_card):
#     """Approved → Published (visible to parents). Admin / staff only."""
#     if not (user.is_superuser or user.is_staff):
#         raise PermissionDenied("Only admin or staff can publish report cards.")
#     report_card.status = 'published'
#     report_card.save(update_fields=['status', 'updated_at'])


# # ═══════════════════════════════════════════════════════════════════
# # SECTION 6 — Template context builder
# # ═══════════════════════════════════════════════════════════════════

# def build_report_card_context(report_card):
#     """
#     Builds the full context dict consumed by both the edit template and
#     the PDF render. Groups skill entries by subject name; splits domain
#     ratings into psychomotor and affective buckets.
#     """
#     columns = list(report_card.rating_scale.columns.order_by('order'))

#     entries = (
#         report_card.skill_entries
#         .select_related('skill__subject', 'selected_column', 'entered_by')
#         .order_by('skill__subject__name', 'skill__order')
#     )

#     subjects = defaultdict(lambda: {'comment': '', 'skills': []})
#     for entry in entries:
#         subj_name = entry.skill.subject.name
#         # Store the first non-empty subject comment found
#         if not subjects[subj_name]['comment'] and entry.subject_comment:
#             subjects[subj_name]['comment'] = entry.subject_comment
#         subjects[subj_name]['skills'].append({
#             'entry':              entry,
#             'skill':              entry.skill,
#             'selected_column_id': entry.selected_column_id,
#         })

#     psychomotor = list(
#         report_card.domain_ratings
#         .filter(domain='psychomotor')
#         .order_by('order')
#     )
#     affective = list(
#         report_card.domain_ratings
#         .filter(domain='affective')
#         .order_by('order')
#     )

#     return {
#         'report_card':         report_card,
#         'columns':             columns,
#         'subjects_data':       dict(subjects),
#         'psychomotor_ratings': psychomotor,
#         'affective_ratings':   affective,
#         'student':             report_card.student,
#         'period':              report_card.period,
#         'prep_class':          report_card.prep_class,
#     }


# # ═══════════════════════════════════════════════════════════════════
# # SECTION 7 — Dashboard / navigation helpers
# # ═══════════════════════════════════════════════════════════════════

# def get_teacher_prep_classes(user):
#     """
#     Returns the PrepClass queryset this user may work with.

#     Superuser / staff → all active prep classes.
#     Teacher           → only prep classes whose Standard appears in
#                         teacher.standards_assigned.
#     Anyone else       → empty queryset.
#     """
#     if user.is_superuser or user.is_staff:
#         return PrepClass.objects.filter(is_active=True).select_related('standard')

#     teacher = _get_teacher(user)
#     if teacher is None:
#         return PrepClass.objects.none()

#     assigned_standard_ids = teacher.standards_assigned.values_list('id', flat=True)

#     return PrepClass.objects.filter(
#         is_active=True,
#         standard_id__in=assigned_standard_ids,
#     ).select_related('standard')


# def get_teacher_prep_subjects(user, prep_class):
#     """
#     Returns the Subject queryset a user may score for the given prep_class.

#     Superuser / staff → all subjects that have skills for this class.
#     Teacher           → intersection of subjects_taught and the above.
#     Anyone else       → empty queryset.
#     """
#     from curriculum.models import Subject

#     # Subjects that have at least one PrepSubjectSkill for this class
#     # (either explicitly assigned or globally available)
#     base_qs = Subject.objects.filter(
#         prep_skills__isnull=False,
#     ).filter(
#         Q(prep_skills__prep_class=prep_class) |
#         Q(prep_skills__prep_class__isnull=True)
#     ).distinct()

#     if user.is_superuser or user.is_staff:
#         return base_qs

#     teacher = _get_teacher(user)
#     if teacher is None:
#         return Subject.objects.none()

#     # Restrict to what this teacher is actually assigned to teach
#     taught_ids = teacher.subjects_taught.values_list('id', flat=True)
#     return base_qs.filter(id__in=taught_ids)


# # ═══════════════════════════════════════════════════════════════════
# # SECTION 8 — Student portal helpers
# # ═══════════════════════════════════════════════════════════════════

# def get_student_from_user(user):
#     """
#     Resolves auth.User → students.Student safely.
#     Returns None if the user has no linked Student record.
#     The Student model links to User via a OneToOneField or ForeignKey;
#     Django's default reverse accessor is  user.student.
#     Adjust the accessor name below if your Student model uses
#     a different related_name on its user field.
#     """
#     try:
#         return user.student          # reverse accessor — adjust if needed
#     except Exception:
#         return None


# def get_student_report_cards(student, session_id=None, term_id=None):
#     """
#     Returns a queryset of PrepReportCards for a given student.

#     Only PUBLISHED cards are visible to the student.
#     Optionally filtered by curriculum Session and/or Term.

#     Parameters
#     ----------
#     student    : students.Student instance
#     session_id : int | None — curriculum.Session PK
#     term_id    : int | None — curriculum.Term PK
#     """
#     qs = (
#         PrepReportCard.objects
#         .filter(student=student, status='published')
#         .select_related(
#             'prep_class__standard',
#             'period__session',
#             'period__term',
#             'rating_scale',
#             'promoted_to',
#         )
#         .order_by(
#             '-period__session__start_date',
#             'period__term__start_date',
#         )
#     )

#     if session_id:
#         qs = qs.filter(period__session_id=session_id)

#     if term_id:
#         qs = qs.filter(period__term_id=term_id)

#     return qs


# def build_student_report_card_context(report_card, student):
#     """
#     Extends build_report_card_context() with student-safety checks.
#     Raises PermissionDenied when the card does not belong to the student
#     or has not been published yet.
#     """
#     # Ownership check
#     if report_card.student_id != student.pk:
#         raise PermissionDenied("This report card does not belong to you.")

#     # Visibility check — students only see published cards
#     if report_card.status != 'published':
#         raise PermissionDenied(
#             "This report card has not been published yet. "
#             "Please check back later or contact the school."
#         )

#     ctx = build_report_card_context(report_card)
#     ctx['readonly'] = True
#     ctx['student_view'] = True
#     return ctx

# 3rd edit ==============
"""
KwikSchools — Prep Report Card Services
========================================
All business logic lives here; views stay thin.

Confirmed model relationships:
─────────────────────────────────────────────────────────────────
staff.Teacher
    user               = OneToOneField(User)   reverse: user.teacher
    standards_assigned = ManyToManyField(Standard)
    subjects_taught    = ManyToManyField(Subject)
    active             = BooleanField

curriculum.Standard
    form_teacher       = ForeignKey(Teacher, related_name='form_class')

results.MotorAbilityScore
    student = ForeignKey(Student)
    term    = ForeignKey(Term)             unique_together = (student, term)
    Fields  : honesty, politeness, neatness, cooperation, obedience,
              attentiveness, punctuality, perseverance, emotional_stability,
              attitude, leadership, physical_education, musical, games,
              handwriting, reading, verbal_fluency, handling_tools
    All IntegerField(1–5, null/blank)

PrepAcademicPeriod
    term    = ForeignKey(curriculum.Term)  ← bridge to MotorAbilityScore
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
    PrepSubjectSkill,
    RatingScale,
    PrepAcademicPeriod,
    RatingColumn,
)

# MotorAbilityScore lives in the results app — imported locally where used
# to avoid circular imports and to keep the apps loosely coupled.
MOTOR_ABILITY_FIELDS = [
    # (field_name,          display_label)
    ('honesty',             'Honesty'),
    ('politeness',          'Politeness'),
    ('neatness',            'Neatness'),
    ('cooperation',         'Cooperation'),
    ('obedience',           'Obedience'),
    ('attentiveness',       'Attentiveness'),
    ('punctuality',         'Punctuality'),
    ('perseverance',        'Perseverance'),
    ('emotional_stability', 'Emotional Stability'),
    ('attitude',            'Attitude'),
    ('leadership',          'Leadership'),
    ('physical_education',  'Physical Education'),
    ('musical',             'Musical'),
    ('games',               'Games'),
    ('handwriting',         'Handwriting'),
    ('reading',             'Reading'),
    ('verbal_fluency',      'Verbal Fluency'),
    ('handling_tools',      'Handling Tools'),
]


# ═══════════════════════════════════════════════════════════════════
# SECTION 1 — Internal helpers
# ═══════════════════════════════════════════════════════════════════

def _get_teacher(user):
    """
    Safely resolves User → Teacher.
    Returns None when no Teacher record exists or when Teacher.active=False.
    """
    try:
        teacher = user.teacher
    except Exception:
        return None
    if not teacher.active:
        return None
    return teacher


def _get_motor_ability_score(student, term):
    """
    Fetches the MotorAbilityScore for the given student + term.
    Returns the instance or None — never raises.
    """
    try:
        from results.models import MotorAbilityScore
        return MotorAbilityScore.objects.filter(
            student=student, term=term
        ).first()
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# SECTION 2 — Permission helpers
# ═══════════════════════════════════════════════════════════════════

# def user_can_edit_report(user, report_card):
#     """
#     Superusers and is_staff: unrestricted.
#     Teacher: must have report card's Standard in standards_assigned.
#     """
#     if user.is_superuser or user.is_staff:
#         return True
#     teacher = _get_teacher(user)
#     if teacher is None:
#         return False
#     return teacher.standards_assigned.filter(
#         pk=report_card.prep_class.standard_id
#     ).exists()


# def user_can_edit_motor_scores(user, report_card):
#     """
#     Only the form teacher of the class (or admin/staff) may enter/edit
#     MotorAbilityScores for pupils in this prep class.

#     Standard.form_teacher FK → Teacher (related_name='form_class').
#     """
#     if user.is_superuser or user.is_staff:
#         return True
#     teacher = _get_teacher(user)
#     if teacher is None:
#         return False
#     standard = report_card.prep_class.standard
#     return (
#         standard.form_teacher_id is not None
#         and standard.form_teacher_id == teacher.pk
#     )


# # Keep old name as an alias so any code that still calls it doesn't break
# user_can_edit_domain_ratings = user_can_edit_motor_scores


# def user_can_enter_subject_skills(user, report_card, subject):
#     """
#     Teacher must teach the subject AND be assigned to the class.
#     Superusers/staff bypass.
#     """
#     if user.is_superuser or user.is_staff:
#         return True
#     teacher = _get_teacher(user)
#     if teacher is None:
#         return False
#     teaches_subject = teacher.subjects_taught.filter(pk=subject.pk).exists()
#     assigned_class  = teacher.standards_assigned.filter(
#         pk=report_card.prep_class.standard_id
#     ).exists()
#     return teaches_subject and assigned_class

# ═══════════════════════════════════════════════════════════════════
# SECTION 2 — Permission helpers
# ═══════════════════════════════════════════════════════════════════

# def user_can_edit_report(user, report_card):
#     """
#     Unrestricted: Superusers and is_staff.
#     Teacher Rules: Must be assigned to the class via `standards_assigned` 
#     OR be the designated `form_teacher` for that class's Standard.
#     """
#     if user.is_superuser or user.is_staff:
#         return True
    
#     teacher = _get_teacher(user)
#     if teacher is None:
#         return False

#     standard = report_card.prep_class.standard

#     # Check if the teacher is the form teacher of this class's standard
#     is_form_teacher = (standard.form_teacher_id == teacher.pk)
#     if is_form_teacher:
#         return True

#     # Otherwise, fallback check: must have the standard in assigned classes
#     return teacher.standards_assigned.filter(pk=standard.pk).exists()


# def user_can_edit_motor_scores(user, report_card):
#     """
#     Only Superusers, is_staff, or the explicit class form_teacher can 
#     enter or edit MotorAbilityScores for pupils in this class.
#     """
#     if user.is_superuser or user.is_staff:
#         return True
    
#     teacher = _get_teacher(user)
#     if teacher is None:
#         return False
        
#     standard = report_card.prep_class.standard
#     return standard.form_teacher_id == teacher.pk


# # Keep old name as an alias so any legacy view or admin call-sites don't break
# user_can_edit_domain_ratings = user_can_edit_motor_scores


# def user_can_enter_subject_skills(user, report_card, subject):
#     """
#     Teacher entry matrix:
#     - If they are the class form_teacher, they have access to all subjects for this class.
#     - Otherwise, they must teach the specific subject AND be explicitly assigned to the class.
#     """
#     if user.is_superuser or user.is_staff:
#         return True
        
#     teacher = _get_teacher(user)
#     if teacher is None:
#         return False

#     standard = report_card.prep_class.standard

#     # Rule 1: A class form teacher can manage all subjects for their own class
#     if standard.form_teacher_id == teacher.pk:
#         return True

#     # Rule 2: Subject teachers must fulfill both assignments (Class + Subject)
#     teaches_subject = teacher.subjects_taught.filter(pk=subject.pk).exists()
#     assigned_class  = teacher.standards_assigned.filter(pk=standard.pk).exists()
    
#     return teaches_subject and assigned_class


# def user_can_view_or_print_report(user, report_card):
#     """
#     Restricts viewing and compilation capabilities for official report documentation.
#     Accessible only by Admins, Staff, or the class form_teacher.
#     """
#     if user.is_superuser or user.is_staff:
#         return True

#     teacher = _get_teacher(user)
#     if teacher is None:
#         return False

#     standard = report_card.prep_class.standard
#     return standard.form_teacher_id == teacher.pk

# ═══════════════════════════════════════════════════════════════════
# SECTION 2 — Permission helpers
# ═══════════════════════════════════════════════════════════════════

def user_can_edit_report(user, report_card):
    """
    Page-level gatekeeper. Determines if a user can open this report card's edit screen.
    - Superusers / Staff: Unrestricted.
    - Form Teacher: Allowed if managing their own class.
    - Subject Teacher: Allowed if assigned to this class standard AND teaches 
      at least one active subject for it.
    """
    if user.is_superuser or user.is_staff:
        return True
    
    teacher = _get_teacher(user)
    if teacher is None:
        return False

    standard = report_card.prep_class.standard

    # If they are the class form teacher, they automatically get edit workspace access
    if standard.form_teacher_id == teacher.pk:
        return True

    # Check if they are assigned to this class standard at all
    is_assigned_to_class = teacher.standards_assigned.filter(pk=standard.pk).exists()
    if not is_assigned_to_class:
        return False

    # Verify if they teach any subjects tied to this class's report card entries
    from .models import PrepSubjectSkill
    teacher_subject_ids = teacher.subjects_taught.values_list('pk', flat=True)
    
    return PrepSubjectSkill.objects.filter(
        prep_class=report_card.prep_class,
        subject_id__in=teacher_subject_ids,
        is_active=True
    ).exists()


def user_can_modify_class_metadata(user, report_card):
    """
    Restricts administrative actions (Attendance modifications, Class Teacher Comments, 
    and Submission workflows) strictly to Admins, Staff, or the assigned Class Form Teacher.
    """
    if user.is_superuser or user.is_staff:
        return True
        
    teacher = _get_teacher(user)
    if teacher is None:
        return False
        
    return report_card.prep_class.standard.form_teacher_id == teacher.pk


def user_can_edit_motor_scores(user, report_card):
    """
    Psychomotor parameters / MotorAbilityScores can only be updated by 
    Admins, Staff, or the dedicated Form Teacher.
    """
    return user_can_modify_class_metadata(user, report_card)

# Keep old name alias alive for backwards compatibility
user_can_edit_domain_ratings = user_can_edit_motor_scores


def user_can_enter_subject_skills(user, report_card, subject):
    """
    Subject Skill Matrix validation:
    - Form Teacher: Can touch any subject within their own classroom.
    - Subject Teacher: Can ONLY modify if assigned to both the Standard class AND the Subject.
    """
    if user.is_superuser or user.is_staff:
        return True
        
    teacher = _get_teacher(user)
    if teacher is None:
        return False

    standard = report_card.prep_class.standard

    # Rule 1: Form teacher can access all items for their class standard
    if standard.form_teacher_id == teacher.pk:
        return True

    # Rule 2: Subject teachers must fulfill both relationship bindings explicitly
    teaches_subject = teacher.subjects_taught.filter(pk=subject.pk).exists()
    assigned_class  = teacher.standards_assigned.filter(pk=standard.pk).exists()
    
    return teaches_subject and assigned_class


def user_can_view_or_print_report(user, report_card):
    """
    Restricts access to viewing completed previews or printable report documentation.
    Accessible by Admins, Staff, or the class Form Teacher.
    """
    return user_can_modify_class_metadata(user, report_card)


# ═══════════════════════════════════════════════════════════════════
# SECTION 3 — Report card creation
# ═══════════════════════════════════════════════════════════════════

@transaction.atomic
def create_report_card(student, prep_class, period, created_by, rating_scale=None):
    """
    Creates one PrepReportCard and pre-populates blank PrepSkillEntry rows.
    MotorAbilityScore is NOT created here — it is fetched at render time
    from the results app (it may already exist from normal result entry).
    """
    if rating_scale is None:
        rating_scale = RatingScale.objects.filter(is_default=True).first()
        if not rating_scale:
            raise ValueError(
                "No default rating scale configured. "
                "Go to Admin → Prep Reports → Rating Scales."
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
    Pre-populate blank skill entries for a new card.
    Motor ability scores are NOT pre-created — they live in results app.
    Uses bulk_create(ignore_conflicts=True) so re-runs are safe.
    """
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


@transaction.atomic
def bulk_create_report_cards_for_class(prep_class, period, created_by, rating_scale=None):
    """
    Creates report cards for every active student enrolled in prep_class.
    Returns (created_count, skipped_count).
    """
    from students.models import Student

    if rating_scale is None:
        rating_scale = RatingScale.objects.filter(is_default=True).first()
        if not rating_scale:
            raise ValueError("No default rating scale configured.")

    students_qs = Student.objects.filter(
        current_class=prep_class.standard,
        student_status='active',
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
# SECTION 4 — Saving skill entries
# ═══════════════════════════════════════════════════════════════════

@transaction.atomic
def save_subject_skill_entries(user, report_card, subject, skill_data, subject_comment=""):
    """
    Persists the teacher's column ticks for one subject block.

    skill_data : dict { skill_id (int) : column_id (int|None) }
    Raises PermissionDenied when not authorised.
    """
    if not user_can_enter_subject_skills(user, report_card, subject):
        raise PermissionDenied(
            f"You are not assigned to teach '{subject.name}' in this class."
        )

    first_row = True
    for skill_id, column_id in skill_data.items():
        column = None
        if column_id:
            try:
                column = RatingColumn.objects.get(
                    pk=column_id,
                    scale=report_card.rating_scale,
                )
            except RatingColumn.DoesNotExist:
                pass

        entry, _ = PrepSkillEntry.objects.get_or_create(
            report_card=report_card,
            skill_id=skill_id,
        )
        entry.selected_column = column
        entry.entered_by = user
        if first_row:
            entry.subject_comment = subject_comment
            first_row = False
        entry.save()


# ═══════════════════════════════════════════════════════════════════
# SECTION 5 — MotorAbilityScore entry (replaces save_domain_ratings)
# ═══════════════════════════════════════════════════════════════════

@transaction.atomic
def save_motor_ability_scores(user, report_card, scores_data):
    """
    Creates or updates the MotorAbilityScore record for the report card's
    student + term using the existing results.MotorAbilityScore model.

    Only the form teacher (or admin/staff) may call this.

    scores_data : dict { field_name: int_value_or_None }
    e.g. {'honesty': 4, 'neatness': 5, 'games': None, ...}
    """
    if not user_can_edit_motor_scores(user, report_card):
        raise PermissionDenied(
            "Only the form teacher of this class can enter "
            "motor ability / psychomotor scores."
        )

    from results.models import MotorAbilityScore

    term = report_card.period.term
    student = report_card.student

    mas, _ = MotorAbilityScore.objects.get_or_create(
        student=student,
        term=term,
    )

    valid_fields = {f for f, _ in MOTOR_ABILITY_FIELDS}
    for field_name, value in scores_data.items():
        if field_name not in valid_fields:
            continue
        # Convert empty string → None; coerce numeric strings → int
        if value == '' or value is None:
            setattr(mas, field_name, None)
        else:
            try:
                int_val = int(value)
                if 1 <= int_val <= 5:
                    setattr(mas, field_name, int_val)
                else:
                    setattr(mas, field_name, None)
            except (ValueError, TypeError):
                setattr(mas, field_name, None)

    mas.save()
    return mas


# Keep old name as alias so any existing call sites still work
def save_domain_ratings(user, report_card, ratings_data):
    """
    Deprecated shim — maps old PrepDomainRating-style call to
    save_motor_ability_scores().  ratings_data here is expected as a
    dict { field_name: value } matching MotorAbilityScore fields.
    """
    return save_motor_ability_scores(user, report_card, ratings_data)


# ═══════════════════════════════════════════════════════════════════
# SECTION 6 — Workflow transitions
# ═══════════════════════════════════════════════════════════════════

def submit_report_card(user, report_card):
    if report_card.status != 'draft':
        raise ValueError("Only draft report cards can be submitted.")
    if not user_can_edit_report(user, report_card):
        raise PermissionDenied("You are not authorised to submit this report card.")
    report_card.status = 'submitted'
    report_card.save(update_fields=['status', 'updated_at'])


def approve_report_card(user, report_card):
    if not (user.is_superuser or user.is_staff):
        raise PermissionDenied("Only admin or staff can approve report cards.")
    report_card.status = 'approved'
    report_card.approved_by = user
    report_card.save(update_fields=['status', 'approved_by', 'updated_at'])


def publish_report_card(user, report_card):
    if not (user.is_superuser or user.is_staff):
        raise PermissionDenied("Only admin or staff can publish report cards.")
    report_card.status = 'published'
    report_card.save(update_fields=['status', 'updated_at'])


# ═══════════════════════════════════════════════════════════════════
# SECTION 7 — Context builder
# ═══════════════════════════════════════════════════════════════════

def build_report_card_context(report_card):
    """
    Builds the full template context dict.

    motor_ability_score : MotorAbilityScore instance or None
    motor_ability_fields: list of (field_name, display_label, value)
                          — ready for the template to iterate over
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
        if not subjects[subj_name]['comment'] and entry.subject_comment:
            subjects[subj_name]['comment'] = entry.subject_comment
        subjects[subj_name]['skills'].append({
            'entry':              entry,
            'skill':              entry.skill,
            'selected_column_id': entry.selected_column_id,
        })

    # Fetch MotorAbilityScore from results app using student + term
    motor_score = _get_motor_ability_score(
        report_card.student,
        report_card.period.term,
    )

    # Build a flat list of (field_name, label, current_value) for templates
    motor_fields = [
        (fname, label, getattr(motor_score, fname, None) if motor_score else None)
        for fname, label in MOTOR_ABILITY_FIELDS
    ]

    return {
        'report_card':         report_card,
        'columns':             columns,
        'subjects_data':       dict(subjects),
        # Keep old keys so existing templates that reference them don't break:
        'psychomotor_ratings': [],   # emptied — use motor_ability_fields instead
        'affective_ratings':   [],   # emptied — use motor_ability_fields instead
        # New keys:
        'motor_ability_score':  motor_score,
        'motor_ability_fields': motor_fields,
        'student':             report_card.student,
        'period':              report_card.period,
        'prep_class':          report_card.prep_class,
    }


# ═══════════════════════════════════════════════════════════════════
# SECTION 8 — Dashboard helpers
# ═══════════════════════════════════════════════════════════════════

def get_teacher_prep_classes(user):
    if user.is_superuser or user.is_staff:
        return PrepClass.objects.filter(is_active=True).select_related('standard')
    teacher = _get_teacher(user)
    if teacher is None:
        return PrepClass.objects.none()
    assigned_ids = teacher.standards_assigned.values_list('id', flat=True)
    return PrepClass.objects.filter(
        is_active=True,
        standard_id__in=assigned_ids,
    ).select_related('standard')


def get_teacher_prep_subjects(user, prep_class):
    from curriculum.models import Subject
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

    taught_ids = teacher.subjects_taught.values_list('id', flat=True)
    return base_qs.filter(id__in=taught_ids)


# ═══════════════════════════════════════════════════════════════════
# SECTION 9 — Student portal helpers
# ═══════════════════════════════════════════════════════════════════

def get_student_from_user(user):
    try:
        return user.student
    except Exception:
        return None


def get_student_report_cards(student, session_id=None, term_id=None):
    qs = (
        PrepReportCard.objects
        .filter(student=student, status='published')
        .select_related(
            'prep_class__standard',
            'period__session',
            'period__term',
            'rating_scale',
            'promoted_to',
        )
        .order_by(
            '-period__session__start_date',
            'period__term__start_date',
        )
    )
    if session_id:
        qs = qs.filter(period__session_id=session_id)
    if term_id:
        qs = qs.filter(period__term_id=term_id)
    return qs


def build_student_report_card_context(report_card, student):
    if report_card.student_id != student.pk:
        raise PermissionDenied("This report card does not belong to you.")
    if report_card.status != 'published':
        raise PermissionDenied(
            "This report card has not been published yet. "
            "Please check back later or contact the school."
        )
    ctx = build_report_card_context(report_card)
    ctx['readonly'] = True
    ctx['student_view'] = True
    return ctx
