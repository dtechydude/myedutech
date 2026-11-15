"""
Front-end grading of E-Learning assignment submissions.

NEW, SELF-CONTAINED MODULE: it does not change models.py, views.py, forms.py
or any existing behaviour. It only reads/updates AssignmentSubmission.score,
.teacher_feedback and .graded_by (the same fields the admin edits).

Who can do what
  * superuser / is_staff : every submission, every class and subject.
  * teacher              : only submissions for assignments whose LESSON they
                           created (Lesson.created_by == request.user).
  * anyone else          : 403 (anonymous users are sent to log in).
"""
from django import forms
from django.apps import apps as django_apps
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.views.generic import TemplateView, UpdateView

from .models import Assignment, AssignmentSubmission, ELearningSubject
from .permissions import is_teacher_or_staff

PAGE_SIZE = 25
STATUS_FILTERS = ('all', 'pending', 'graded', 'late')
LATE_Q = Q(assignment__due_date__isnull=False, submitted_at__gt=F('assignment__due_date'))


# ---------------------------------------------------------------- helpers
def _get_standard_model():
    # Same lazy lookup views.py uses: the only link to curriculum.
    return django_apps.get_model('curriculum', 'Standard')


def _to_int(value):
    return int(value) if value and str(value).isdigit() else None


def has_full_access(user):
    return user.is_superuser or user.is_staff


def scoped_assignments(user):
    """Assignments this user may grade."""
    qs = Assignment.objects.all()
    if not has_full_access(user):
        qs = qs.filter(lesson__created_by=user)
    return qs


def scoped_submissions(user):
    """Submissions this user may see and grade (the ONE permission rule)."""
    qs = AssignmentSubmission.objects.select_related(
        'assignment', 'assignment__lesson', 'assignment__lesson__standard',
        'assignment__lesson__subject', 'student', 'graded_by',
    )
    if not has_full_access(user):
        qs = qs.filter(assignment__lesson__created_by=user)
    return qs


def _url(name, **params):
    params = {k: v for k, v in params.items() if v not in (None, '', 'all')}
    base = reverse(name)
    return f'{base}?{urlencode(params)}' if params else base


class GradingAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return has_full_access(user) or is_teacher_or_staff(user)


# ------------------------------------------------------------------- form
class GradeSubmissionForm(forms.ModelForm):
    """Only score + feedback are editable. The model's own clean() rejects a
    score above the assignment's maximum, so that rule stays in one place."""

    class Meta:
        model = AssignmentSubmission
        fields = ['score', 'teacher_feedback']
        widgets = {
            'teacher_feedback': forms.Textarea(attrs={'rows': 5, 'maxlength': 500}),
        }
        labels = {'teacher_feedback': 'Feedback to the student (optional)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['score'].required = True
        attrs = {'min': 0, 'inputmode': 'numeric'}
        max_score = self.instance.assignment.max_score if self.instance.pk else None
        if max_score is not None:
            attrs['max'] = max_score
        self.fields['score'].widget.attrs.update(attrs)


# ------------------------------------------------------------------ views
class SubmissionListView(GradingAccessMixin, TemplateView):
    template_name = 'elearning/submission_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user, GET = self.request.user, self.request.GET
        assignments = scoped_assignments(user)

        # --- filter options (only what this user may grade) ---------------
        standards = (_get_standard_model().objects
                     .filter(pk__in=assignments.values('lesson__standard_id'))
                     .order_by('name'))
        standard_id = _to_int(GET.get('standard'))
        if standard_id and not standards.filter(pk=standard_id).exists():
            standard_id = None

        subjects = (ELearningSubject.objects.select_related('standard')
                    .filter(pk__in=assignments.values('lesson__subject_id')))
        if standard_id:
            subjects = subjects.filter(standard_id=standard_id)
        subjects = subjects.order_by('name')
        subject_id = _to_int(GET.get('subject'))
        if subject_id and not subjects.filter(pk=subject_id).exists():
            subject_id = None

        assignment = None
        assignment_id = _to_int(GET.get('assignment'))
        if assignment_id:
            assignment = assignments.select_related('lesson').filter(pk=assignment_id).first()
            assignment_id = assignment.pk if assignment else None

        status = GET.get('status') if GET.get('status') in STATUS_FILTERS else 'all'

        # --- submissions ---------------------------------------------------
        qs = scoped_submissions(user)
        if standard_id:
            qs = qs.filter(assignment__lesson__standard_id=standard_id)
        if subject_id:
            qs = qs.filter(assignment__lesson__subject_id=subject_id)
        if assignment_id:
            qs = qs.filter(assignment_id=assignment_id)

        counts = qs.aggregate(
            all=Count('id'),
            pending=Count('id', filter=Q(score__isnull=True)),
            graded=Count('id', filter=Q(score__isnull=False)),
            late=Count('id', filter=LATE_Q),
        )
        if status == 'pending':
            qs = qs.filter(score__isnull=True)
        elif status == 'graded':
            qs = qs.filter(score__isnull=False)
        elif status == 'late':
            qs = qs.filter(LATE_Q)
        # Ungraded first, newest first inside each group.
        qs = qs.order_by(F('score').asc(nulls_first=True), '-submitted_at')

        page_obj = Paginator(qs, PAGE_SIZE).get_page(GET.get('page'))

        keep = dict(standard=standard_id, subject=subject_id, assignment=assignment_id)
        labels = (('all', 'All'), ('pending', 'Awaiting grading'),
                  ('graded', 'Graded'), ('late', 'Late'))
        ctx.update(
            full_access=has_full_access(user),
            standards=standards, subjects=subjects,
            standard_id=standard_id, subject_id=subject_id,
            assignment=assignment, status=status,
            tabs=[{'key': k, 'label': lbl, 'count': counts[k], 'active': k == status,
                   'url': _url('elearning:submission_list', status=k, **keep)}
                  for k, lbl in labels],
            submissions=page_obj, page_obj=page_obj,
            qs_nopage=urlencode({k: v for k, v in dict(keep, status=status).items()
                                 if v not in (None, '', 'all')}),
            has_filters=any([standard_id, subject_id, assignment_id, status != 'all']),
            clear_assignment_url=_url('elearning:submission_list', status=status,
                                      standard=standard_id, subject=subject_id),
            current_url=self.request.get_full_path(),
        )
        return ctx


class SubmissionGradeView(GradingAccessMixin, UpdateView):
    form_class = GradeSubmissionForm
    template_name = 'elearning/submission_grade.html'
    context_object_name = 'submission'

    def get_queryset(self):
        # A teacher opening someone else's submission gets a 404.
        return scoped_submissions(self.request.user)

    def _next_url(self):
        nxt = self.request.POST.get('next') or self.request.GET.get('next') or ''
        if nxt and url_has_allowed_host_and_scheme(
                nxt, allowed_hosts={self.request.get_host()},
                require_https=self.request.is_secure()):
            return nxt
        return reverse('elearning:submission_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['next_url'] = self._next_url()
        ctx['lesson'] = self.object.assignment.lesson
        return ctx

    def form_valid(self, form):
        submission = form.save(commit=False)
        submission.graded_by = self.request.user
        submission.save()  # model.save() stamps graded_at; signals still fire
        self.object = submission
        max_score = submission.assignment.max_score
        total = f'/{max_score}' if max_score is not None else ''
        messages.success(self.request, f'Saved: {submission.student} scored {submission.score}{total} '
                                       f'for "{submission.assignment.title}".')
        return redirect(self._next_url())