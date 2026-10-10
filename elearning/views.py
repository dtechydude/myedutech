from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count
from django.db.models import Prefetch, Q
from django.views.generic import (TemplateView, DetailView,
                                   ListView, FormView, CreateView,
                                   UpdateView, DeleteView)
from .models import (
    Lesson, ELearningSubject, save_lesson_files,
    Assignment, AssignmentSubmission, Comment, Reply,
)
# from .forms import CommentForm, LessonForm, ReplyForm, AssignmentForm, AssignmentSubmissionForm
from .forms import (CommentForm, LessonForm, LessonUpdateForm, ReplyForm,
                    AssignmentForm, AssignmentSubmissionForm)
from .permissions import (
    ClassAccessMixin, TeacherRequiredMixin, get_student, is_teacher_or_staff,
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ObjectDoesNotExist

from django.apps import apps as django_apps


def _get_standard_model():
    """
    Lazily fetch curriculum.Standard through Django's app registry
    instead of a top-level import (the one unavoidable link to curriculum).
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


# ---------------------------------------------------------------------
# Access control (✅ hardened): every page below now requires login, and
# a student can only open their OWN class's subjects/lessons. Teachers,
# staff and superusers can open everything. This is what keeps
# "Unlisted" YouTube links and "anyone with the link" Drive files
# effectively private — the links are only ever shown inside the portal.
# ---------------------------------------------------------------------
class SubjectListView(ClassAccessMixin, DetailView):
    context_object_name = 'standards'
    template_name = 'elearning/test_class_subjects.html'

    def get_queryset(self):
        Standard = _get_standard_model()
        return Standard.objects.all()

    def get_standard_id(self, obj):
        return obj.pk


class LessonListView(ClassAccessMixin, DetailView):
    context_object_name = 'subjects'
    model = ELearningSubject
    template_name = 'elearning/test_course_list.html'

    def get_queryset(self):
        # URL carries the class slug too — use it so mismatched URLs 404.
        return (ELearningSubject.objects
                .select_related('standard')
                .prefetch_related('lessons')
                .filter(standard__slug=self.kwargs['standard']))

    def get_standard_id(self, obj):
        return obj.standard_id


class LessonLookupMixin:
    """
    Lesson.slug is not unique (two subjects can both have an
    "Introduction" lesson), so resolve lessons by class + subject + slug
    — all three are already in the URL.
    """

    def get_queryset(self):
        return (Lesson.objects
                .select_related('standard', 'subject', 'created_by')
                .filter(standard__slug=self.kwargs['standard'],
                        subject__slug=self.kwargs['subject']))


class LessonDetailView(ClassAccessMixin, LessonLookupMixin, DetailView, FormView):
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

    def get_standard_id(self, obj):
        return obj.standard_id

    def get_context_data(self, **kwargs):
        context = super(LessonDetailView, self).get_context_data(**kwargs)
        if 'form' not in context:
            context['form'] = self.form_class()
        if 'form2' not in context:
            context['form2'] = self.second_form_class()

        # Optional for templates: comments with authors/replies pre-fetched
        # (avoids one query per comment/reply).
        context['comments'] = (
            self.object.comments
            .select_related('author')
            .prefetch_related(Prefetch('replies', queryset=Reply.objects.select_related('author')))
        )

        # ── Assignments/Homework for this lesson ──────────────────────
        # Each assignment gets `.my_submission` (this student's existing
        # submission, or None) and `.submission_form` (pre-filled).
        assignments = list(self.object.assignments.all())
        student = get_student(self.request.user)

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

        # assignment submission (external link only, no uploads)
        if 'submission_form' in request.POST:
            return self.handle_assignment_submission(request)

        if 'form' in request.POST:
            form = self.get_form(self.get_form_class())
            on_valid = self.form_valid
        else:
            form = self.get_form(self.second_form_class)
            on_valid = self.form2_valid

        if form.is_valid():
            return on_valid(form)

        # ✅ FIX — an invalid comment/reply used to return None (HTTP 500).
        messages.error(request, "Your message could not be posted. Please check it and try again.")
        return HttpResponseRedirect(self.get_success_url())

    def handle_assignment_submission(self, request):
        """
        Records a student's external link (Google Drive, a cPanel-hosted
        file, etc.) as their submission for an Assignment of this lesson.
        """
        raw_id = request.POST.get('assignment_id', '')
        if not raw_id.isdigit():
            raise Http404
        assignment = get_object_or_404(Assignment, id=int(raw_id), lesson=self.object)

        student = get_student(request.user)
        if student is None:
            messages.error(request, "Only students can submit assignments.")
            return HttpResponseRedirect(self.get_success_url())

        existing = AssignmentSubmission.objects.filter(assignment=assignment, student=student).first()

        # ✅ NEW — once the teacher has graded it, the work is locked.
        if existing is not None and existing.is_graded:
            messages.error(request, f"'{assignment.title}' has already been graded and can no longer be changed.")
            return HttpResponseRedirect(self.get_success_url())

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
        standard = self.object.standard
        subject = self.object.subject
        return reverse_lazy('elearning:lesson_detail', kwargs={'standard': standard.slug,
                                                                 'subject': subject.slug,
                                                                 'slug': self.object.slug})

    def form_valid(self, form):
        fm = form.save(commit=False)
        fm.author = self.request.user
        # ✅ FIX — the old `self.object.comments.name` raised AttributeError
        # (`comments` is a related manager, not a model instance).
        fm.lesson_name = self.object
        fm.save()
        return HttpResponseRedirect(self.get_success_url())

    def form2_valid(self, form):
        raw_id = self.request.POST.get('comment.id', '')
        if not raw_id.isdigit():
            raise Http404
        # ✅ the comment must belong to THIS lesson
        comment = get_object_or_404(Comment, pk=int(raw_id), lesson_name=self.object)
        fm = form.save(commit=False)
        fm.author = self.request.user
        fm.comment_name = comment
        fm.save()
        return HttpResponseRedirect(self.get_success_url())


class LessonCreateView(TeacherRequiredMixin, CreateView):
    # ✅ hardened: previously had no view-level permission check at all.
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


class LessonUpdateView(LoginRequiredMixin, UserPassesTestMixin, LessonLookupMixin, UpdateView):
    form_class = LessonUpdateForm  # ✅ same CKEditor-friendly widgets as the create page    model = Lesson
    template_name = 'elearning/test_lesson_update_view.html'
    context_object_name = 'lessons'

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    # preventing other users from update other people's post
    def test_func(self):
        post = self.get_object()
        if self.request.user == post.created_by:
            return True
        return False


class LessonDeleteView(LoginRequiredMixin, UserPassesTestMixin, LessonLookupMixin, DeleteView):
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
# Assignment / Homework CRUD (teacher/staff only) — unchanged
# =====================================================================

def _is_teacher_or_staff(user):
    return is_teacher_or_staff(user)


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
    Unchanged from the original: not wired to any URL, and its student
    branch references a `SubjectOnlineMeeting` model that does not exist.
    Inert — left alone on purpose.
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