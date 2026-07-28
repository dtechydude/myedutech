from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.db.models import Prefetch, Q  # Add Q and Prefetch
from django.views.generic import (TemplateView, DetailView,
                                   ListView, FormView, CreateView,
                                   UpdateView, DeleteView)
from .models import (
    Lesson, ELearningSubject, save_lesson_files,
    Assignment, AssignmentSubmission,
)
from .forms import CommentForm, LessonForm, ReplyForm, AssignmentForm, AssignmentSubmissionForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ObjectDoesNotExist

from django.apps import apps as django_apps


def _get_standard_model():
    """
    Lazily fetch curriculum.Standard through Django's app registry
    instead of a top-level `from curriculum.models import Standard`.
    This is the one unavoidable link to curriculum (a lesson has to
    belong to some class, and classes are owned by curriculum) — kept
    as a runtime lookup rather than an import so this module never
    directly depends on curriculum's code.
    """
    return django_apps.get_model('curriculum', 'Standard')


class StandardSelfListView(LoginRequiredMixin, ListView):
    context_object_name = 'standards'
    template_name = 'elearning/test_my_class.html'

    # Student can only view their class elearning
    def get_queryset(self):
        Standard = _get_standard_model()
        return Standard.objects.filter(name=self.request.user.student.current_class)


# Standard list view for the admin and teachers
class ClassListView(LoginRequiredMixin, ListView):
    context_object_name = 'class'
    template_name = 'elearning/test_elearning_class.html'

    def get_queryset(self):
        Standard = _get_standard_model()
        return Standard.objects.all()


class SubjectListView(DetailView):
    context_object_name = 'standards'
    template_name = 'elearning/test_class_subjects.html'

    def get_queryset(self):
        Standard = _get_standard_model()
        return Standard.objects.all()


class LessonListView(DetailView):
    context_object_name = 'subjects'
    model = ELearningSubject
    template_name = 'elearning/test_course_list.html'


class LessonDetailView(DetailView, FormView):
    context_object_name = 'lessons'
    model = Lesson
    template_name = 'elearning/test_lesson-detail.html'
    # for replies to lessons
    form_class = CommentForm
    second_form_class = ReplyForm
    '''
        send two forms to page
        see which one is posted
        take action on the form which is posted
    '''
    def get_context_data(self, **kwargs):
        context = super(LessonDetailView, self).get_context_data(**kwargs)
        if 'form' not in context:
            context['form'] = self.form_class()
        if 'form2' not in context:
            context['form2'] = self.second_form_class()
        # context['comments] = Comment.objects.filter(id=self.object.id)

        # ── NEW — Assignments/Homework for this lesson ────────────────
        # Each assignment gets `.my_submission` (this student's existing
        # submission, or None) and `.submission_form` (a form pre-filled
        # with that submission, so editing shows what was already sent)
        # attached directly — avoids needing a custom template filter
        # for dict lookups in the template.
        assignments = list(self.object.assignments.all())
        student = getattr(self.request.user, 'student', None)

        if student is not None:
            existing_by_assignment = {
                s.assignment_id: s for s in AssignmentSubmission.objects.filter(
                    assignment__in=assignments, student=student
                )
            }
            for assignment in assignments:
                assignment.my_submission = existing_by_assignment.get(assignment.id)
                assignment.submission_form = AssignmentSubmissionForm(instance=assignment.my_submission)
        else:
            for assignment in assignments:
                assignment.my_submission = None
                assignment.submission_form = None

        context['assignments'] = assignments
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        # ── NEW — assignment submission (external link only, no uploads) ──
        if 'submission_form' in request.POST:
            return self.handle_assignment_submission(request)

        if 'form' in request.POST:
            form_class = self.get_form_class()
            form_name = 'form'
        else:
            form_class = self.second_form_class
            form_name = 'form2'

        form = self.get_form(form_class)

        if form_name == 'form' and form.is_valid():
            print("comment form is returned")
            return self.form_valid(form)
        elif form_name == 'form2' and form.is_valid():
            print("reply form is returned")
            return self.form2_valid(form)

    def handle_assignment_submission(self, request):
        """
        ✅ NEW — Records a student's external link (Google Drive, a
        cPanel-hosted file, etc.) as their submission for a specific
        Assignment tied to this lesson. Nothing is ever uploaded to
        this server; only the link + an optional note are stored.
        """
        assignment_id = request.POST.get('assignment_id')
        assignment = get_object_or_404(Assignment, id=assignment_id, lesson=self.object)

        student = getattr(request.user, 'student', None)
        if student is None:
            messages.error(request, "Only students can submit assignments.")
            return HttpResponseRedirect(self.get_success_url())

        existing = AssignmentSubmission.objects.filter(assignment=assignment, student=student).first()
        form = AssignmentSubmissionForm(request.POST, instance=existing)

        if form.is_valid():
            submission = form.save(commit=False)
            submission.assignment = assignment
            submission.student = student
            submission.save()
            messages.success(request, f"Your submission for '{assignment.title}' has been recorded.")
        else:
            messages.error(request, "Please provide a valid link before submitting.")

        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        self.object = self.get_object()
        standard = self.object.standard
        subject = self.object.subject
        return reverse_lazy('elearning:lesson_detail', kwargs={'standard': standard.slug,
                                                                 'subject': subject.slug,
                                                                 'slug': self.object.slug})

    def form_valid(self, form):
        self.object = self.get_object()
        fm = form.save(commit=False)
        fm.author = self.request.user
        fm.lesson_name = self.object.comments.name
        fm.lesson_name_id = self.object.id
        fm.save()
        return HttpResponseRedirect(self.get_success_url())

    def form2_valid(self, form):
        self.object = self.get_object()
        fm = form.save(commit=False)
        fm.author = self.request.user
        fm.comment_name_id = self.request.POST.get('comment.id')
        fm.save()
        return HttpResponseRedirect(self.get_success_url())


class LessonCreateView(CreateView):
    form_class = LessonForm
    context_object_name = 'subject'
    model = ELearningSubject
    template_name = 'elearning/test_lesson_create.html'

    def get_success_url(self):
        self.object = self.get_object()
        standard = self.object.standard
        return reverse_lazy('elearning:lesson_list', kwargs={'standard': standard.slug, 'slug': self.object.slug})

    def form_valid(self, form, *args, **kwargs):
        self.object = self.get_object()
        fm = form.save(commit=False)
        fm.created_by = self.request.user
        fm.standard = self.object.standard
        fm.subject = self.object
        fm.save()
        return HttpResponseRedirect(self.get_success_url())


class LessonUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    fields = ('name', 'position', 'video', 'comment')
    model = Lesson
    template_name = 'elearning/test_lesson_update_view.html'
    context_object_name = 'lessons'

    # function to check if user is the login user
    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    # preventing other users from update other people's post
    def test_func(self):
        post = self.get_object()
        if self.request.user == post.created_by:
            return True
        return False


class LessonDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Lesson
    context_object_name = 'lessons'
    template_name = 'elearning/test_lesson_delete.html'

    def get_success_url(self):
        standard = self.object.standard
        subject = self.object.subject
        return reverse_lazy('elearning:lesson_list', kwargs={'standard': standard.slug, 'slug': subject.slug})

    # preventing other users from update other people's post
    def test_func(self):
        post = self.get_object()
        if self.request.user == post.created_by:
            return True
        return False


# =====================================================================
# ✅ NEW — Assignment / Homework CRUD (teacher/staff only)
# ---------------------------------------------------------------------
# Mirrors the existing Lesson CRUD pattern above for consistency. Unlike
# the pre-existing LessonCreateView (which has no view-level access
# check — access is only hidden at the template level), these new views
# DO enforce access control at the view level via UserPassesTestMixin,
# since there's no existing behavior here to preserve and it costs
# nothing to do it properly for new code.
# =====================================================================

def _is_teacher_or_staff(user):
    return bool(user.is_authenticated and (user.is_superuser or user.is_staff or hasattr(user, 'teacher')))


class AssignmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Assignment
    form_class = AssignmentForm
    template_name = 'elearning/assignment_create.html'

    def test_func(self):
        return _is_teacher_or_staff(self.request.user)

    def dispatch(self, request, *args, **kwargs):
        self.lesson = get_object_or_404(
            Lesson,
            slug=kwargs.get('lesson_slug'),
            standard__slug=kwargs.get('standard'),
            subject__slug=kwargs.get('subject'),
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lesson'] = self.lesson
        return context

    def form_valid(self, form):
        form.instance.lesson = self.lesson
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('elearning:lesson_detail', kwargs={
            'standard': self.lesson.standard.slug,
            'subject': self.lesson.subject.slug,
            'slug': self.lesson.slug,
        })


class AssignmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Assignment
    form_class = AssignmentForm
    template_name = 'elearning/assignment_create.html'
    context_object_name = 'assignment'

    def test_func(self):
        return _is_teacher_or_staff(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['lesson'] = self.object.lesson
        return context

    def get_success_url(self):
        lesson = self.object.lesson
        return reverse('elearning:lesson_detail', kwargs={
            'standard': lesson.standard.slug,
            'subject': lesson.subject.slug,
            'slug': lesson.slug,
        })


class AssignmentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Assignment
    context_object_name = 'assignment'
    template_name = 'elearning/assignment_confirm_delete.html'

    def test_func(self):
        return _is_teacher_or_staff(self.request.user)

    def get_success_url(self):
        lesson = self.object.lesson
        return reverse('elearning:lesson_detail', kwargs={
            'standard': lesson.standard.slug,
            'subject': lesson.subject.slug,
            'slug': lesson.slug,
        })


@login_required
def class_meeting_list_view(request):
    """
    NOTE: Moved into elearning unchanged, exactly as it existed in
    curriculum/views.py. This view is not currently wired to any URL
    (there was no `path(...)` for it in the original urls.py either),
    and its student-facing branch references a `SubjectOnlineMeeting`
    model that does not exist anywhere in the codebase. It is inert —
    kept only for continuity, not fixed, since that wasn't part of this
    refactor's scope.
    """
    user = request.user
    context = {'subjects_with_meetings': []}

    # --- Staff / Superuser ---
    if user.is_superuser or user.is_staff:
        context['is_staff_view'] = True
        return render(request, 'elearning/class_meeting_list.html', context)

    # --- Student branch ---
    try:
        student = user.student  # works if OneToOneField
    except ObjectDoesNotExist:
        student = None

    if student and student.current_class:
        student_class = student.current_class
        context['student_class_name'] = student_class.name

        subjects = (
            ELearningSubject.objects.filter(standard=student_class)
            .prefetch_related(
                Prefetch(
                    'online_meetings',
                    queryset=SubjectOnlineMeeting.objects.filter(is_active=True),  # noqa: F821 — pre-existing, undefined
                    to_attr='active_meetings'
                )
            )
            .order_by('name')
        )

        for subject in subjects:
            if subject.active_meetings:
                context['subjects_with_meetings'].append({
                    'subject_name': subject.name,
                    'meetings': subject.active_meetings,
                })

        return render(request, 'elearning/class_meeting_list.html', context)

    # --- Fallback ---
    return redirect(reverse('pages:portal-home'))
