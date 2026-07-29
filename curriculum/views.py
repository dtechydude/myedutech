from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from .models import Standard, ClassGroup
from students.models import Student


from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models import Prefetch, Q # Add Q and Prefetch
from django.views.generic import(TemplateView, DetailView,
                                ListView, FormView, CreateView, 
                                UpdateView, DeleteView)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


# =====================================================================
# ✅ E-LEARNING VIEWS MOVED OUT — now in the independent `elearning` app
# ---------------------------------------------------------------------
# StandardSelfListView, ClassListView, SubjectListView, LessonListView,
# LessonDetailView, LessonCreateView, LessonUpdateView, LessonDeleteView,
# and class_meeting_list_view now live in the standalone `elearning` app
# — see elearning/views.py. There is intentionally NO re-export here:
# elearning is fully independent, so curriculum has no knowledge of it.
#
# If anything elsewhere in your project still does
# `from curriculum.views import LessonDetailView` (etc.), update it to
# `from elearning.views import ...` — see the README for a grep command
# to find every call site.
# =====================================================================


@login_required
def class_list(request):
    total_class = (Student.objects .values('current_class') .annotate(count=Count('id')).order_by('current_class'))
    total_gender = Student.objects.filter().order_by('gender').values('gender').annotate(count=Count('gender'))

    context = {
            'total_class': total_class,
            'total_gender': total_gender,

    }
    return render(request, 'curriculum/classes_list.html', context)


#Displays all teachers
@login_required
def classgroup_form_teachers_list(request):
    all_teachers = ClassGroup.objects.all()   

    context = {
        'all_teachers': all_teachers
    }
    return render(request, 'curriculum/classgroup_form_teachers_list.html', context)


#Displays all teachers
@login_required
def form_teachers_head_list(request):
    all_teachers = Standard.objects.all()   

    context = {
        'all_teachers': all_teachers
    }
    return render(request, 'curriculum/form_teachers_head_list.html', context)

# Standard list view for the admin and teachers
class ClassListView(LoginRequiredMixin, ListView):
    context_object_name = 'class'
    model = Standard
    # template_name = 'curriculum/class_list.html'
    template_name = 'curriculum/test_elearning_class.html'
    