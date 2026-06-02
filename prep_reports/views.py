"""
KwikSchools — Prep Report Card Views
=====================================
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import ListView, TemplateView

from .models import (
    PrepClass, PrepReportCard, PrepSkillEntry,
    PrepDomainRating, PrepSubjectSkill, PrepAcademicPeriod,
    RatingColumn, RatingScale,
)
from .services import (
    build_report_card_context,
    bulk_create_report_cards_for_class,
    create_report_card,
    get_teacher_prep_classes,
    get_teacher_prep_subjects,
    save_domain_ratings,
    save_subject_skill_entries,
    submit_report_card,
    approve_report_card,
    publish_report_card,
    user_can_edit_report,
    user_can_edit_domain_ratings,
)
from .forms import (
    PrepReportCardCommentForm,
    PrepDomainRatingForm,
    BulkCreateReportForm,
)


# ---------------------------------------------------------------------------
# Dashboard / Overview
# ---------------------------------------------------------------------------

class PrepDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'prep_reports/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        prep_classes = get_teacher_prep_classes(user)
        period = PrepAcademicPeriod.get_current()

        stats = []
        for pc in prep_classes:
            total = PrepReportCard.objects.filter(
                prep_class=pc, period=period
            ).count() if period else 0
            completed = PrepReportCard.objects.filter(
                prep_class=pc, period=period,
                status__in=['submitted', 'approved', 'published']
            ).count() if period else 0
            stats.append({
                'prep_class': pc,
                'total': total,
                'completed': completed,
                'pending': total - completed,
            })

        ctx.update({
            'prep_classes': prep_classes,
            'current_period': period,
            'stats': stats,
        })
        return ctx


# ---------------------------------------------------------------------------
# Class-level: list all students / report cards
# ---------------------------------------------------------------------------

class PrepClassStudentListView(LoginRequiredMixin, ListView):
    template_name = 'prep_reports/class_student_list.html'
    context_object_name = 'report_cards'
    paginate_by = 40

    def dispatch(self, request, *args, **kwargs):
        self.prep_class = get_object_or_404(PrepClass, pk=kwargs['prep_class_id'])
        self.period = get_object_or_404(PrepAcademicPeriod, pk=kwargs['period_id'])
        allowed_classes = get_teacher_prep_classes(request.user)
        if not (request.user.is_superuser or request.user.is_staff):
            if not allowed_classes.filter(pk=self.prep_class.pk).exists():
                raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            PrepReportCard.objects
            .filter(prep_class=self.prep_class, period=self.period)
            .select_related('student__user', 'prep_class__standard')
            .order_by('student__user__last_name')
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['prep_class'] = self.prep_class
        ctx['period'] = self.period
        ctx['periods'] = PrepAcademicPeriod.objects.select_related('session', 'term').order_by('-session__start_date', 'term__start_date')
        ctx['can_bulk_create'] = (
            self.request.user.is_superuser or self.request.user.is_staff
        )
        return ctx


# ---------------------------------------------------------------------------
# Bulk-create report cards for a class
# ---------------------------------------------------------------------------

class BulkCreateReportCardsView(LoginRequiredMixin, View):
    def post(self, request, prep_class_id, period_id):
        if not (request.user.is_superuser or request.user.is_staff):
            raise PermissionDenied
        prep_class = get_object_or_404(PrepClass, pk=prep_class_id)
        period = get_object_or_404(PrepAcademicPeriod, pk=period_id)
        created, skipped = bulk_create_report_cards_for_class(
            prep_class, period, request.user
        )
        messages.success(
            request,
            f"Report cards created: {created} new, {skipped} already existed."
        )
        return redirect('prep_reports:class_students', prep_class_id=prep_class_id, period_id=period_id)


# ---------------------------------------------------------------------------
# Single Report Card: teacher entry view (MAIN EDITING VIEW)
# ---------------------------------------------------------------------------

# class PrepReportCardEditView(LoginRequiredMixin, View):
#     template_name = 'prep_reports/report_card_edit.html'

#     def _get_objects(self, report_card_id):
#         return get_object_or_404(
#             PrepReportCard.select_related(
#                 'student__user', 'prep_class__standard',
#                 'period', 'rating_scale'
#             ) if hasattr(PrepReportCard, 'select_related')
#             else PrepReportCard.objects.select_related(
#                 'student__user', 'prep_class__standard',
#                 'period', 'rating_scale'
#             ),
#             pk=report_card_id
#         )

#     def get(self, request, report_card_id):
#         card = get_object_or_404(
#             PrepReportCard.objects.select_related(
#                 'student__user', 'prep_class__standard', 'period', 'rating_scale'
#             ),
#             pk=report_card_id
#         )
#         if not user_can_edit_report(request.user, card):
#             raise PermissionDenied

#         subjects = get_teacher_prep_subjects(request.user, card.prep_class)
#         ctx = build_report_card_context(card)
#         ctx['subjects'] = subjects
#         ctx['can_edit_domains'] = user_can_edit_domain_ratings(request.user, card)
#         ctx['comment_form'] = PrepReportCardCommentForm(instance=card)
#         ctx['is_editable'] = card.status in ('draft', 'submitted')
#         return render(request, self.template_name, ctx)

#     def post(self, request, report_card_id):
#         card = get_object_or_404(PrepReportCard, pk=report_card_id)
#         if not user_can_edit_report(request.user, card):
#             raise PermissionDenied

#         action = request.POST.get('action', 'save')

#         # --- Save teacher comment ---
#         if action == 'save_comment':
#             form = PrepReportCardCommentForm(request.POST, instance=card)
#             if form.is_valid():
#                 form.save()
#                 messages.success(request, "Comments saved successfully.")
#             else:
#                 messages.error(request, "Error saving comments.")
#             return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

#         # --- Save skill entries for a subject ---
#         if action == 'save_skills':
#             subject_id = request.POST.get('subject_id')
#             if not subject_id:
#                 messages.error(request, "No subject specified.")
#                 return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

#             from curriculum.models import Subject
#             subject = get_object_or_404(Subject, pk=subject_id)
#             subject_comment = request.POST.get(f'subject_comment_{subject_id}', '')

#             # Build skill_data dict from POST: skill_<id> = column_id
#             skill_data = {}
#             skills = PrepSubjectSkill.objects.filter(
#                 subject=subject, is_active=True
#             ).filter(
#                 Q(prep_class=card.prep_class) | Q(prep_class__isnull=True)
#             )
#             for skill in skills:
#                 col_val = request.POST.get(f'skill_{skill.pk}', '')
#                 skill_data[skill.pk] = col_val if col_val else None

#             try:
#                 save_subject_skill_entries(
#                     request.user, card, subject, skill_data, subject_comment
#                 )
#                 messages.success(request, f"Scores saved for {subject.name}.")
#             except PermissionDenied as e:
#                 messages.error(request, str(e))

#             return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

#         # --- Save domain ratings ---
#         if action == 'save_domains':
#             if not user_can_edit_domain_ratings(request.user, card):
#                 raise PermissionDenied
#             ratings_data = []
#             for rating in card.domain_ratings.all():
#                 val = request.POST.get(f'domain_{rating.pk}', '')
#                 ratings_data.append({'id': rating.pk, 'rating_text': val})
#             try:
#                 save_domain_ratings(request.user, card, ratings_data)
#                 messages.success(request, "Domain ratings saved.")
#             except PermissionDenied as e:
#                 messages.error(request, str(e))
#             return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

#         # --- Submit card ---
#         if action == 'submit':
#             try:
#                 submit_report_card(request.user, card)
#                 messages.success(request, "Report card submitted for approval.")
#             except (PermissionDenied, ValueError) as e:
#                 messages.error(request, str(e))
#             return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

#         # --- Approve / Publish (admin) ---
#         if action == 'approve':
#             try:
#                 approve_report_card(request.user, card)
#                 messages.success(request, "Report card approved.")
#             except PermissionDenied as e:
#                 messages.error(request, str(e))
#             return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

#         if action == 'publish':
#             try:
#                 publish_report_card(request.user, card)
#                 messages.success(request, "Report card published.")
#             except PermissionDenied as e:
#                 messages.error(request, str(e))
#             return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

#         return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages

# Assuming appropriate internal relative imports for your app architecture
from .models import PrepReportCard, PrepSubjectSkill
from .forms import PrepReportCardCommentForm  # Verify exact comment form import path
from .services import (
    user_can_edit_report,
    user_can_modify_class_metadata,
    user_can_edit_motor_scores,
    user_can_edit_domain_ratings,
    user_can_enter_subject_skills,
    get_teacher_prep_subjects,
    build_report_card_context,
    save_subject_skill_entries,
    submit_report_card,
    approve_report_card,
    publish_report_card
)

class PrepReportCardEditView(LoginRequiredMixin, View):
    template_name = 'prep_reports/report_card_edit.html'

    def get(self, request, report_card_id):
        card = get_object_or_404(
            PrepReportCard.objects.select_related(
                'student__user', 'prep_class__standard', 'period', 'rating_scale'
            ),
            pk=report_card_id
        )
        
        # 1. Global View Authorization Check
        if not user_can_edit_report(request.user, card):
            raise PermissionDenied

        # 2. Extract context configurations tailored to the current user's role
        subjects = get_teacher_prep_subjects(request.user, card.prep_class)
        ctx = build_report_card_context(card)
        
        # Class-level capability tags passed directly down to template layout engine
        can_manage_class = user_can_modify_class_metadata(request.user, card)
        
        ctx['subjects'] = subjects
        ctx['can_edit_domains'] = user_can_edit_motor_scores(request.user, card)
        ctx['can_manage_class'] = can_manage_class  # Use in HTML to hide comment/attendance blocks
        ctx['comment_form'] = PrepReportCardCommentForm(instance=card)
        ctx['is_editable'] = card.status in ('draft', 'submitted')
        
        return render(request, self.template_name, ctx)

    def post(self, request, report_card_id):
        card = get_object_or_404(PrepReportCard, pk=report_card_id)
        
        # Baseline authentication check
        if not user_can_edit_report(request.user, card):
            raise PermissionDenied

        action = request.POST.get('action', 'save')

        # ─── ACTION: SAVE COMMENT & ATTENDANCE ───
        if action == 'save_comment':
            if not user_can_modify_class_metadata(request.user, card):
                raise PermissionDenied  # Stop non-form teachers trying to save comments/attendance
                
            form = PrepReportCardCommentForm(request.POST, instance=card)
            if form.is_valid():
                form.save()
                messages.success(request, "Class records and comments saved successfully.")
            else:
                messages.error(request, "Error saving class records.")
            return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

        # ─── ACTION: SAVE SKILL ENTRIES FOR A SUBJECT ───
        if action == 'save_skills':
            subject_id = request.POST.get('subject_id')
            if not subject_id:
                messages.error(request, "No subject specified.")
                return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

            from curriculum.models import Subject
            subject = get_object_or_404(Subject, pk=subject_id)
            
            # Enforce target object isolation: confirm they can grade *this specific* subject
            if not user_can_enter_subject_skills(request.user, card, subject):
                raise PermissionDenied

            subject_comment = request.POST.get(f'subject_comment_{subject_id}', '')

            # Pull relevant checklist rows securely
            skill_data = {}
            skills = PrepSubjectSkill.objects.filter(
                subject=subject, is_active=True
            ).filter(
                Q(prep_class=card.prep_class) | Q(prep_class__isnull=True)
            )
            for skill in skills:
                col_val = request.POST.get(f'skill_{skill.pk}', '')
                skill_data[skill.pk] = col_val if col_val else None

            try:
                save_subject_skill_entries(
                    request.user, card, subject, skill_data, subject_comment
                )
                messages.success(request, f"Scores saved successfully for {subject.name}.")
            except PermissionDenied as e:
                messages.error(request, str(e))

            return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

        # ─── ACTION: SUBMIT CARD FOR REVIEW ───
        if action == 'submit':
            if not user_can_modify_class_metadata(request.user, card):
                raise PermissionDenied
            try:
                submit_report_card(request.user, card)
                messages.success(request, "Report card submitted for approval.")
            except (PermissionDenied, ValueError) as e:
                messages.error(request, str(e))
            return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

        # ─── ACTION: MANAGEMENT APPROVALS ───
        if action in ('approve', 'publish'):
            # Only superusers or staff can access core administrative functions
            if not (request.user.is_superuser or request.user.is_staff):
                raise PermissionDenied
                
            try:
                if action == 'approve':
                    approve_report_card(request.user, card)
                    messages.success(request, "Report card approved.")
                else:
                    publish_report_card(request.user, card)
                    messages.success(request, "Report card published.")
            except PermissionDenied as e:
                messages.error(request, str(e))
                
            return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

        return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

# ---------------------------------------------------------------------------
# Subject-specific AJAX inline entry (optional enhancement)
# ---------------------------------------------------------------------------

class SubjectSkillAjaxView(LoginRequiredMixin, View):
    """
    Returns HTML snippet for a single subject's skill-entry form.
    Used for tab-based editing without full page reload.
    """
    def get(self, request, report_card_id, subject_id):
        from curriculum.models import Subject
        card = get_object_or_404(PrepReportCard, pk=report_card_id)
        subject = get_object_or_404(Subject, pk=subject_id)

        if not user_can_edit_report(request.user, card):
            return JsonResponse({'error': 'Not authorised'}, status=403)

        skills = PrepSubjectSkill.objects.filter(
            subject=subject, is_active=True
        ).filter(
            Q(prep_class=card.prep_class) | Q(prep_class__isnull=True)
        ).order_by('order')

        entries = {
            e.skill_id: e for e in
            PrepSkillEntry.objects.filter(report_card=card, skill__subject=subject)
        }
        columns = list(card.rating_scale.columns.order_by('order'))
        subject_comment = ''
        if entries:
            first_entry = next(iter(entries.values()))
            subject_comment = first_entry.subject_comment

        return render(request, 'prep_reports/partials/subject_skill_form.html', {
            'card': card,
            'subject': subject,
            'skills': skills,
            'entries': entries,
            'columns': columns,
            'subject_comment': subject_comment,
            'can_edit': card.status in ('draft', 'submitted'),
        })


# ---------------------------------------------------------------------------
# Read-only Report Card Preview (for parents / admin)
# ---------------------------------------------------------------------------

class PrepReportCardPreviewView(LoginRequiredMixin, TemplateView):
    template_name = 'prep_reports/report_card_preview.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        card = get_object_or_404(
            PrepReportCard.objects.select_related(
                'student__user', 'prep_class__standard', 'period',
                'rating_scale', 'promoted_to'
            ),
            pk=self.kwargs['report_card_id']
        )
        # Parents can only see published cards for their own children
        user = self.request.user
        if not (user.is_superuser or user.is_staff or
                user_can_edit_report(user, card)):
            # Check parent relationship
            try:
                if not user.parent_profile.students.filter(
                    pk=card.student.pk
                ).exists():
                    raise PermissionDenied
                if card.status != 'published':
                    raise PermissionDenied(
                        "This report card is not yet published."
                    )
            except AttributeError:
                raise PermissionDenied

        ctx.update(build_report_card_context(card))
        ctx['readonly'] = True
        return ctx


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------

class PrepReportCardPDFView(LoginRequiredMixin, View):
    def get(self, request, report_card_id):
        card = get_object_or_404(
            PrepReportCard.objects.select_related(
                'student__user', 'prep_class__standard', 'period',
                'rating_scale', 'promoted_to'
            ),
            pk=report_card_id
        )
        user = request.user
        if not (user.is_superuser or user.is_staff or
                user_can_edit_report(user, card)):
            raise PermissionDenied

        ctx = build_report_card_context(card)
        ctx['readonly'] = True
        ctx['for_pdf'] = True

        # Use WeasyPrint or xhtml2pdf — WeasyPrint preferred
        try:
            from weasyprint import HTML
            from django.template.loader import render_to_string
            html_string = render_to_string('prep_reports/report_card_pdf.html', ctx)
            pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf_file, content_type='application/pdf')
            filename = (
                f"report_{card.student.user.last_name}_"
                f"{card.period.session}_{card.period.term}.pdf"
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
        except ImportError:
            # Fallback: render HTML for printing
            return render(request, 'prep_reports/report_card_pdf.html', ctx)


# ---------------------------------------------------------------------------
# Admin: Manage Prep Classes
# ---------------------------------------------------------------------------

class PrepClassListView(LoginRequiredMixin, ListView):
    model = PrepClass
    template_name = 'prep_reports/admin/prep_class_list.html'
    context_object_name = 'prep_classes'

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.is_staff):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return PrepClass.objects.select_related('standard').annotate(
            card_count=Count('report_cards')
        )


# ---------------------------------------------------------------------------
# Period selector utility view
# ---------------------------------------------------------------------------

class SelectPeriodView(LoginRequiredMixin, TemplateView):
    template_name = 'prep_reports/select_period.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['prep_classes'] = get_teacher_prep_classes(self.request.user)
        ctx['periods'] = PrepAcademicPeriod.objects.select_related('session', 'term').order_by('-session__start_date', 'term__start_date')
        ctx['current_period'] = PrepAcademicPeriod.get_current()
        return ctx

# New Edit
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

def user_can_edit_report(user, report_card):
    """
    Superusers and is_staff: unrestricted.
    Teacher: must have report card's Standard in standards_assigned.
    """
    if user.is_superuser or user.is_staff:
        return True
    teacher = _get_teacher(user)
    if teacher is None:
        return False
    return teacher.standards_assigned.filter(
        pk=report_card.prep_class.standard_id
    ).exists()


def user_can_edit_motor_scores(user, report_card):
    """
    Only the form teacher of the class (or admin/staff) may enter/edit
    MotorAbilityScores for pupils in this prep class.

    Standard.form_teacher FK → Teacher (related_name='form_class').
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


# Keep old name as an alias so any code that still calls it doesn't break
user_can_edit_domain_ratings = user_can_edit_motor_scores


def user_can_enter_subject_skills(user, report_card, subject):
    """
    Teacher must teach the subject AND be assigned to the class.
    Superusers/staff bypass.
    """
    if user.is_superuser or user.is_staff:
        return True
    teacher = _get_teacher(user)
    if teacher is None:
        return False
    teaches_subject = teacher.subjects_taught.filter(pk=subject.pk).exists()
    assigned_class  = teacher.standards_assigned.filter(
        pk=report_card.prep_class.standard_id
    ).exists()
    return teaches_subject and assigned_class


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
