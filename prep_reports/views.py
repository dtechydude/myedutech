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

class PrepReportCardEditView(LoginRequiredMixin, View):
    template_name = 'prep_reports/report_card_edit.html'

    def _get_objects(self, report_card_id):
        return get_object_or_404(
            PrepReportCard.select_related(
                'student__user', 'prep_class__standard',
                'period', 'rating_scale'
            ) if hasattr(PrepReportCard, 'select_related')
            else PrepReportCard.objects.select_related(
                'student__user', 'prep_class__standard',
                'period', 'rating_scale'
            ),
            pk=report_card_id
        )

    def get(self, request, report_card_id):
        card = get_object_or_404(
            PrepReportCard.objects.select_related(
                'student__user', 'prep_class__standard', 'period', 'rating_scale'
            ),
            pk=report_card_id
        )
        if not user_can_edit_report(request.user, card):
            raise PermissionDenied

        subjects = get_teacher_prep_subjects(request.user, card.prep_class)
        ctx = build_report_card_context(card)
        ctx['subjects'] = subjects
        ctx['can_edit_domains'] = user_can_edit_domain_ratings(request.user, card)
        ctx['comment_form'] = PrepReportCardCommentForm(instance=card)
        ctx['is_editable'] = card.status in ('draft', 'submitted')
        return render(request, self.template_name, ctx)

    def post(self, request, report_card_id):
        card = get_object_or_404(PrepReportCard, pk=report_card_id)
        if not user_can_edit_report(request.user, card):
            raise PermissionDenied

        action = request.POST.get('action', 'save')

        # --- Save teacher comment ---
        if action == 'save_comment':
            form = PrepReportCardCommentForm(request.POST, instance=card)
            if form.is_valid():
                form.save()
                messages.success(request, "Comments saved successfully.")
            else:
                messages.error(request, "Error saving comments.")
            return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

        # --- Save skill entries for a subject ---
        if action == 'save_skills':
            subject_id = request.POST.get('subject_id')
            if not subject_id:
                messages.error(request, "No subject specified.")
                return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

            from curriculum.models import Subject
            subject = get_object_or_404(Subject, pk=subject_id)
            subject_comment = request.POST.get(f'subject_comment_{subject_id}', '')

            # Build skill_data dict from POST: skill_<id> = column_id
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
                messages.success(request, f"Scores saved for {subject.name}.")
            except PermissionDenied as e:
                messages.error(request, str(e))

            return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

        # --- Save domain ratings ---
        if action == 'save_domains':
            if not user_can_edit_domain_ratings(request.user, card):
                raise PermissionDenied
            ratings_data = []
            for rating in card.domain_ratings.all():
                val = request.POST.get(f'domain_{rating.pk}', '')
                ratings_data.append({'id': rating.pk, 'rating_text': val})
            try:
                save_domain_ratings(request.user, card, ratings_data)
                messages.success(request, "Domain ratings saved.")
            except PermissionDenied as e:
                messages.error(request, str(e))
            return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

        # --- Submit card ---
        if action == 'submit':
            try:
                submit_report_card(request.user, card)
                messages.success(request, "Report card submitted for approval.")
            except (PermissionDenied, ValueError) as e:
                messages.error(request, str(e))
            return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

        # --- Approve / Publish (admin) ---
        if action == 'approve':
            try:
                approve_report_card(request.user, card)
                messages.success(request, "Report card approved.")
            except PermissionDenied as e:
                messages.error(request, str(e))
            return redirect('prep_reports:report_card_edit', report_card_id=card.pk)

        if action == 'publish':
            try:
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
