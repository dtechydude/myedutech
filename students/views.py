from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Count, Sum, Q, F
from django.db import models
import datetime
#converting html to pdf
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
# from xhtml2pdf import pisa
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from students.models import Student, Hostel, Parent, GraduationRecord, Room
from staff.models import Teacher
from students.forms import StudentUpdateForm, SuperUserStudentUpdateForm
from payments.models import Payment, CategoryFee # Import Payment and CategoryFee models

from users.forms import UserRegisterForm
from curriculum.models import Standard, ClassGroup, Term, Session, SchoolIdentity
import io
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from django.http import FileResponse
import csv
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.template.loader import get_template
from xhtml2pdf import pisa

from django.db import IntegrityError, transaction
from datetime import date
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied





# Displays all students
@login_required
def student_list(request):
    # Check if the user is authenticated at the very beginning
    if not request.user.is_authenticated:
        # If not authenticated, redirect to login or show an error page
        return render(request, 'pages/portal_home.html') # Or redirect('login')

    # Now that we know the user is authenticated, we can safely access user properties.
    
    # Check for CSV export request first
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')

        # Determine which students to export based on user's role
        if request.user.is_superuser or request.user.is_staff:
            students_to_export = Student.objects.exclude(student_status='graduated').order_by('-date_admitted')
            filename = 'all_students.csv'
        elif hasattr(request.user, 'teacher'):
            students_to_export = Student.objects.filter(
                form_teacher__user=request.user
            ).exclude(student_status='graduated').order_by('user')
            filename = 'my_students.csv'
        else:
            return HttpResponse('You are not authorized to export student data.', status=403)

        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        writer = csv.writer(response)
        writer.writerow([
            'StudentID', 'Full Name', 'Current Class', 'DOB', 'Student Email', 'Student Phone', 
            'Guardian Phone', 'Guardian Email', 'Student Status'
        ])

        for student in students_to_export:
            writer.writerow([
                student.user.username,
                student.get_full_name(),
                student.current_class.name if student.current_class else '',
                student.DOB.strftime('%Y-%m-%d'),
                student.user.email,
                student.user.profile.phone,
                student.guardian_phone,
                student.guardian_email,
                student.student_status
            ])
        return response

    # Rendering logic for the HTML page
    my_students = []
    all_students = Student.objects.exclude(student_status='graduated').order_by('-date_admitted')

    if hasattr(request.user, 'teacher'):
        my_students = Student.objects.filter(
            form_teacher__user=request.user
        ).exclude(student_status='graduated').order_by('user')

    context = {
        'all_students': all_students,
        'my_students': my_students
    }

    if request.user.is_superuser or request.user.is_staff:
        return render(request, 'students/student_list.html', context)
    elif my_students:
        return render(request, 'students/my_student_list.html', context)
    else:
        return render(request, 'pages/portal_home.html')



# For Boading Students
@login_required
def student_boarder_list(request):
    # Filter for 'boarder' students and exclude any with a 'graduated' status
    boarder_student = Student.objects.filter(
        student_type='boarder'
    ).exclude(
        student_status='graduated'
    ).order_by('-date_admitted')

    context = {
        'boarder_student': boarder_student,
        'total_count': boarder_student.count()

    }

    if request.user.is_superuser or request.user.is_staff:
        return render(request, 'students/student_boarder_list.html', context)
    else:
        return render(request, 'pages/portal_home.html')



# ==========================================================================
# GRADUATED Students List Old
@login_required
def graduated_students_list(request):
    """
    Displays a list of all students who have a status of 'graduated'.
    """
    graduated_students = Student.objects.filter(student_status='graduated').order_by('last_name', 'first_name')
    
    context = {
        'graduated_students': graduated_students,
        'title': 'Graduated Students',
    }
    return render(request, 'students/graduated_students_list.html', context)

# GRADUATED Students(Move Students To Graduated)
def is_authorized_staff(user):
    return user.is_superuser or user.is_staff



@user_passes_test(is_authorized_staff)
def graduate_students_view(request):
    standards = Standard.objects.all().order_by('name')
    sessions = Session.objects.all().order_by('-start_date')  # or use name
    students = Student.objects.none()
    selected_standard = None

    if request.method == "GET":
        standard_id = request.GET.get('standard')
        if standard_id:
            selected_standard = get_object_or_404(Standard, id=standard_id)
            students = Student.objects.filter(
                current_class=selected_standard
            ).exclude(student_status='graduated').order_by('last_name')

        return render(request, 'students/graduate_students.html', {
            'standards': standards,
            'sessions': sessions,
            'students': students,
            'selected_standard': selected_standard,
            'title': 'Graduate Students To Alumni',
        })

    # POST
    selected_ids = request.POST.getlist('selected_students')
    session_id = request.POST.get('graduation_session_id')

    if not selected_ids:
        messages.error(request, "Please select at least one student to graduate.")
        return redirect('students:graduate_students')

    # validate session
    graduation_session = None
    if session_id:
        graduation_session = get_object_or_404(Session, id=session_id)

    try:
        with transaction.atomic():
            students_to_grad = Student.objects.filter(id__in=selected_ids)

            # Ensure Alumni standard exists
            alumni_standard, created = Standard.objects.get_or_create(name__iexact='Alumni', defaults={'name': 'Alumni'})

            count = students_to_grad.count()
            for student in students_to_grad:
                # Create a graduation record
                GraduationRecord.objects.create(
                    student=student,
                    session=graduation_session,
                    graduated_class=student.current_class
                )

                # Update student fields
                student.student_status = 'graduated'
                student.current_class = alumni_standard
                student.graduated_session = graduation_session
                student.save()

        messages.success(request, f"Successfully graduated {count} students.")
    except Exception as e:
        messages.error(request, f"An error occurred: {e}")

    return redirect('students:graduate_students')



@user_passes_test(is_authorized_staff)
def alumni_list_view(request):
    queryset = Student.objects.filter(student_status='graduated') \
        .select_related('current_class', 'graduated_session')

    sessions = Session.objects.all().order_by('-start_date')
    standards = Standard.objects.filter(name__iexact='Alumni') | Standard.objects.exclude(name__iexact='Alumni')

    # ---- FILTERING ----
    session_id = request.GET.get('session')
    class_id = request.GET.get('class')
    year = request.GET.get('year')
    q = request.GET.get('q')

    if session_id:
        queryset = queryset.filter(graduated_session__id=session_id)

    if class_id:
        queryset = queryset.filter(graduation_records__graduated_class__id=class_id)

    if year:
        queryset = queryset.filter(graduation_records__date_graduated__year=year)

    if q:
        queryset = queryset.filter(
            models.Q(first_name__icontains=q) |
            models.Q(last_name__icontains=q) |
            models.Q(USN__icontains=q)
        )

    queryset = queryset.distinct().order_by('-graduation_records__date_graduated', 'last_name')

    # ---- SIMPLE CSV EXPORT WITHOUT CHANGING YOUR LOGIC ----
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response['Content-Disposition'] = 'attachment; filename="alumni.csv"'

        writer = csv.writer(response)
        writer.writerow(["Name", "Previous Class", "Session", "Graduated On"])

        for student in queryset:
            rec = student.graduation_records.first()
            writer.writerow([
                student.get_full_name(),
                rec.graduated_class.name if rec else "-",
                student.graduated_session.name if student.graduated_session else "-",
                rec.date_graduated.strftime("%Y-%m-%d %H:%M") if rec and rec.date_graduated else "-"
            ])
        return response

    # ---- PAGINATION (unchanged) ----
    paginator = Paginator(queryset, 25)
    page = request.GET.get('page')
    alumni_page = paginator.get_page(page)

    # ---- YEARS (unchanged) ----
    date_objects = GraduationRecord.objects.dates('date_graduated', 'year', order='DESC')
    years = [date_obj.year for date_obj in date_objects]

    return render(request, 'students/alumni_list.html', {
        'alumni': alumni_page,
        'sessions': sessions,
        'years': years,
        'standards': standards,
        'q': q,
    })



@user_passes_test(is_authorized_staff)
def readmit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id, student_status='graduated')
    standards = Standard.objects.exclude(name__iexact='Alumni').order_by('name')

    if request.method == 'POST':
        new_class_id = request.POST.get('new_class')
        if not new_class_id:
            messages.error(request, "Please choose a class to re-admit the student into.")
            return redirect('students:readmit_student', student_id=student.id)

        new_class = get_object_or_404(Standard, id=new_class_id)
        student.current_class = new_class
        student.student_status = 'active'
        student.graduated_session = None  # optional: clear session
        student.save()

        messages.success(request, f"{student.get_full_name()} has been re-admitted into {new_class.name}.")
        return redirect('students:alumni_list')

    return render(request, 'students/readmit_student.html', {
        'student': student,
        'standards': standards,
    })

#  End Graduated View Code
#======================================================================================

@login_required
def hostel_list(request):
    # Prefetch the students to make the property counts faster
    hostel_list = Hostel.objects.all().prefetch_related('hostel_name')
    
    context = {
        'hostel_list': hostel_list,
    }
    
    return render(request, 'students/hostel_list.html', context)
    

# SEARCH STUDENT RECORD
def student_search_list(request):
    # Base queryset - using select_related for performance (database optimization)
    query = request.GET.get('search', '').strip()
    student_list = Student.objects.select_related('current_class', 'user').all()

    # Apply search filters if a query exists
    if query:
        student_list = student_list.filter(
            Q(first_name__icontains=query) | 
            Q(last_name__icontains=query) | 
            Q(current_class__name__icontains=query) | 
            Q(guardian_name__icontains=query) | 
            Q(user__username__icontains=query) | 
            Q(USN__icontains=query)
        ).distinct()

    # Pagination logic
    page = request.GET.get('page', 1)
    paginator = Paginator(student_list, 20) # 20 is usually better for mobile/web balance
    
    try:
        students = paginator.page(page)
    except PageNotAnInteger:
        students = paginator.page(1)
    except EmptyPage:
        students = paginator.page(paginator.num_pages)

    context = {
        'students': students,
        'query': query,
        'is_search': bool(query)
    }
    
    return render(request, 'students/search_student_list.html', context)



#count students in each class
@login_required
def student_in_class(request):
    students = Student.objects.all()
    # student_no = Student.objects.exclude(current_class__name="Alumni").order_by('current_class').values('current_class__name').annotate(count=Count('current_class__name'))
    student_no = (
    Student.objects
    .filter(
        current_class__isnull=False,
        current_class__name__isnull=False
    )
    .exclude(current_class__name__in=["", "Alumni"])
    .values("current_class__name")
    .annotate(count=Count("id"))
    .order_by("current_class__name")
)
    # try:
    #     num_inclass = Student.objects.filter(standard__name = request.user.student.standard).count()
    # except Student.DoesNotExist:
    #     num_inclass = Student.objects.filter()

    try:
        num_inclass = Student.objects.filter(
            current_class=request.user.student.current_class
            ).count()
    except Student.DoesNotExist:
        num_inclass = 0

    return render(request, 'students/student_no_in_class.html', {'students': students, 'student_no':student_no, 'num_inclass':num_inclass})


class StudentDetailView(DetailView):
    template_name = 'students/student_detail.html'
    queryset = Student.objects.all()

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Student, USN=id_)
    


## Specific to the login detail New Logic to handle student does not exist
class StudentSelfDetailView(LoginRequiredMixin, DetailView):
    model = Student
    template_name = 'students/student_self_detail.html'
    context_object_name = 'student'

    def get_object(self, queryset=None):
        try:
            # Attempt to find the Student object linked to the logged-in user.
            return Student.objects.get(user=self.request.user)
        except Student.DoesNotExist:
            # If no student is found, redirect to a safe page with an error message.
            messages.error(self.request, "Your student profile could not be found. Please contact the school administration for assistance.")
            return redirect('pages:portal-home') # Adjust this URL as needed


    
# new student update form
class StudentUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'students/student_update_form.html'
    # Define the default form and model here for clarity
    # model = Student 
    # form_class = StudentUpdateForm # This is often necessary even if overridden by get_form_class

    def dispatch(self, request, *args, **kwargs):
        """
        Check if the user is staff before allowing them to access the view.
        If not staff, redirect them to the portal home page.
        """
        if not request.user.is_staff:
            messages.error(request, "You do not have permission to edit student details.")
            # Redirect to the main portal home page
            return redirect(reverse_lazy('pages:portal-home')) # Change 'pages:portal-home' to your actual home URL name
        
        # If the user is staff, proceed with the UpdateView logic
        return super().dispatch(request, *args, **kwargs)

    def get_object(self, queryset=None):
        """
        Retrieves the student object based on the URL parameter (usn).
        """
        usn = self.kwargs.get("usn")
        return get_object_or_404(Student, USN=usn)

    def get_form_class(self):
        # Allow superusers to use the superuser form, staff uses the standard form
        if self.request.user.is_superuser:
            return SuperUserStudentUpdateForm
        
        # If the user is staff (and passed the dispatch check)
        return StudentUpdateForm

    def get_success_url(self):
        """
        Defines the URL to redirect to after a successful form submission.
        """
        # Ensure 'self.object' is available after a successful save
        return reverse_lazy('students:student-detail', kwargs={'id': self.object.USN})


class StudentDeleteView(LoginRequiredMixin, DeleteView):
    template_name = 'students/student_delete.html'
    success_url = reverse_lazy('students:student-list')
    
    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Student, id=id_)
    

class MyTeacherDetailView(DetailView):
    template_name = 'student/my_teacher_detail.html'
    context_object_name = 'teacher'
    queryset = Teacher.objects.all()

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Teacher, id=id_)
    
# My Class Mates

@login_required
def my_classmates_view(request):
    try:
        # Get the logged-in user's student profile
        student = request.user.student
        
        # Get the classroom the student belongs to
        standard = student.current_class

        if standard:
            # Get all other students in the same classroom, excluding the current student
            classmates = Student.objects.filter(current_class=standard).exclude(user=request.user)
        else:
            classmates = [] # No classroom assigned
            
        context = {
            'student': student,
            'standard': standard,
            'classmates': classmates,
        }
        return render(request, 'students/my_classmates.html', context)
    except Student.DoesNotExist:
        # Handle cases where the logged-in user doesn't have a student profile
        return render(request, 'students/no_student_profile.html', {})
    except Exception as e:
        # Generic error handling
        return render(request, 'students/error.html', {'error_message': str(e)})
    


# Student ID Card
class StudentIDCardView(LoginRequiredMixin, View):
    def get(self, request, student_id):
        student = get_object_or_404(Student, id=student_id)
        
        # REMOVED: SchoolIdentity.objects.first() lookup.
        # The context processor will now handle 'school_info' automatically.

        context = {
            'student': student,
            # 'school_info' is removed from here
        }
        return render(request, 'students/test_student_id_card.html', context)

# Bulk Print ID Card
class BulkStudentIDCardView(LoginRequiredMixin, View):
    def get(self, request):
        class_id = request.GET.get('class')
        # students = Student.objects.select_related('current_class')
        # In BulkStudentIDCardView
        students = Student.objects.select_related(
            'current_class__identity_mapping__school_identity', 
            'user__profile'
        ).all()

        if class_id:
            students = students.filter(current_class_id=class_id)

        return render(request, 'students/bulk_id_cards.html', {
            'students': students,
            'classes': Standard.objects.all(),
            'selected_class': class_id,
            # 'school_info' is removed from here so it doesn't stay hardcoded to 'first()'
        })

# Student Promotion Logic
def is_authorized_to_promote(user):
    """
    Checks if the user is an admin or a staff member.
    """
    return user.is_superuser or hasattr(user, 'teacher')

@user_passes_test(is_authorized_to_promote)
def promote_students_view(request):
    """
    View to promote all students from one class to the next using a defined promotion order.
    """
    if request.method == 'POST':
        from_class_id = request.POST.get('from_class')
        
        if not from_class_id:
            messages.error(request, "Please select a class to promote.")
            return redirect('promote_students')

        try:
            from_class = Standard.objects.get(id=from_class_id)
            
            # Permission Check
            is_admin = request.user.is_superuser
            is_form_teacher = False
            if hasattr(request.user, 'teacher'):
                # Assuming Standard has a ForeignKey to Teacher
                is_form_teacher = (from_class.form_teacher == request.user.teacher)

            if not is_admin and not is_form_teacher:
                messages.error(request, "You do not have permission to promote this class.")
                return redirect('promote_students')

            # Find the next class based on the promotion_order
            try:
                next_class = Standard.objects.get(promotion_order=from_class.promotion_order + 1)
                promotion_type = 'promoted'
            except Standard.DoesNotExist:
                # If there is no next class, students will be graduated
                next_class = None
                promotion_type = 'graduated'
            
            with transaction.atomic():
                students_to_promote = Student.objects.filter(current_class=from_class)
                count = students_to_promote.count()
                
                if promotion_type == 'promoted':
                    students_to_promote.update(current_class=next_class)
                    messages.success(request, f"Successfully promoted {count} students from {from_class.name} to {next_class.name}.")
                else:
                    students_to_promote.update(current_class=None, student_status='graduated')
                    messages.success(request, f"Successfully graduated {count} students from {from_class.name}.")
            
        except Standard.DoesNotExist:
            messages.error(request, "The selected class does not exist.")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")
            
        return redirect('students:promote_students')

    # GET request: display the form
    classes = Standard.objects.all().order_by('promotion_order')
    context = {
        'classes': classes,
        'title': 'Promote Students',
    }
    return render(request, 'students/promote_students.html', context)


# Promoting Individual Students Using the Standard Model
def is_authorized_to_promote(user):
    """
    Checks if the user is an admin or a staff member.
    """
    return user.is_superuser or hasattr(user, 'teacher')

@user_passes_test(is_authorized_to_promote)
def promote_individual_students_view(request):
    """
    View to promote specific students from a selected class.
    """
    classes = Standard.objects.all().order_by('promotion_order')
    students = Student.objects.none()
    from_class = None
    next_class_options = Standard.objects.none()

    if request.method == 'POST':
        from_class_id = request.POST.get('from_class_id')
        selected_students_ids = request.POST.getlist('selected_students')
        to_class_id = request.POST.get('to_class')

        if not from_class_id or not selected_students_ids or not to_class_id:
            messages.error(request, "Invalid promotion request. Please select a class, students, and a destination class.")
            return redirect('promote_individual_students')

        try:
            from_class = get_object_or_404(Standard, id=from_class_id)
            to_class = get_object_or_404(Standard, id=to_class_id)
            
            # Permission Check (re-check on POST for security)
            is_admin = request.user.is_superuser
            is_form_teacher = False
            if hasattr(request.user, 'teacher'):
                # Assuming Standard has a ForeignKey to Teacher
                is_form_teacher = (from_class.form_teacher == request.user.teacher)

            if not is_admin and not is_form_teacher:
                messages.error(request, "You do not have permission to promote students from this class.")
                return redirect('promote_individual_students')

            with transaction.atomic():
                students_to_promote = Student.objects.filter(
                    current_class=from_class,
                    id__in=selected_students_ids
                )
                count = students_to_promote.count()
                
                students_to_promote.update(current_class=to_class)
                
            messages.success(request, f"Successfully promoted {count} students from {from_class.name} to {to_class.name}.")
            
        except Standard.DoesNotExist:
            messages.error(request, "One of the selected classes does not exist.")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")
            
        return redirect('students:promote_individual_students')

    # GET request: Display the student selection form
    selected_class_id = request.GET.get('class')
    if selected_class_id:
        from_class = get_object_or_404(Standard, id=selected_class_id)
        students = Student.objects.filter(current_class=from_class).order_by('last_name', 'first_name')
        
        # Get next class options (all classes after the selected one)
        # next_class_options = Standard.objects.filter(
        #     promotion_order__gt=from_class.promotion_order
        # ).order_by('promotion_order')

        next_class_options = Standard.objects.exclude(
        id=from_class.id
    ).order_by(F('promotion_order').asc(nulls_last=True), 'name')

    context = {
        'classes': classes,
        'students': students,
        'from_class': from_class,
        'next_class_options': next_class_options,
        'title': 'Individual Student Promotion',
    }
    return render(request, 'students/promote_individual_students.html', context)


# Promoting Using The ClassGroup Model Not Yet implemented
@user_passes_test(is_authorized_to_promote)
def promote_students_by_group_view(request):
    if request.method == 'POST':
        from_group_id = request.POST.get('from_group')
        
        if not from_group_id:
            messages.error(request, "Please select a class group to promote.")
            return redirect('promote_students_by_group')

        try:
            from_group = ClassGroup.objects.get(id=from_group_id)
            from_standard = from_group.standard
            
            try:
                next_standard = Standard.objects.get(promotion_order=from_standard.promotion_order + 1)
                next_group = ClassGroup.objects.get(standard=next_standard, promotion_order=from_group.promotion_order)
                promotion_type = 'promoted'
            except (Standard.DoesNotExist, ClassGroup.DoesNotExist):
                next_group = None
                promotion_type = 'graduated'

            # ... permission checks (as before)

            with transaction.atomic():
                students_to_promote = Student.objects.filter(current_class=from_group)
                count = students_to_promote.count()
                
                if promotion_type == 'promoted':
                    students_to_promote.update(current_class=next_group)
                    messages.success(request, f"Successfully promoted {count} students from {from_group.name} to {next_group.name}.")
                else:
                    students_to_promote.update(current_class=None, student_status='graduated')
                    messages.success(request, f"Successfully graduated {count} students from {from_group.name}.")
            
        except Exception as e:
            messages.error(request, f"An error occurred: {e}")
            
        return redirect('promote_students_by_group')

    # GET request
    groups = ClassGroup.objects.all().order_by('standard__promotion_order', 'promotion_order')
    context = {
        'groups': groups,
        'title': 'Promote Students by Group',
    }
    return render(request, 'schools/promote_students_by_group.html', context)


# View For Assigning Class Group To Students
def is_authorized_staff(user):
    return user.is_superuser or user.is_staff

@user_passes_test(is_authorized_staff)
def assign_classgroup_to_students_view(request):
    """
    Allows batch assignment of a ClassGroup to students within a specific Standard.
    """
    if request.method == 'POST':
        standard_id = request.POST.get('standard_id')
        classgroup_id = request.POST.get('classgroup')
        selected_student_ids = request.POST.getlist('selected_students')

        if not standard_id or not classgroup_id or not selected_student_ids:
            messages.error(request, "Please select a standard, a class group, and at least one student.")
            return redirect('assign_classgroup_to_students')

        try:
            standard = get_object_or_404(Standard, id=standard_id)
            classgroup = get_object_or_404(ClassGroup, id=classgroup_id)

            # Important: Validate that the selected ClassGroup belongs to the selected Standard.
            if classgroup.standard != standard:
                messages.error(request, "The selected class group does not belong to the selected standard.")
                return redirect('assign_classgroup_to_students')
            
            with transaction.atomic():
                students_to_update = Student.objects.filter(id__in=selected_student_ids, current_class=standard)
                count = students_to_update.count()
                
                # Update the students' class_group field. The form_teacher is automatically
                # determined by this relationship.
                students_to_update.update(class_group=classgroup)
                
            messages.success(request, f"Successfully assigned {count} students to {classgroup.name}.")

        except Exception as e:
            messages.error(request, f"An error occurred: {e}")

        return redirect('students:assign_classgroup_to_students')
    
    # GET request
    standards = Standard.objects.all().order_by('name')
    selected_standard = None
    students = Student.objects.none()
    class_groups = ClassGroup.objects.none()

    standard_id_param = request.GET.get('standard')
    if standard_id_param:
        selected_standard = get_object_or_404(Standard, id=standard_id_param)
        students = Student.objects.filter(current_class=selected_standard).order_by('first_name')
        class_groups = ClassGroup.objects.filter(standard=selected_standard).order_by('name')

    context = {
        'standards': standards,
        'selected_standard': selected_standard,
        'students': students,
        'class_groups': class_groups,
        'title': 'Assign Class Group to Students',
    }
    return render(request, 'students/assign_classgroup.html', context)



# PARENT DASHBOARD
from prep_reports.models import PrepReportCard

@login_required
def parent_dashboard(request):

    from results.models import  ResultPublication, SessionResultStatus
    from curriculum.models import Session, Term
    from payments.models import StudentFeeAssignment, Payment
    from django.db.models import Sum
    from decimal import Decimal

    try:
        parent = Parent.objects.get(user=request.user)
        children = Student.objects.filter(parent=parent).prefetch_related('scores__term')
    except Parent.DoesNotExist:
        children = []

    children_with_reports = []

    all_terms = Term.objects.all().order_by('id')
    all_sessions = Session.objects.all().order_by('id')

    current_session = Session.objects.filter(is_current=True).order_by('-name').first()
    current_term = Term.objects.filter(session=current_session, is_current=True).order_by('-start_date').first()

    for child in children:

        invoices = StudentFeeAssignment.objects.filter(student=child).order_by('-id')
        receipts = Payment.objects.filter(student=child).order_by('-payment_date')

        child_data = {
            'child': child,
            'termly_reports': [],
            'session_reports': [],
            'invoices': invoices,
            'receipts': receipts,
            'grand_payment_summary': {},
            'current_term': current_term,
            'current_session': current_session,
        }

        # =====================================================
        # PREP REPORTS (UNCHANGED - already correct)
        # =====================================================
        published_prep_cards = (
            PrepReportCard.objects.filter(
                student=child,
                status='published'
            )
            .select_related('period', 'period__term', 'period__session')
        )

        prep_term_ids = set()

        for card in published_prep_cards:
            if card.period and card.period.term:
                prep_term_ids.add(card.period.term.id)

                child_data['termly_reports'].append({
                    'is_prep': True,
                    'prep_card': card,
                    'term': card.period.term,
                })

        # =====================================================
        # TERM PUBLICATION (FIXED - IMPORTANT PART)
        # =====================================================

        published_term_ids = set(
            ResultPublication.objects.filter(
                student=child,
                is_published=True
            ).values_list('term_id', flat=True)
        )

        for term in all_terms:

            # skip prep-covered terms
            if term.id in prep_term_ids:
                continue

            # enforce publication gate
            if term.id not in published_term_ids:
                continue

            # ensure scores exist
            if child.scores.filter(term=term).exists():
                child_data['termly_reports'].append({
                    'is_prep': False,
                    'term': term,
                })

        # =====================================================
        # SESSION REPORTS (UNCHANGED - already correct)
        # =====================================================

        published_session_ids = set(
            SessionResultStatus.objects.filter(
                student=child,
                is_published=True
            ).values_list('session_id', flat=True)
        )

        for session in all_sessions:
            if (
                session.id in published_session_ids and
                child.scores.filter(term__session=session).exists()
            ):
                child_data['session_reports'].append(session)

        # =====================================================
        # FINANCIAL SUMMARY (UNCHANGED)
        # =====================================================

        total_due = StudentFeeAssignment.objects.filter(student=child).aggregate(
            total_due=Sum('amount_due')
        ).get('total_due') or Decimal('0.00')

        total_paid = Payment.objects.filter(student=child).aggregate(
            total_paid=Sum('amount_received')
        ).get('total_paid') or Decimal('0.00')

        total_balance = total_due - total_paid

        child_data['grand_payment_summary'] = {
            'total_due': total_due,
            'total_paid': total_paid,
            'total_balance': total_balance,
            'is_paid': total_balance <= 0
        }

        # =====================================================
        # SORT REPORTS (SAFE)
        # =====================================================

        child_data['termly_reports'].sort(
            key=lambda x: (
                x['term'].start_date if x.get('term') else None
            ),
            reverse=True
        )

        children_with_reports.append(child_data)

    context = {
        'children_with_reports': children_with_reports
    }

    return render(request, 'students/parent_dashboard.html', context)


@staff_member_required
def parent_list_view(request):
    query = request.GET.get('q', '')
    
    parents_list = Parent.objects.all().prefetch_related('children')
    
    if query:
        parents_list = parents_list.filter(
            Q(guardian_name__icontains=query) |
            Q(guardian_email__icontains=query) |
            Q(user__username__icontains=query) |
            Q(children__first_name__icontains=query) |
            Q(children__last_name__icontains=query)
        ).distinct()

    paginator = Paginator(parents_list, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    try:
        school_info = SchoolIdentity.objects.first()
    except SchoolIdentity.DoesNotExist:
        school_info = None
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'school_info': school_info,
    }
    return render(request, 'students/parent_list.html', context)

# New view to export data as CSV
@staff_member_required
def export_parents_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="parents.csv"'

    writer = csv.writer(response)
    
    # Write the header row
    writer.writerow(['Guardian Name', 'Guardian Email', 'Guardian Phone', 'Student Name', 'Student USN'])
    
    # Get all parents and related children
    parents = Parent.objects.all().prefetch_related('children')
    
    for parent in parents:
        # Check if the parent has children
        if parent.children.exists():
            for child in parent.children.all():
                writer.writerow([
                    parent.guardian_name, 
                    parent.guardian_email, 
                    parent.guardian_phone,
                    child.get_full_name(),
                    child.USN
                ])
        else:
            # Handle parents without children
            writer.writerow([
                parent.guardian_name, 
                parent.guardian_email, 
                parent.guardian_phone,
                'N/A',
                'N/A'
            ])

    return response


# Student's Birthay
@login_required
def upcoming_birthdays_view(request):
    """
    Allows form teachers to view their own students' birthdays
    and admins (is_staff) to view all students' birthdays.
    """
    today = datetime.date.today()
    current_month = today.month
    upcoming_month_1 = (today.month % 12) + 1
    upcoming_month_2 = (upcoming_month_1 % 12) + 1
    
    # Check if the user is a staff member (admin)
    if request.user.is_staff:
        # Staff members see all students
        birthday_students = Student.objects.select_related('user__profile').filter(
            Q(DOB__month=current_month) | 
            Q(DOB__month=upcoming_month_1) | 
            Q(DOB__month=upcoming_month_2)
        ).order_by('DOB__month', 'DOB__day')
    else:
        # Normal users (form teachers) see only their own students
        try:
            form_teacher = request.user.teacher # Assuming a one-to-one relationship
            birthday_students = Student.objects.select_related('user__profile').filter(
                form_teacher=form_teacher,
                DOB__month__in=[current_month, upcoming_month_1, upcoming_month_2]
            ).order_by('DOB__month', 'DOB__day')
        except Teacher.DoesNotExist:
            # Handle cases where the user is logged in but not a teacher
            return redirect('some_other_view_name') # Change to a safe URL name

    # Handle CSV export request
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = "all_students_birthdays.csv" if request.user.is_staff else "my_students_birthdays.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Full Name', 'DOB', 'Student Email', 'Student Phone', 'Guardian Phone', 'Guardian Email', 'Current Class'])

        for student in birthday_students:
            writer.writerow([
                student.get_full_name(),
                student.DOB.strftime('%B %d'),
                student.user.email,
                student.user.profile.phone,
                student.guardian_phone,
                student.guardian_email,
                student.current_class
            ])
        return response

    # Normal template rendering
    current_birthdays = birthday_students.filter(DOB__month=current_month)
    upcoming_birthdays = birthday_students.exclude(DOB__month=current_month)

    context = {
        'current_birthdays': current_birthdays,
        'upcoming_birthdays': upcoming_birthdays,
    }
    
    return render(request, 'students/upcoming_birthdays.html', context)


#============================================================
# LOGIC FOR STUDENT ARCHIVE

# --- Helper Function for CSV Export (Unchanged) ---
def export_students_csv(queryset):
    """
    Helper function to generate a CSV response from a given student queryset.
    (Assuming Student model and its field definitions are available)
    """
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="student_archive.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "USN",
        "Full Name",
        "Gender",
        "Status",
        "Class on Admission",
        "Date Admitted",
        "Graduated Session",
        "Parent/Guardian",
        "Guardian Phone",
    ])

    for s in queryset:
        # Safely access foreign key names, assuming .name exists
        class_name = s.class_on_admission.name if hasattr(s, 'class_on_admission') and s.class_on_admission else ""
        session_name = s.graduated_session.name if hasattr(s, 'graduated_session') and s.graduated_session else ""
        
        writer.writerow([
            s.USN,
            f"{s.last_name} {s.first_name}",
            s.gender,
            s.student_status,
            class_name,
            s.date_admitted,
            session_name,
            s.guardian_name,
            s.guardian_phone,
        ])

    return response
# --------------------------------------------------

@staff_member_required
def student_archive(request):
    """
    Displays the archived student records, supporting search, filtering, and CSV export,
    with server-side pagination.
    """
    # Archived statuses
    archived_status = ['graduated', 'dropped', 'expelled', 'suspended']

    # Base queryset, ordered for consistent pagination
    students = Student.objects.filter(student_status__in=archived_status).order_by('-date_admitted', 'last_name')

    # --- GET FILTERS & PAGE NUMBER ---
    q = request.GET.get('q')
    status_filter = request.GET.get('status')
    session_filter = request.GET.get('session')
    page = request.GET.get('page', 1) # Default to page 1

    # --- APPLY FILTERS TO QUERYSET ---
    if q:
        students = students.filter(
            models.Q(first_name__icontains=q) |
            models.Q(last_name__icontains=q) |
            models.Q(USN__icontains=q)
        )

    if status_filter and status_filter != "all":
        students = students.filter(student_status=status_filter)

    if session_filter and session_filter != "all":
        students = students.filter(graduated_session_id=session_filter)

    # --- CSV EXPORT (Must run on the full filtered queryset) ---
    if request.GET.get("export") == "csv":
        return export_students_csv(students)

    # --- SERVER-SIDE PAGINATION ---
    paginator = Paginator(students, 15) # 15 students per page
    
    try:
        students_page = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        students_page = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results.
        students_page = paginator.page(paginator.num_pages)

    # --- PREPARE CONTEXT ---
    sessions = Student.objects.filter(graduated_session__isnull=False).values_list("graduated_session", "graduated_session__name").distinct()

    # Generate the query string fragment to preserve filters across pagination links
    # Start with request.GET.copy() to get mutable object
    params = request.GET.copy()
    # Remove 'page' so it can be cleanly added back by the template pagination logic
    if 'page' in params:
        params.pop('page')
    query_string = params.urlencode()

    return render(request, "students/archive.html", {
        "students": students_page, # Pass the Paginator Page object
        "sessions": sessions,
        "selected_status": status_filter,
        "selected_session": session_filter,
        "q": q,
        "query_string": query_string, # Used to preserve filters in pagination links
    })


# student bulk upload
"""
views.py — Bulk Student Upload Views
KwikSchools — Smarter Schools!
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET, require_POST
from django.utils.decorators import method_decorator
from django.views import View

from .forms import StudentBulkUploadForm
from .services.bulk_upload import process_student_csv, generate_sample_csv

logger = logging.getLogger(__name__)


def _is_staff_or_superuser(user):
    """Permission check: only staff or superusers may bulk upload."""
    return user.is_active and (user.is_staff or user.is_superuser)


staff_required = user_passes_test(
    _is_staff_or_superuser,
    login_url='login',  # adjust to your login URL name
)


# ─── Bulk Upload View ────────────────────────────────────────────────────────

@method_decorator([login_required(login_url='login'), staff_required], name='dispatch')
class StudentBulkUploadView(View):
    """
    GET  — show the upload form + instructions.
    POST — process the CSV and display results.
    """
    template_name = 'students/bulk_upload.html'

    def get(self, request):
        form = StudentBulkUploadForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = StudentBulkUploadForm(request.POST, request.FILES)

        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
                'form_errors': form.errors,
            })

        csv_file = form.cleaned_data['csv_file']
        overwrite = form.cleaned_data.get('overwrite_existing', False)

        try:
            results = process_student_csv(
                file_obj=csv_file,
                overwrite=overwrite,
                request_user=request.user,
            )
        except Exception as e:
            logger.exception('Bulk upload failed unexpectedly.')
            messages.error(request, f'Upload failed: {e}')
            return render(request, self.template_name, {'form': form})

        # Build summary message
        summary = (
            f"Upload complete — "
            f"{results['created']} created, "
            f"{results['updated']} updated, "
            f"{results['skipped']} skipped "
            f"out of {results['total_rows']} rows."
        )

        if results['errors']:
            messages.warning(request, summary)
        else:
            messages.success(request, summary)

        return render(request, self.template_name, {
            'form': StudentBulkUploadForm(),
            'results': results,
            'summary': summary,
        })


# ─── Sample CSV Download ─────────────────────────────────────────────────────

@login_required(login_url='login')
@user_passes_test(_is_staff_or_superuser, login_url='login')
@require_GET
def download_sample_csv(request):
    """
    Returns a pre-filled sample CSV for staff to use as a template.
    """
    csv_content = generate_sample_csv()
    response = HttpResponse(csv_content, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="kwikschools_student_upload_template.csv"'
    return response


# ─── AJAX: validate headers only (optional progressive enhancement) ──────────

@login_required(login_url='login')
@user_passes_test(_is_staff_or_superuser, login_url='login')
def ajax_validate_csv_headers(request):
    """
    Light-weight AJAX endpoint: receives a CSV file and returns
    header validation result so the user gets instant feedback
    before full upload.
    """
    if request.method != 'POST':
        return JsonResponse({'valid': False, 'error': 'POST only.'}, status=405)

    uploaded = request.FILES.get('csv_file')
    if not uploaded:
        return JsonResponse({'valid': False, 'error': 'No file received.'})

    try:
        import csv as csv_mod
        import io
        from .forms import REQUIRED_HEADERS

        content = uploaded.read().decode('utf-8-sig')
        reader = csv_mod.DictReader(io.StringIO(content))
        headers = [h.strip() for h in (reader.fieldnames or [])]
        missing = [h for h in REQUIRED_HEADERS if h not in headers]

        if missing:
            return JsonResponse({
                'valid': False,
                'missing': missing,
                'message': f'Missing columns: {", ".join(missing)}'
            })

        rows = list(reader)
        return JsonResponse({
            'valid': True,
            'row_count': len(rows),
            'message': f'{len(rows)} data rows detected. All required headers found.',
        })

    except Exception as e:
        return JsonResponse({'valid': False, 'error': str(e)})


# Student Class Progress
@login_required
def class_progress(request, student_id=None):
    user = request.user

    if user.is_superuser or user.groups.filter(name__in=['Admin', 'Teacher']).exists():
        # Staff viewing any student
        if not student_id:
            raise PermissionDenied("Student ID required for staff view.")
        student = get_object_or_404(Student, pk=student_id)

    else:
        # Regular student viewing their own progress
        student = get_object_or_404(Student, user=user)
        if student_id and int(student_id) != student.id:
            raise PermissionDenied("You can only view your own progress.")

    history = student.get_class_history()

    context = {
        'student': student,
        'history': history,
        'is_staff_view': user.is_superuser or user.groups.filter(name__in=['Admin', 'Teacher']).exists(),
    }
    return render(request, 'students/class_progress.html', context)