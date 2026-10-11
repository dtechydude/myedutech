from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import ListView

from . import services
from .models import Notification


def _back(request, default='notices:list'):
    target = request.POST.get('next', '')
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()},
                                                  require_https=request.is_secure()):
        return HttpResponseRedirect(target)
    return redirect(default)


class NotificationListView(LoginRequiredMixin, ListView):
    template_name = 'elearning/notices/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user)
        if self.request.GET.get('filter') == 'unread':
            qs = qs.filter(is_read=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(unread=services.unread_count(self.request.user),
                   only_unread=self.request.GET.get('filter') == 'unread')
        return ctx


class NotificationOpenView(LoginRequiredMixin, View):
    """Marks the notification read, then takes the user to the page it is about."""

    def get(self, request, pk):
        note = get_object_or_404(Notification, pk=pk, recipient=request.user)
        note.mark_read()
        return redirect(services.safe_url(note.url) or 'notices:list')


class MarkReadView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        get_object_or_404(Notification, pk=pk, recipient=request.user).mark_read()
        return _back(request)


class MarkAllReadView(LoginRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request):
        services.mark_all_read(request.user)
        return _back(request)