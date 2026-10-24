from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from .models import Teacher
from .teacher_status import deactivate_teacher, deactivation_warnings, reactivate_teacher


class SchoolAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Superusers and staff (is_staff) only."""

    def test_func(self):
        user = self.request.user
        return user.is_staff or user.is_superuser


class TeacherDeactivateForm(forms.Form):
    date_left = forms.DateField(
        label='Date left', widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    reason = forms.CharField(
        label='Reason', max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'list': 'leave-reasons',
                                      'placeholder': 'e.g. Resigned'}))

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher = teacher
        self.fields['date_left'].initial = timezone.localdate()

    def clean_date_left(self):
        value = self.cleaned_data['date_left']
        if value > timezone.localdate():
            raise ValidationError('The date left cannot be in the future.')
        employed = getattr(self.teacher, 'date_employed', None)
        if employed and value < employed:
            raise ValidationError('The date left cannot be before the date employed.')
        return value


class TeacherArchiveView(SchoolAdminRequiredMixin, ListView):
    """Everyone who has worked at the school: former teachers by default, or current / all."""
    template_name = 'staff/teacher_archive.html'
    context_object_name = 'teachers'
    paginate_by = 25

    def get_queryset(self):
        qs = Teacher.objects.select_related('user', 'dept', 'staff_role')
        self.show = self.request.GET.get('show', 'former')
        if self.show == 'current':
            qs = qs.current().order_by('last_name', 'first_name')
        elif self.show == 'all':
            qs = qs.order_by('-active', 'last_name', 'first_name')
        else:
            self.show = 'former'
            qs = qs.former().order_by('-date_left', 'last_name')
        self.q = self.request.GET.get('q', '').strip()
        if self.q:
            qs = qs.filter(
                Q(first_name__icontains=self.q) | Q(last_name__icontains=self.q)
                | Q(user__username__icontains=self.q) | Q(user__first_name__icontains=self.q)
                | Q(user__last_name__icontains=self.q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx.update(show=self.show, q=self.q, querystring=params.urlencode(),
                   current_count=Teacher.objects.current().count(),
                   former_count=Teacher.objects.former().count())
        return ctx


class TeacherStatusMixin(SchoolAdminRequiredMixin):
    @cached_property
    def teacher(self):
        return get_object_or_404(Teacher.objects.select_related('user'), pk=self.kwargs['pk'])

    def blocked(self, must_be_active):
        """A redirect when the request makes no sense (own account / wrong current state), else None."""
        if self.teacher.user_id and self.teacher.user_id == self.request.user.id:
            messages.error(self.request, 'You cannot change the status of your own account.')
            return redirect('staff:teacher_archive')
        if must_be_active and not self.teacher.active:
            messages.info(self.request, f'{self.teacher.display_name} is already marked as having left.')
            return redirect('staff:teacher_archive')
        if not must_be_active and self.teacher.active:
            messages.info(self.request, f'{self.teacher.display_name} is already active.')
            return redirect('staff:teacher_archive')
        return None


class TeacherDeactivateView(TeacherStatusMixin, FormView):
    template_name = 'staff/teacher_status_form.html'
    form_class = TeacherDeactivateForm

    def get(self, request, *args, **kwargs):
        return self.blocked(True) or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.blocked(True) or super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['teacher'] = self.teacher
        return kwargs

    def get_context_data(self, **kwargs):
        return super().get_context_data(teacher=self.teacher, mode='deactivate',
                                        warnings=deactivation_warnings(self.teacher), **kwargs)

    def form_valid(self, form):
        deactivate_teacher(self.teacher, by=self.request.user, reason=form.cleaned_data['reason'],
                           date_left=form.cleaned_data['date_left'])
        messages.success(self.request, f'{self.teacher.display_name} is now marked as having left the school. '
                                       'Their portal access has been switched off.')
        return redirect(reverse('staff:teacher_archive'))


class TeacherReactivateView(TeacherStatusMixin, TemplateView):
    template_name = 'staff/teacher_status_form.html'

    def get(self, request, *args, **kwargs):
        return self.blocked(False) or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        denied = self.blocked(False)
        if denied:
            return denied
        reactivate_teacher(self.teacher, by=request.user)
        messages.success(request, f'{self.teacher.display_name} is active again. Their portal access is back on.')
        return redirect(reverse('staff:teacher_archive') + '?show=current')

    def get_context_data(self, **kwargs):
        return super().get_context_data(teacher=self.teacher, mode='reactivate', **kwargs)