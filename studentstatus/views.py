from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.functional import cached_property
from django.views.generic import FormView, ListView

from students.models import Student

from . import services
from .constants import (
    ACTIVE, LOGIN_BLOCKED_STATUSES, PROTECTED_STATUSES, STATUS_CHOICES,
    STATUS_LABELS, block_message,
)
from .forms import StatusChangeForm, StudentStatusFilterForm
from .models import StudentStatusLog
from .permissions import is_status_admin


def _client_ip(request):
    # REMOTE_ADDR only: X-Forwarded-For can be spoofed by the client. Behind
    # Nginx, configure real_ip so REMOTE_ADDR carries the visitor's address.
    return request.META.get('REMOTE_ADDR') or None

class StatusAdminMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Superusers and staff only. Anonymous -> login page, other users -> 403."""

    def test_func(self):
        return is_status_admin(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['filter_qs'] = params.urlencode()  # keeps filters on pagination links
        return ctx

class StudentStatusListView(StatusAdminMixin, ListView):
    """Searchable, filterable list of all students with their status."""
    template_name = 'studentstatus/status_list.html'
    context_object_name = 'students'
    paginate_by = 25

    @cached_property
    def filter_form(self):
        return StudentStatusFilterForm(self.request.GET or None)

    def get_queryset(self):
        qs = Student.objects.select_related('current_class').order_by('last_name', 'first_name')
        form = self.filter_form
        if form.is_valid():
            data = form.cleaned_data
            if data['q']:
                q = data['q']
                qs = qs.filter(
                    Q(first_name__icontains=q) | Q(last_name__icontains=q) |
                    Q(middle_name__icontains=q) | Q(USN__icontains=q)
                )
            if data['status']:
                qs = qs.filter(student_status=data['status'])
            if data['standard']:
                qs = qs.filter(current_class=data['standard'])
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        counts = dict(
            Student.objects.order_by().values_list('student_status').annotate(n=Count('pk'))
        )
        selected = self.request.GET.get('status', '')
        ctx['filter_form'] = self.filter_form
        ctx['status_counts'] = [
            {'status': value, 'label': label, 'count': counts.get(value, 0),
             'selected': value == selected}
            for value, label in STATUS_CHOICES
        ]
        ctx['title'] = 'Student Status'
        return ctx


class StudentStatusChangeView(StatusAdminMixin, FormView):
    """Change one student's status, with the full history underneath."""
    template_name = 'studentstatus/status_change.html'
    form_class = StatusChangeForm

    @cached_property
    def student(self):
        return get_object_or_404(
            Student.objects.select_related('current_class'), pk=self.kwargs['pk']
        )

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['student'] = self.student
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        status = self.student.student_status
        ctx.update(
            title='Manage Student Status',
            student=self.student,
            status_label=STATUS_LABELS.get(status, status),
            is_protected=status in PROTECTED_STATUSES,
            is_login_blocked=status in LOGIN_BLOCKED_STATUSES,
            block_message=block_message(status),
            history=StudentStatusLog.objects.filter(student=self.student)
                                            .select_related('changed_by')[:20],
        )
        return ctx

    def form_valid(self, form):
        try:
            log = services.change_student_status(
                student_id=self.student.pk,
                new_status=form.cleaned_data['new_status'],
                changed_by=self.request.user,
                reason=form.cleaned_data['reason'],
                ip_address=_client_ip(self.request),
            )
        except services.StatusChangeError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)

        name = self.student.get_full_name()
        if log.new_status == ACTIVE:
            messages.success(self.request, f"{name} is now Active and can log in again.")
        else:
            messages.success(
                self.request,
                f"{name} is now {log.get_new_status_display()}. "
                "They can no longer log in and any open session has been ended."
            )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('studentstatus:change', kwargs={'pk': self.student.pk})


class StatusLogListView(StatusAdminMixin, ListView):
    """School-wide audit trail of status changes."""
    template_name = 'studentstatus/status_log.html'
    context_object_name = 'logs'
    paginate_by = 30

    def get_queryset(self):
        qs = StudentStatusLog.objects.select_related('student', 'changed_by')
        q = (self.request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(student_name__icontains=q) | Q(student_usn__icontains=q) |
                Q(changed_by_name__icontains=q) | Q(reason__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Status Change Log'
        ctx['q'] = (self.request.GET.get('q') or '').strip()
        return ctx