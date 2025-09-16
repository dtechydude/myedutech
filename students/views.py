from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Count, Sum, Q
import datetime
#converting html to pdf
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
# from xhtml2pdf import pisa
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from students.models import Student, Hostel, Parent
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
            'Full Name', 'DOB', 'Student Email', 'Student Phone', 
            'Guardian Phone', 'Guardian Email', 'Current Class', 'Student Status'
        ])

        for student in students_to_export:
            writer.writerow([
                student.get_full_name(),
                student.DOB.strftime('%Y-%m-%d'),
                student.user.email,
                student.user.profile.phone,
                student.guardian_phone,
                student.guardian_email,
                student.current_class.name if student.current_class else '',
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
        'boarder_student': boarder_student
    }

    if request.user.is_superuser or request.user.is_staff:
        return render(request, 'students/student_boarder_list.html', context)
    else:
        return render(request, 'pages/portal_home.html')

# GRADUATED Students List
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
    """
    Filters students by class, allows selecting multiple students,
    and changes their status to 'graduated' in a batch.
    """
    students = Student.objects.none()
    selected_standard = None
    
    if request.method == 'POST':
        selected_student_ids = request.POST.getlist('selected_students')
        standard_id = request.POST.get('standard_id')

        if not selected_student_ids:
            messages.error(request, "Please select at least one student to graduate.")
            return redirect('graduate_students')

        try:
            with transaction.atomic():
                students_to_graduate = Student.objects.filter(id__in=selected_student_ids)
                count = students_to_graduate.count()
                
                students_to_graduate.update(student_status='graduated')
                
            messages.success(request, f"Successfully graduated {count} students.")

        except Exception as e:
            messages.error(request, f"An error occurred: {e}")

        return redirect('students:graduate_students')
    
    # GET request
    standard_id_param = request.GET.get('standard')
    if standard_id_param:
        selected_standard = get_object_or_404(Standard, id=standard_id_param)
        # Filter active students in the selected class
        students = Student.objects.filter(current_class=selected_standard).exclude(student_status='graduated').order_by('last_name')

    standards = Standard.objects.all().order_by('name')

    context = {
        'standards': standards,
        'students': students,
        'selected_standard': selected_standard,
        'title': 'Graduate Students To Alumni',
    }
    return render(request, 'students/graduate_students.html', context)
    

 # Hostel List
@login_required
def hostel_list(request):
    hostel_list = Hostel.objects.all()
    # boarder_student = Student.objects.all().order_by('-date_admitted')

    context ={
        'hostel_list': hostel_list,
    }         
    
    return render(request, 'students/hostel_list.html', context)
    


# Student Search Query App
def student_search_list(request):
    student = Student.objects.all()
    
     # PAGINATOR METHOD
    page = request.GET.get('page', 1)
    paginator = Paginator(student, 30)
    try:
        student = paginator.page(page)
    except PageNotAnInteger:
        student = paginator.page(1)
    except EmptyPage:
        student = paginator.page(paginator.num_pages)

    return render(request, 'students/search_student_list.html', {'student': student })

# Define function to search student
def search(request):
    results = []

    if request.method == "GET":
        query = request.GET.get('search')

        if query == '':
            query = 'None'

        results = Student.objects.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(current_class__name__icontains=query) | Q(guardian_name__icontains=query) | Q(user__username__icontains=query) | Q(USN__icontains=query))
        # results = Student.objects.filter(Q(full_name__icontains=query))
        
    return render(request, 'students/search.html', {'query': query, 'results': results})

#count students in each class
@login_required
def student_in_class(request):
    students = Student.objects.all()
    student_no = Student.objects.filter().order_by('current_class').values('current_class__name').annotate(count=Count('current_class__name'))

    try:
        num_inclass = Student.objects.filter(standard__name = request.user.student.standard).count()
    except Student.DoesNotExist:
        num_inclass = Student.objects.filter()

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


# class StudentUpdateView(LoginRequiredMixin, UpdateView):
#     form_class = StudentUpdateForm
#     template_name = 'students/student_update_form.html'
#     # queryset = StudentDetail.objects.all()


#     def get_object(self):
#         id_ = self.kwargs.get("id")
#         return get_object_or_404(Student, USN=id_)

#     def form_valid(self, form):
#         print(form.cleaned_data)
        return super().form_valid(form)
    
# new student update form
class StudentUpdateView(LoginRequiredMixin, UpdateView):
    template_name = 'students/student_update_form.html'
    
    def get_object(self, queryset=None):
        """
        Retrieves the student object based on the URL parameter (usn).
        """
        usn = self.kwargs.get("usn")
        return get_object_or_404(Student, USN=usn)

    def get_form_class(self):
        # ... (rest of your get_form_class method is correct)
        if self.request.user.is_superuser or self.request.user.is_staff:
            return SuperUserStudentUpdateForm
        return StudentUpdateForm

    def get_success_url(self):
        """
        Defines the URL to redirect to after a successful form submission.
        """
        # Make sure this also uses 'usn'
        return reverse_lazy('students:student-detail', kwargs={'usn': self.object.USN})

     

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
    """
    Displays a printable ID card for a specific student.
    """
    def get(self, request, student_id):
        student = get_object_or_404(Student, id=student_id)
        
        # Get the SchoolIdentity. Assuming there is only one instance.
        # If there can be multiple, you may need a different retrieval method.
        try:
            school_identity = SchoolIdentity.objects.first()
        except SchoolIdentity.DoesNotExist:
            school_identity = None

        context = {
            'student': student,
            'school_identity': school_identity,
        }
        return render(request, 'students/test_student_id_card.html', context)


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
        next_class_options = Standard.objects.filter(
            promotion_order__gt=from_class.promotion_order
        ).order_by('promotion_order')

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



# Parent Logic
@login_required
def parent_dashboard(request):
    try:
        parent = Parent.objects.get(user=request.user)
        children = Student.objects.filter(parent=parent).prefetch_related('scores__term')
    except Parent.DoesNotExist:
        children = []
    
    children_with_reports = []
    all_terms = Term.objects.all().order_by('id')
    all_sessions = Session.objects.all().order_by('id')
    
    for child in children:
        child_data = {
            'child': child,
            'termly_reports': [],
            'session_reports': [],
            'payment_summary': {},
        }
        
        # Check for available termly reports
        for term in all_terms:
            if child.scores.filter(term=term).exists():
                child_data['termly_reports'].append(term)
        
        # Check for available session reports
        for session in all_sessions:
            if child.scores.filter(term__session=session).exists():
                child_data['session_reports'].append(session)
        
        # Get all unique completed payments for the child
        completed_payments = Payment.objects.filter(
            student=child,
            status='completed'
        ).values(
            'payment_category', 'term', 'session'
        ).annotate(
            total_paid=Sum('amount_received')
        ).order_by('payment_category__name')

        for payment_item in completed_payments:
            try:
                # Find the corresponding CategoryFee to get the total amount due
                category_fee = CategoryFee.objects.get(
                    payment_category__id=payment_item['payment_category'],
                    term__id=payment_item['term'],
                    session__id=payment_item['session']
                )
                amount_due = category_fee.amount_due
                balance = amount_due - payment_item['total_paid']

                child_data['payment_summary'][category_fee.id] = {
                    'category_fee': category_fee,
                    'total_paid': payment_item['total_paid'],
                    'balance': balance,
                }
            except CategoryFee.DoesNotExist:
                # Handle cases where a payment exists but the corresponding fee is deleted
                pass

        children_with_reports.append(child_data)
        
    # Fetch SchoolIdentity
    try:
        school_identity = SchoolIdentity.objects.first()
    except SchoolIdentity.DoesNotExist:
        school_identity = None
    
    context = {
        'children_with_reports': children_with_reports,
        'school_identity': school_identity,
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
        school_identity = SchoolIdentity.objects.first()
    except SchoolIdentity.DoesNotExist:
        school_identity = None
    
    context = {
        'page_obj': page_obj,
        'query': query,
        'school_identity': school_identity,
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



# # Parent List
# @staff_member_required
# def parent_list_view(request):
#     query = request.GET.get('q', '')
    
#     parents_list = Parent.objects.all().prefetch_related('children')
    
#     if query:
#         parents_list = parents_list.filter(
#             Q(guardian_name__icontains=query) |
#             Q(guardian_email__icontains=query) |
#             Q(user__username__icontains=query) |
#             Q(children__first_name__icontains=query) |
#             Q(children__last_name__icontains=query)
#         ).distinct()

#     paginator = Paginator(parents_list, 10)
#     page_number = request.GET.get('page')
#     page_obj = paginator.get_page(page_number)

#     # Get the school identity to pass to the template
#     try:
#         school_identity = SchoolIdentity.objects.first()
#     except SchoolIdentity.DoesNotExist:
#         school_identity = None
    
#     context = {
#         'page_obj': page_obj,
#         'query': query,
#         'school_identity': school_identity  # Pass the school identity to the context
#     }
#     return render(request, 'students/parent_list.html', context)


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