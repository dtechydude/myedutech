from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Count
from django.db.models import F
from django.db import transaction
#converting html to pdf
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
# from xhtml2pdf import pisa
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from staff.models import Teacher
from students.models import Student
from curriculum.models import Standard, ClassGroup, SchoolIdentity
from staff.forms import TeacherUpdateForm, TeacherForm, CustomUserCreationForm, StaffRegisterForm, StaffUpdateForm
from django.contrib.auth.forms import UserCreationForm


#Displays all teachers
@login_required
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
    

# Teachers Subjects & Classes Assigned
def teacher_subjects_standards_view(request):
    """
    Displays a list of all teachers, their subjects taught,
    and the standards they are assigned to.
    """
    # Fetch all teacher objects from the database
    # The .prefetch_related() method is used for efficiency to
    # fetch all related subjects and standards in a single query.
    teachers = Teacher.objects.all().prefetch_related('subjects_taught', 'standards_assigned')

    context = {
        'teachers': teachers,
        'title': 'Teacher Assignments'
    }
    return render(request, 'staff/teacher_assignments.html', context)

# Visiting An Individual Teachers Assigned Classes And Subjects
def teacher_profile_view(request, teacher_id):
    """
    Displays the subjects and standards assigned to a specific teacher.
    """
    # Fetch the specific teacher object by ID, or return a 404 error if not found.
    teacher = get_object_or_404(
        Teacher.objects.prefetch_related('subjects_taught', 'standards_assigned'), 
        id=teacher_id
    )
    
    context = {
        'teacher': teacher,
        'title': f'{teacher.get_full_name()} Assignments'
    }
    return render(request, 'staff/teacher_assigned_page.html', context)

# Each Teachers Seeing Their Assigned Subects & Classes
@login_required
def my_assignments_view(request):
    """
    Displays the subjects and standards assigned to the currently logged-in teacher.
    """
    try:
        # Get the Teacher object associated with the logged-in user.
        teacher = Teacher.objects.prefetch_related(
            'subjects_taught', 
            'standards_assigned'
        ).get(user=request.user)

        context = {
            'teacher': teacher,
            'title': 'My Assignments'
        }
        return render(request, 'staff/teacher_self_assignments.html', context)
        
    except Teacher.DoesNotExist:
        # This block handles the case where the current user is not a teacher.
        messages.info(request, "Your profile is not linked to a teacher account. Please contact the administrator.")
        return redirect('pages:portal-home') # Redirect to a safe page like the dashboard

# View to Assign a Form Teacher to A Standard
def is_superuser(user):
    return user.is_superuser

@user_passes_test(is_superuser)
def assign_form_teacher_view(request):
    """
    View to assign a form teacher to a class and update all students in that class.
    """
    if request.method == 'POST':
        class_id = request.POST.get('class')
        teacher_id = request.POST.get('teacher')

        if not class_id or not teacher_id:
            messages.error(request, "Please select both a class and a teacher.")
            return redirect('assign_form_teacher')

        try:
            standard = get_object_or_404(Standard, id=class_id)
            teacher = get_object_or_404(Teacher, id=teacher_id)

            with transaction.atomic():
                # 1. Update the Standard model with the new form teacher.
                standard.form_teacher = teacher
                standard.save()
                
                # 2. Update all students in that class with the new form teacher.
                students_in_class = Student.objects.filter(current_class=standard)
                count = students_in_class.count()
                students_in_class.update(form_teacher=teacher)

            messages.success(request, f"Successfully assigned {teacher} as the form teacher for {standard.name} and updated {count} students.")

        except Exception as e:
            messages.error(request, f"An error occurred: {e}")

        return redirect('staff:assign_form_teacher')

    classes = Standard.objects.all().order_by('name')
    teachers = Teacher.objects.all().order_by('user__last_name')
    
    context = {
        'classes': classes,
        'teachers': teachers,
        'title': 'Assign Form Teacher',
    }
    return render(request, 'staff/assign_form_teacher.html', context)

# Assign A Form Teacher To A ClassGroup
def is_authorized_staff(user):
    return user.is_superuser or user.is_staff

@user_passes_test(is_authorized_staff)
def assign_form_teacher_to_classgroup_view(request):
    """
    Assigns a form teacher to a specific class group.
    """
    if request.method == 'POST':
        class_group_id = request.POST.get('class_group')
        teacher_id = request.POST.get('teacher')

        if not class_group_id or not teacher_id:
            messages.error(request, "Please select both a class group and a teacher.")
            return redirect('staff:assign_form_teacher_to_classgroup')

        try:
            class_group = get_object_or_404(ClassGroup, id=class_group_id)
            teacher = get_object_or_404(Teacher, id=teacher_id)

            with transaction.atomic():
                class_group.form_teacher = teacher
                class_group.save()
            
            messages.success(request, f"Successfully assigned {teacher.user.get_full_name()} as the form teacher for {class_group.name}.")

        except Exception as e:
            messages.error(request, f"An error occurred: {e}")

        return redirect('staff:assign_form_teacher_to_classgroup')

    # GET request
    class_groups = ClassGroup.objects.all().order_by('standard__name', 'name')
    teachers = Teacher.objects.all().order_by('user__first_name')
    
    context = {
        'class_groups': class_groups,
        'teachers': teachers,
        'title': 'Assign Form Teacher to Class Group',
    }
    return render(request, 'staff/assign_formteacher_to_classgroup.html', context)


# Teachers Signup View
# Get the custom User model if it exists, otherwise use the default
User = get_user_model()

@login_required
def teacher_user_signup(request):
    school_identity = SchoolIdentity.objects.first()
    
    if request.method == 'POST':
        user_form = CustomUserCreationForm(request.POST)
        if user_form.is_valid():
            # Store validated user data in the session
            request.session['teacher_user_data'] = {
                'username': user_form.cleaned_data['username'],
                'first_name': user_form.cleaned_data['first_name'],
                'last_name': user_form.cleaned_data['last_name'],
                'email': user_form.cleaned_data.get('email', ''), 
                'password': user_form.cleaned_data['password2'],
            }
            messages.success(request, 'User account created successfully. Please fill in the rest of the details.')
            return redirect('staff:teacher_details_signup')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        user_form = CustomUserCreationForm()
        
    context = {
        'user_form': user_form,
        'school_identity': school_identity,
    }
    return render(request, 'staff/teacher_user_signup.html', context)

@login_required
def teacher_details_signup(request):
    school_identity = SchoolIdentity.objects.first()
    
    # Check if Step 1 was completed
    teacher_user_data = request.session.get('teacher_user_data')
    if not teacher_user_data:
        messages.error(request, 'Please complete the user registration first.')
        return redirect('staff:teacher_user_signup')

    if request.method == 'POST':
        teacher_form = TeacherForm(request.POST)
        
        if teacher_form.is_valid():
            try:
                user = User.objects.create_user(
                    username=teacher_user_data['username'],
                    email=teacher_user_data['email'],
                    password=teacher_user_data['password'],
                    first_name=teacher_user_data['first_name'],
                    last_name=teacher_user_data['last_name'],
                )
            except Exception as e:
                messages.error(request, f'Failed to create user account: {e}. Please try again.')
                return redirect('staffteacher_user_signup')
            
            teacher = teacher_form.save(commit=False)
            teacher.user = user
            teacher.first_name = teacher_user_data['first_name']
            teacher.last_name = teacher_user_data['last_name']
            teacher.save()
            teacher_form.save_m2m()
            
            del request.session['teacher_user_data']
            
            return redirect('staff:teacher_signup_success')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        teacher_form = TeacherForm()
        
    context = {
        'teacher_form': teacher_form,
        'school_identity': school_identity,
        'first_name': teacher_user_data.get('first_name', ''), # Pass pre-filled values
        'last_name': teacher_user_data.get('last_name', ''),
        'middle_name': teacher_user_data.get('middle_name', '') # Middle name isn't in step 1, but we pass it anyway
    }
    return render(request, 'staff/teacher_details_signup.html', context)



@login_required
def teacher_signup_success(request):
    """
    Renders the success page after a teacher has been signed up.
    Provides options to sign up another teacher or go back to the dashboard.
    """
    school_identity = SchoolIdentity.objects.first()
    context = {
        'school_identity': school_identity,
    }
    return render(request, 'staff/teacher_signup_success.html', context)