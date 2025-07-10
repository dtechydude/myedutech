from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Count
from django.db.models import F
#converting html to pdf
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
# from xhtml2pdf import pisa
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from staff.models import Teacher
from students.models import Student
from curriculum.models import Standard
from staff.forms import TeacherUpdateForm, StaffRegisterForm, StaffUpdateForm
# from attendance.models import AttendanceTotal, Attendance, AttendanceClass



#Displays all teachers
def teachers_list(request):
    all_teachers = Teacher.objects.all().order_by('-date_employed')    

    context = {
        'all_teachers': all_teachers
    }
    return render(request, 'staff/teachers_list.html', context)


# Display only my teacher
@login_required # Ensure only logged-in users can access this view
def my_teacher_view(request):
    logged_in_user = request.user

    try:
        # Get the Student profile associated with the logged-in user
        student_profile = Student.objects.get(user=logged_in_user)

        # Get the teacher associated with this student
        my_teacher = student_profile.form_teacher

        context = {
            'student': student_profile,
            'teacher': my_teacher,
            'has_teacher': True if my_teacher else False # For template logic
        }
    except Student.DoesNotExist:
        # Handle cases where a logged-in user doesn't have a Student profile
        # (e.g., if they are a teacher, or haven't completed their profile)
        context = {
            'student': None,
            'teacher': None,
            'has_teacher': False,
            'message': "You don't have a student profile yet."
        }
        # You might redirect them to a profile creation page or show a relevant message
        # return redirect('create_student_profile')

    return render(request, 'students/my_teacher_detail.html', context)



# #Displays all staff
# def staff_list(request):
#     all_staff = Staff.objects.all().order_by('-date_employed')

#     context ={
#         'all_staff': all_staff
#     }
#     return render(request, 'staff/staff_list.html', context)

# def assign_list(request):
#     assign = Assign.objects.all().order_by('-class_id')

#     context ={
#         'assign':assign
#     }
#     return render(request, 'staff/assign_list.html', context)


# Specific to the login detail
class TeacherSelfDetailView(LoginRequiredMixin, DetailView):
    template_name = 'staff/teacher_self_detail.html'
    model = Teacher

    def get_object(self, queryset=None):
           if queryset is None:
               queryset = self.get_queryset()
           return queryset.filter(user=self.request.user).first()


class TeacherDetailView(DetailView):
    template_name = 'staff/teacher_self_detail.html'
    context_object_name = 'teacher'
    queryset = Teacher.objects.all()

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Teacher, id=id_)
    

class TeacherUpdateView(LoginRequiredMixin, UpdateView):
    form_class = TeacherUpdateForm
    template_name = 'students/student_update_form.html'
    # queryset = StudentDetail.objects.all()


    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Teacher, id=id_)

    def form_valid(self, form):
        print(form.cleaned_data)
        return super().form_valid(form)

class TeacherDeleteView(LoginRequiredMixin, DeleteView):
    template_name = 'staff/teacher_delete.html'
    success_url = reverse_lazy('staff:teacher-list')
    
    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Teacher, id=id_)
    


@login_required
def my_clas(request, teacher_id, choice):
    teacher1 = get_object_or_404(Teacher, id=teacher_id)
    return render(request, 'attendance/t_clas.html', {'teacher1': teacher1, 'choice': choice})



def classroom_students(request, class_id):
    classroom = get_object_or_404(Class, id=class_id)
    students = Student.objects.filter(class_id=class_id)
    students_in_classroom = classroom.students.all().order_by('full_name')

    context = {
        'classroom': classroom,
        'students_in_classroom': students_in_classroom,
        'students':students
        
    }
    return render(request, 'staff/classroom_students.html', context)


class TeacherStudentCountListView(ListView):
    model = Teacher
    template_name = 'staff/all_teachers_student_counts.html'
    context_object_name = 'teachers' # Renames the default 'object_list' to 'teachers'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for teacher in context['teachers']:
            teacher.student_count = teacher.teacher.count() # Add student_count as an attribute
        return context