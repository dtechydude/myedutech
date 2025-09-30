from django.http import HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse_lazy, reverse
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models import Prefetch, Q # Add Q and Prefetch
from django.views.generic import(TemplateView, DetailView,
                                ListView, FormView, CreateView, 
                                UpdateView, DeleteView)
from .models import Lesson, Standard, ELearningSubject, ClassGroup, save_lesson_files
from .forms import CommentForm, LessonForm, ReplyForm
from django.urls import reverse_lazy
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from students.models import Student
from django.core.exceptions import ObjectDoesNotExist



class StandardSelfListView(LoginRequiredMixin, ListView):
    context_object_name = 'standards'
    model = Standard
    # template_name = 'curriculum/class_list.html'
    template_name = 'curriculum/test_my_class.html'
 
    # Student can only view their class elearning
    def get_queryset(self):
        return Standard.objects.filter(name = self.request.user.student.current_class)

# Standard list view for the admin and teachers
class ClassListView(LoginRequiredMixin, ListView):
    context_object_name = 'class'
    model = Standard
    # template_name = 'curriculum/class_list.html'
    template_name = 'curriculum/test_elearning_class.html'
    

    
class SubjectListView(DetailView):
    context_object_name = 'standards'
    model = Standard
    template_name = 'curriculum/test_class_subjects.html'


class LessonListView(DetailView):
    context_object_name = 'subjects'
    model = ELearningSubject
    template_name = 'curriculum/test_course_list.html'


class LessonDetailView(DetailView, FormView):
    context_object_name = 'lessons'
    model = Lesson
    template_name = 'curriculum/test_lesson-detail.html'
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
        return context


    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if 'form' in request.POST:
            form_class = self.get_form_class()
            form_name = 'form'
        else:
            form_class = self.second_form_class
            form_name = 'form2'

        form = self.get_form(form_class)

        if form_name=='form' and form.is_valid():
            print("comment form is returned")
            return self.form_valid(form)
        elif form_name=='form2' and form.is_valid():
            print("reply form is returned")
            return self.form2_valid(form)

    def get_success_url(self):
        self.object = self.get_object()
        standard = self.object.standard
        subject = self.object.subject
        return reverse_lazy('curriculum:lesson_detail', kwargs={'standard':standard.slug,
                                                            'subject':subject.slug,
                                                            'slug':self.object.slug})

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
        fm. comment_name_id = self.request.POST.get('comment.id')
        fm.save()
        return HttpResponseRedirect(self.get_success_url())
            



class LessonCreateView(CreateView):
    form_class = LessonForm
    context_object_name = 'subject'
    model = ELearningSubject
    template_name = 'curriculum/test_lesson_create.html'

    def get_success_url(self):
        self.object = self.get_object()
        standard = self.object.standard
        return reverse_lazy('curriculum:lesson_list',kwargs={'standard':standard.slug, 'slug':self.object.slug})

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
    template_name = 'curriculum/test_lesson_update_view.html'
    context_object_name = 'lessons'
    
    #function to check if user is the login user
    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    #preventing other users from update other people's post
    def test_func(self):
        post = self.get_object()
        if self.request.user == post.created_by:
            return True
        return False


class LessonDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Lesson
    context_object_name = 'lessons'
    template_name = 'curriculum/test_lesson_delete.html'

    def get_success_url(self):
        standard = self.object.standard
        subject = self.object.subject
        return reverse_lazy('curriculum:lesson_list', kwargs={'standard':standard.slug, 'slug':subject.slug})

#preventing other users from update other people's post
    def test_func(self):
        post = self.get_object()
        if self.request.user == post.created_by:
            return True
        return False


@login_required
def class_list(request):
    total_class = Student.objects.filter().order_by('section').values('class_id__id').annotate(count=Count('class_id__id'))
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


   

# online class integration
# @login_required
# def e_learning_home(request):
#     user = request.user
#     context = {}
    
#     if hasattr(user, 'student') and user.student.current_class:
#         # 1. Get the student's current class
#         student_class = user.student.current_class
        
#         # 2. Fetch all active online links for that specific class
#         platforms = OnlineClassPlatform.objects.filter(
#             current_class=student_class,
#             is_active=True
#         ).order_by('platform')

#         context['student_class_name'] = student_class.name
#         context['platforms'] = platforms
    
#     elif user.is_staff or user.is_teacher:
#         # Optional: Staff/Teachers see all active links for management
#         platforms = OnlineClassPlatform.objects.filter(is_active=True).order_by('current_class__name')
#         context['platforms'] = platforms
#         context['is_staff_view'] = True
        
#     else:
#         # User is logged in but not a student with a class or staff
#         context['platforms'] = []

#     return render(request, 'e_learning/e_learning_page.html', context)


# @login_required
# def class_meeting_list_view(request):
#     user = request.user
#     context = {'subjects_with_meetings': []}
    
#     # ------------------------------------------------------------
#     # A) CHECK FOR STAFF / TEACHER ACCESS (View Admin Message)
#     # ------------------------------------------------------------
#     is_teacher = getattr(user, 'is_teacher', False)

#     if user.is_staff or is_teacher:
#         context['is_staff_view'] = True
#         return render(request, 'curriculum/class_meeting_list.html', context)

#     # ------------------------------------------------------------
#     # B) STUDENT LOGIC
#     # ------------------------------------------------------------
#     is_fully_assigned_student = (
#         hasattr(user, 'student') and user.student and user.student.current_class
#     )
    
#     if is_fully_assigned_student:
#         # --- EXECUTE NORMAL STUDENT FLOW ---
#         student_class = user.student.current_class
#         context['student_class_name'] = student_class.name
        
#         # ... (rest of your successful student logic remains the same)
#         subjects = ELearningSubject.objects.filter(
#             standard=student_class
#         ).prefetch_related(
#             Prefetch(
#                 'online_meetings',
#                 queryset=SubjectOnlineMeeting.objects.filter(is_active=True),
#                 to_attr='active_meetings'
#             )
#         ).order_by('name')

#         for subject in subjects:
#             if subject.active_meetings:
#                 context['subjects_with_meetings'].append({
#                     'subject_name': subject.name,
#                     'meetings': subject.active_meetings,
#                 })
        
#         return render(request, 'curriculum/class_meeting_list.html', context)
    
#     # ------------------------------------------------------------
#     # C) FALLBACK: LOGGED-IN USER IS NOT STAFF, NOT TEACHER, AND NOT A FULLY ASSIGNED STUDENT
#     # ------------------------------------------------------------
    
#     # Instead of rendering a potentially confusing empty template, redirect to home.
#     # Replace 'home' with the actual name of your home/dashboard URL
#     return redirect(reverse('pages:portal-home')) # <--- THIS IS THE CRITICAL CHANGE


@login_required
def class_meeting_list_view(request):
    user = request.user
    context = {'subjects_with_meetings': []}

    # --- Staff / Superuser ---
    if user.is_superuser or user.is_staff:
        context['is_staff_view'] = True
        return render(request, 'curriculum/class_meeting_list.html', context)

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
                    queryset=SubjectOnlineMeeting.objects.filter(is_active=True),
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

        return render(request, 'curriculum/class_meeting_list.html', context)

    # --- Fallback ---
    return redirect(reverse('pages:portal-home'))
