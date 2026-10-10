from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from . import services
from .forms import NoteFilterForm, NoteForm, ReviewForm, SummaryFilterForm
from .models import LessonNote
from .permissions import AuthorRequiredMixin, ReviewerRequiredMixin, is_author, is_reviewer


class NotesContextMixin:
    """Context every lesson-notes page needs (navigation + optional school settings)."""
    nav_active = ''

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx.update(
            nav_active=self.nav_active,
            ln_is_reviewer=is_reviewer(user),
            ln_is_author=is_author(user),
            ln_folder_url=getattr(settings, 'LESSONNOTES_SHARED_FOLDER_URL', ''),
            ln_reviewer_email=getattr(settings, 'LESSONNOTES_REVIEWER_EMAIL', ''),
        )
        return ctx


class HomeRedirectView(LoginRequiredMixin, View):
    def get(self, request):
        if is_reviewer(request.user):
            return redirect('lessonnotes:all')
        if is_author(request.user):
            return redirect('lessonnotes:mine')
        raise PermissionDenied


# ------------------------------------------------------------------ lists
class NoteListBase(NotesContextMixin, ListView):
    template_name = 'elearning/lessonnotes/note_list.html'
    context_object_name = 'notes'
    paginate_by = getattr(settings, 'LESSONNOTES_PAGE_SIZE', 20)
    mode = 'all'
    show_teacher_filter = False
    scoped_teacher = None

    def base_queryset(self):
        raise NotImplementedError

    def get_queryset(self):
        qs = self.base_queryset().select_related('teacher', 'standard', 'reviewed_by')
        self.filter_form = NoteFilterForm(self.request.GET or None,
                                          show_teacher=self.show_teacher_filter)
        if self.filter_form.is_valid():
            qs = services.filter_notes(qs, self.filter_form.cleaned_data)
        self.scoped_qs = qs
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx.update(filter_form=self.filter_form, stats=services.status_counts(self.scoped_qs),
                   querystring=params.urlencode(), mode=self.mode,
                   scoped_teacher=self.scoped_teacher)
        return ctx


class MyNotesView(AuthorRequiredMixin, NoteListBase):
    nav_active = 'mine'
    mode = 'mine'

    def base_queryset(self):
        return LessonNote.objects.filter(teacher=self.request.user)


class AllNotesView(ReviewerRequiredMixin, NoteListBase):
    """Every teacher's notes — or one teacher's, when reached from the Teachers page."""
    nav_active = 'all'

    def base_queryset(self):
        teacher_id = self.kwargs.get('teacher_id')
        if teacher_id:
            self.scoped_teacher = get_object_or_404(get_user_model(), pk=teacher_id)
            self.nav_active = 'teachers'
            return LessonNote.objects.filter(teacher=self.scoped_teacher)
        self.show_teacher_filter = True
        return LessonNote.objects.all()


class TeacherSummaryView(ReviewerRequiredMixin, NotesContextMixin, ListView):
    template_name = 'elearning/lessonnotes/teacher_summary.html'
    context_object_name = 'teachers'
    paginate_by = 50
    nav_active = 'teachers'

    def get_queryset(self):
        self.filter_form = SummaryFilterForm(self.request.GET or None)
        data = self.filter_form.cleaned_data if self.filter_form.is_valid() else {}
        return services.teacher_summary(data.get('session', ''), data.get('term', ''))

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx.update(filter_form=self.filter_form, querystring=params.urlencode())
        return ctx


class ExportView(ReviewerRequiredMixin, View):
    def get(self, request):
        form = NoteFilterForm(request.GET or None, show_teacher=True)
        qs = LessonNote.objects.all()
        if form.is_valid():
            qs = services.filter_notes(qs, form.cleaned_data)
        response = HttpResponse(services.notes_csv_bytes(qs), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="lesson_notes_{timezone.localdate():%Y%m%d}.csv"')
        return response


# ----------------------------------------------------------------- detail
class NoteDetailView(LoginRequiredMixin, NotesContextMixin, DetailView):
    context_object_name = 'note'
    template_name = 'elearning/lessonnotes/note_detail.html'

    def get_queryset(self):
        return LessonNote.objects.select_related('teacher', 'standard', 'reviewed_by')

    def get_object(self, queryset=None):
        note = super().get_object(queryset)
        user = self.request.user
        if not (is_reviewer(user) or note.teacher_id == user.id):
            raise PermissionDenied
        return note

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        note, user = self.object, self.request.user
        is_owner = note.teacher_id == user.id
        ctx.update(
            events=note.events.select_related('actor'),
            review_form=ReviewForm(),
            can_edit=is_owner and not note.is_locked,
            can_delete=is_owner and not note.is_locked,
            can_review=is_reviewer(user) and (not is_owner or user.is_superuser),
        )
        return ctx


class NoteReviewView(ReviewerRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        note = get_object_or_404(LessonNote, pk=pk)
        form = ReviewForm(request.POST)
        if not form.is_valid():
            for errors in form.errors.values():
                for error in errors:
                    messages.error(request, error)
            return redirect(note)
        try:
            services.review_note(note, request.user,
                                 form.cleaned_data['decision'], form.cleaned_data['remark'])
        except PermissionDenied as exc:
            messages.error(request, str(exc) or 'You are not allowed to review this note.')
        except ValidationError as exc:
            messages.error(request, ' '.join(exc.messages))
        else:
            if form.cleaned_data['decision'] == 'approve':
                messages.success(request, 'Lesson note approved.')
            else:
                messages.warning(request, 'Changes requested — the teacher will see your remark.')
        return redirect(note)


# ------------------------------------------------------- teacher: create/edit
class NoteFormMixin(NotesContextMixin):
    form_class = NoteForm
    template_name = 'elearning/lessonnotes/note_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs


class NoteCreateView(AuthorRequiredMixin, NoteFormMixin, CreateView):
    nav_active = 'submit'

    def get_initial(self):
        initial = super().get_initial()
        last = LessonNote.objects.filter(teacher=self.request.user).order_by('-submitted_at').first()
        if last:  # saves retyping the session and term every week
            initial.update(academic_session=last.academic_session, term=last.term)
        return initial

    def form_valid(self, form):
        self.object = services.create_note(form.save(commit=False), self.request.user)
        messages.success(self.request, 'Lesson note submitted for review.')
        return redirect(self.object)

    def get_context_data(self, **kwargs):
        return super().get_context_data(mode='create', **kwargs)


class NoteUpdateView(AuthorRequiredMixin, NoteFormMixin, UpdateView):
    nav_active = 'mine'
    context_object_name = 'note'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            note = LessonNote.objects.filter(pk=kwargs.get('pk'), teacher=request.user).first()
            if note and note.is_locked:
                messages.warning(request, 'Approved lesson notes are locked. Ask the school to '
                                          'request changes if you need to edit it.')
                return redirect(note)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return LessonNote.objects.filter(teacher=self.request.user)

    def form_valid(self, form):
        was_revision = form.instance.status == LessonNote.Status.REVISION
        self.object = services.update_note(form.save(commit=False), self.request.user)
        messages.success(self.request, 'Re-submitted for review.' if was_revision
                         else 'Lesson note updated.')
        return redirect(self.object)

    def get_context_data(self, **kwargs):
        return super().get_context_data(mode='update', **kwargs)


class NoteDeleteView(AuthorRequiredMixin, NotesContextMixin, DeleteView):
    nav_active = 'mine'
    context_object_name = 'note'
    template_name = 'elearning/lessonnotes/note_confirm_delete.html'
    success_url = reverse_lazy('lessonnotes:mine')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            note = LessonNote.objects.filter(pk=kwargs.get('pk'), teacher=request.user).first()
            if note and note.is_locked:
                messages.warning(request, 'Approved lesson notes cannot be deleted.')
                return redirect(note)
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return LessonNote.objects.filter(teacher=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Lesson note deleted.')
        return super().form_valid(form)