from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Count
import csv
from django.db.models import F, Q
from django.db import transaction
#converting html to pdf
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
# from xhtml2pdf import pisa
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from collections import Counter
from staff.models import Teacher
from students.models import Student
from curriculum.models import Standard, ClassGroup, SchoolIdentity
from staff.forms import TeacherUpdateForm, TeacherForm, CustomUserCreationForm, StaffAttendance, AttendanceDateForm, StaffAttendanceForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import logging
from django.utils import timezone
from datetime import date, timedelta # Make sure to import these!
import json
from django.forms import modelformset_factory
from django.utils import timezone
from django.db import transaction
from datetime import time, datetime
from django.core.paginator import Paginator
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from .models import StaffAttendance, Teacher
from datetime import time
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.forms import modelformset_factory
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Teacher, StaffAttendance
from .forms import (
    StaffAttendanceForm,
    AttendanceDateForm
)








# All Techers
@login_required
def teachers_list(request):
    """
    A view to display all users and export them to a CSV,
    only accessible by staff users.
    """
    user = request.user
    
    # Restrict access to only staff users
    if not user.is_staff:
        return redirect('pages/portal_home.html') # Redirect to a safe URL for non-staff users

    all_teachers_list = Teacher.objects.all().order_by('last_name', 'first_name')
    
    # Handle CSV export request
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="all_teachers.csv"'

        writer = csv.writer(response)
        writer.writerow(['Username', 'First Name', 'Last Name', 'Email', 'Phone', 'State Of Origin', 'User Type', 'Registered Date'])

        for u in all_teachers_list:
            writer.writerow([u.user.username, u.first_name, u.last_name, u.user.email, u.user.profile.phone, u.user.profile.state_of_origin, u.user.profile.user_type, u.user.profile.created])
        return response

    # Normal template rendering
    context = {'all_teachers': all_teachers_list}
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


# Teachers Student Count In Class

class TeacherStudentCountListView(ListView):
    model = Teacher
    template_name = 'staff/all_teachers_student_counts.html'
    context_object_name = 'teachers'

    def get_queryset(self):
        return super().get_queryset().prefetch_related(
            'teacher__current_class'
        ).order_by('user__last_name', 'user__first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        filtered_teachers = []

        for teacher in context['teachers']:
            # 1. Filter students: Exclude "Alumni"
            active_students = [
                s for s in teacher.teacher.all()
                if s.current_class and s.current_class.name != "Alumni"
            ]

            # 2. Calculate the Total Count
            count = len(active_students)

            # 3. ONLY proceed if the teacher has students (is a form teacher)
            if count > 0:
                teacher.total_student_count = count

                # 4. Determine the Unique Class Objects
                unique_classes = {s.current_class for s in active_students}

                # 5. Create the sorted list for badges
                teacher.class_list = [c.name for c in sorted(list(unique_classes), key=lambda x: x.name)]

                # Add this teacher to our final list
                filtered_teachers.append(teacher)

        # 6. Replace the context with our filtered list
        context['teachers'] = filtered_teachers
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



# Get the active User model
User = get_user_model()

@login_required
def teacher_details_signup(request):
    user_data = request.session.get('teacher_user_data')
    if not user_data:
        messages.error(request, 'Session expired. Please start the signup process again.')
        return redirect('staff:teacher_user_signup')

    school_identity = SchoolIdentity.objects.first()

    if request.method == 'POST':
        teacher_form = TeacherForm(request.POST, request.FILES)
        if teacher_form.is_valid():
            try:
                with transaction.atomic():
                    # Create the User instance using data from the *form*
                    user = User.objects.create_user(
                        username=user_data['username'],
                        password=user_data['password'],
                        email=user_data.get('email'),
                        # Get first_name and last_name from the validated form data
                        first_name=teacher_form.cleaned_data['first_name'],
                        last_name=teacher_form.cleaned_data['last_name'],
                    )

                    # Save the Teacher instance linked to the new user
                    teacher = teacher_form.save(commit=False)
                    teacher.user = user
                    teacher.save()
                    teacher_form.save_m2m() 
            
                if 'teacher_user_data' in request.session:
                    del request.session['teacher_user_data']

                messages.success(request, f'Teacher account for {user.first_name} {user.last_name} created successfully.')
                return redirect('staff:teacher_signup_success')
            except Exception as e:
                # Catch the specific KeyError and handle it gracefully
                # If the form is valid, this part should not be hit.
                messages.error(request, f'An error occurred: {e}')
                return redirect('staff:teacher_details_signup')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        # On GET, populate the form with initial data from the session
        initial_data = {
            'first_name': user_data.get('first_name', ''),
            'last_name': user_data.get('last_name', ''),
        }
        teacher_form = TeacherForm(initial=initial_data)

    context = {
        'teacher_form': teacher_form,
        'school_identity': school_identity,
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



class TeacherIDCardView(LoginRequiredMixin, View):
    """
    Displays a printable ID card for a specific teacher.
    """
    def get(self, request, teacher_id):
        teacher = get_object_or_404(Teacher, id=teacher_id)
        
        # Retrieve school branding
        try:
            school_identity = SchoolIdentity.objects.first()
        except Exception:
            school_identity = None

        context = {
            'teacher': teacher,
            'school_identity': school_identity,
        }
        return render(request, 'staff/teacher_id_card.html', context)
    

# # Staff Attendance Views
# # attendance/views.py

@login_required
def take_staff_attendance(request):

    # =====================================
    # ACCESS CONTROL
    # =====================================
    if not (
        request.user.is_staff or
        request.user.is_superuser
    ):
        messages.error(
            request,
            "Unauthorized access."
        )
        return redirect('/dashboard/')

    # =====================================
    # DATE FILTER
    # =====================================
    selected_date = timezone.localdate()

    date_form = AttendanceDateForm(
        request.GET or None
    )

    if date_form.is_valid():
        selected_date = date_form.cleaned_data['date']

    # =====================================
    # SEARCH + PAGE SIZE
    # =====================================
    search_query = request.GET.get('search', '').strip()

    per_page = request.GET.get('per_page', 20)

    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 20

    # =====================================
    # TEACHERS QUERYSET
    # =====================================
    teachers = Teacher.objects.select_related(
        'user'
    ).all().order_by(
        'user__first_name'
    )

    # =====================================
    # SEARCH FILTER
    # =====================================
    if search_query:

        teachers = teachers.filter(

            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)

        )

    # =====================================
    # PAGINATION
    # =====================================
    paginator = Paginator(
        teachers,
        per_page
    )

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(
        page_number
    )

    # =====================================
    # INITIAL DATA
    # =====================================
    initial_data = []

    for teacher in page_obj:

        attendance, created = StaffAttendance.objects.get_or_create(
            teacher=teacher,
            date=selected_date
        )

        initial_data.append({
            'id': attendance.id,
            'teacher_name': teacher.user.get_full_name(),
            'check_in_time': attendance.check_in_time,
            'check_out_time': attendance.check_out_time,
            'status': attendance.status,
            'remarks': attendance.remarks,
        })

    # =====================================
    # FORMSET
    # =====================================
    StaffAttendanceFormSet = modelformset_factory(
        StaffAttendance,
        form=StaffAttendanceForm,
        extra=0,
        can_delete=False
    )

    queryset = StaffAttendance.objects.filter(
        pk__in=[
            d['id']
            for d in initial_data
        ]
    )

    # =====================================
    # SAVE ATTENDANCE
    # =====================================
    if request.method == 'POST':

        formset = StaffAttendanceFormSet(
            request.POST,
            queryset=queryset
        )

        if formset.is_valid():

            with transaction.atomic():

                for form in formset:

                    attendance = form.save(
                        commit=False
                    )

                    # =========================
                    # AUTO LATE LOGIC
                    # =========================
                    if attendance.check_in_time:

                        late_time = time(8, 0)

                        if attendance.check_in_time > late_time:

                            attendance.is_late = True
                            attendance.status = 'late'

                        else:

                            attendance.is_late = False
                            attendance.status = 'present'

                    attendance.save()

            messages.success(
                request,
                f"Staff attendance for {selected_date} saved successfully."
            )

            return redirect(
                f"{request.path}?date={selected_date}&search={search_query}&per_page={per_page}"
            )

        else:

            messages.error(
                request,
                "Please correct the errors below."
            )

    else:

        formset = StaffAttendanceFormSet(
            queryset=queryset
        )

        for i, form in enumerate(formset):

            form.initial['teacher_name'] = (
                initial_data[i]['teacher_name']
            )

    # =====================================
    # CONTEXT
    # =====================================
    context = {
        'formset': formset,
        'date_form': date_form,
        'selected_date': selected_date,
        'search_query': search_query,
        'per_page': per_page,
        'page_obj': page_obj,
        'total_staff': teachers.count(),
    }

    return render(
        request,
        'staff/take_staff_attendance.html',
        context
    )


# Qr Scanner view 2
@login_required
def staff_attendance_scanner_view(request):

    if not (
        request.user.is_staff or
        request.user.is_superuser
    ):
        return redirect('/dashboard/')

    today = timezone.now().date()

    total_staff = Teacher.objects.count()

    present_count = StaffAttendance.objects.filter(
        date=today,
        check_in_time__isnull=False
    ).count()

    return render(
        request,
        'staff/staff_attendance_scanner.html',
        {
            'total_staff': total_staff,
            'present_count': present_count,
            'selected_date': today,  # NEW (useful for UI consistency)
        }
    )

# Qr view 3
@csrf_exempt
@login_required
def scan_staff_attendance_ajax(request, staff_id):

    if not (
        request.user.is_staff or
        request.user.is_superuser
    ):
        return JsonResponse({
            'status': 'error',
            'message': 'Unauthorized access.'
        })

    clean_staff_id = staff_id.strip()

    try:

        teacher = Teacher.objects.get(
            staff_id__iexact=clean_staff_id
        )

        today = timezone.now().date()
        current_time = timezone.localtime().time()

        attendance, created = StaffAttendance.objects.get_or_create(
            teacher=teacher,
            date=today
        )

        # =====================
        # CHECK IN
        # =====================
        if not attendance.check_in_time:

            attendance.check_in_time = current_time
            attendance.checked_in_by = request.user

            late_time = time(8, 0)

            if current_time > late_time:
                attendance.is_late = True
                attendance.status = 'late'
            else:
                attendance.is_late = False
                attendance.status = 'present'

            attendance.save()

            message = f'{teacher} checked in successfully.'

        # =====================
        # CHECK OUT
        # =====================
        elif not attendance.check_out_time:

            attendance.check_out_time = current_time
            attendance.checked_out_by = request.user
            attendance.save()

            message = f'{teacher} checked out successfully.'

        else:

            message = f'{teacher} attendance already completed.'

        present_count = StaffAttendance.objects.filter(
            date=today,
            check_in_time__isnull=False
        ).count()

        return JsonResponse({
            'status': 'success',
            'message': message,
            'present_count': present_count
        })

    except Teacher.DoesNotExist:

        return JsonResponse({
            'status': 'error',
            'message': f'Staff ID "{clean_staff_id}" not found.'
        })

# 4
@login_required
def staff_attendance_report(request):

    if not (
        request.user.is_staff or
        request.user.is_superuser
    ):
        return redirect('/dashboard/')

    records = StaffAttendance.objects.select_related(
        'teacher',
        'teacher__user'
    ).order_by('-date')

    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    # =========================
    # FILTERING
    # =========================
    if start_date and end_date:

        records = records.filter(
            date__range=[start_date, end_date]
        )

    # =========================
    # PAGINATION
    # =========================
    per_page = request.GET.get('per_page', 20)

    paginator = Paginator(records, per_page)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    context = {
        'records': page_obj,
        'page_obj': page_obj,
        'start_date': start_date,
        'end_date': end_date,
        'per_page': per_page,
    }

    return render(
        request,
        'staff/staff_attendance_report.html',
        context
    )


# 5
@login_required
def teacher_self_attendance(request):

    teacher = get_object_or_404(
        Teacher,
        user=request.user
    )

    # =========================
    # BASE QUERYSET
    # =========================
    records = StaffAttendance.objects.filter(
        teacher=teacher
    ).order_by('-date')

    # =========================
    # DATE FILTERS
    # =========================
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if start_date:
        records = records.filter(
            date__gte=start_date
        )

    if end_date:
        records = records.filter(
            date__lte=end_date
        )

    # =========================
    # SUMMARY COUNTS
    # =========================
    present_count = records.filter(
        check_in_time__isnull=False
    ).count()

    late_count = records.filter(
        is_late=True
    ).count()

    # =========================
    # PAGE SIZE FILTER
    # =========================
    per_page = request.GET.get('per_page', 10)

    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 10

    paginator = Paginator(records, per_page)

    page_number = request.GET.get('page')

    page_obj = paginator.get_page(page_number)

    context = {
        'records': page_obj,
        'page_obj': page_obj,
        'teacher': teacher,
        'present_count': present_count,
        'late_count': late_count,
        'per_page': str(per_page),
        'start_date': start_date,
        'end_date': end_date,
    }

    return render(
        request,
        'staff/staff_self_attendance.html',
        context
    )