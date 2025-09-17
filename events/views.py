from django.shortcuts import render, get_object_or_404, redirect
from django.views import generic
from django.utils.safestring import mark_safe
from datetime import datetime, timedelta
from django.urls import reverse_lazy

import calendar
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic.detail import DetailView
from django.views.generic import TemplateView



from .models import Event
from .utils import Calendar
from .forms import EventForm

class CalendarView(LoginRequiredMixin, generic.ListView):
    model = Event
    template_name = 'events/calendar.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        d = self.get_date(self.request.GET.get('month', None))
        cal = Calendar(d.year, d.month)
        html_cal = cal.formatmonth(with_year=True)
        
        context['calendar'] = mark_safe(html_cal)
        context['prev_month'] = self.prev_month(d)
        context['next_month'] = self.next_month(d)
        return context

    def get_queryset(self):
        """Filters events based on the user's role."""
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.groups.filter(name='Admin').exists():
            # Admins can see all events
            return queryset
        elif user.groups.filter(name='Teacher').exists():
            # Teachers can see all, teacher-only, and student-only events
            return queryset.filter(visibility__in=['all', 'teacher', 'student'])
        else:
            # Students can only see all or student-only events
            return queryset.filter(visibility__in=['all', 'student'])

    # def get_date(self, req_month):
    #     if req_month:
    #         return datetime.strptime(req_month, '%Y-%m')
    #     return datetime.today()
    
    def get_date(self, req_month):
        try:
            return datetime.strptime(req_month, '%Y-%m')
        except (TypeError, ValueError):
            return datetime.today()

    def prev_month(self, d):
        first = d.replace(day=1)
        prev_month = first - timedelta(days=1)
        month = 'month=' + str(prev_month.year) + '-' + str(prev_month.month)
        return month

    def next_month(self, d):
        days_in_month = calendar.monthrange(d.year, d.month)[1]
        last = d.replace(day=days_in_month)
        next_month = last + timedelta(days=1)
        month = 'month=' + str(next_month.year) + '-' + str(next_month.month)
        return month

class EventFormView(LoginRequiredMixin, generic.edit.FormView):
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = '/events/'

    def form_valid(self, form):
        event = form.save(commit=False)
        event.organizer = self.request.user
        event.save()
        return super().form_valid(form)

class EventUpdateView(LoginRequiredMixin, generic.edit.UpdateView):
    model = Event
    form_class = EventForm
    template_name = 'events/event_form.html'
    success_url = '/events/'

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.groups.filter(name='Admin').exists():
            return queryset
        return queryset.filter(organizer=user)

# class EventDeleteView(LoginRequiredMixin, generic.edit.DeleteView):
#     model = Event
#     template_name = 'events/event_confirm_delete.html'
#     success_url = '/events/'

#     def get_queryset(self):
#         queryset = super().get_queryset()
#         user = self.request.user
#         if user.is_superuser or user.groups.filter(name='Admin').exists():
#             return queryset
#         return queryset.filter(organizer=user)

class EventDeleteView(LoginRequiredMixin, generic.edit.DeleteView):
    model = Event
    template_name = 'events/event_confirm_delete.html'
    success_url = reverse_lazy('events:event_delete_success')  # Change this line

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return queryset
        return queryset.filter(organizer=user)
    

class EventDetailView(LoginRequiredMixin, DetailView):
    """
    Displays the details of a single event.
    """
    model = Event
    template_name = 'events/event_detail.html'
    context_object_name = 'event'

    def get_queryset(self):
        """
        Filters events based on the user's role to ensure they can view the event.
        """
        queryset = super().get_queryset()
        user = self.request.user
        
        # If the user is an admin or superuser, they can see all events
        if user.is_superuser or user.groups.filter(name='Admin').exists():
            return queryset
        
        # If the user is a teacher, they can see events visible to teachers and students
        if user.groups.filter(name='Teacher').exists():
            return queryset.filter(visibility__in=['all', 'teacher', 'student'])
        
        # If the user is a student, they can only see events visible to students
        return queryset.filter(visibility__in=['all', 'student'])

class EventDeleteSuccessView(LoginRequiredMixin, TemplateView):
    template_name = 'events/event_delete_success.html'