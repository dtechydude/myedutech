from django.shortcuts import render, redirect, get_object_or_404
from django.forms import modelformset_factory
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.utils import timezone
from django.contrib import messages # Import messages for error handling
from .models import Attendance
from students.models import Student
from datetime import date, timedelta # Make sure to import these!
from staff.models import Teacher
from curriculum.models import Session, Term
from decimal import Decimal
from .forms import AttendanceDateForm, AttendanceForm, AttendanceReportForm # Import new forms
import json
from django.http import HttpResponseForbidden, Http404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import logging



# Helper to get teacher profile, handles not found case
def get_teacher_profile(user):
    try:
        return user.teacher
    except Teacher.DoesNotExist:
        return None

@login_required
def take_daily_attendance(request):
    teacher = get_teacher_profile(request.user)
    if not teacher:
        messages.error(request, "You are not authorized to view this page as a teacher.")
        return redirect('/dashboard/') # Redirect to a safe page or login

    # Initialize the date form
    date_form = AttendanceDateForm(request.GET or None)
    selected_date = timezone.localdate() # Default to today
    if date_form.is_valid():
        selected_date = date_form.cleaned_data['date']

    students = Student.objects.filter(form_teacher=teacher).order_by('first_name', 'last_name')

    initial_data = []
    for student in students:
        attendance_record, created = Attendance.objects.get_or_create(
            student=student,
            date=selected_date, # Use the selected_date
            defaults={'present': False}
        )
        initial_data.append({
            'id': attendance_record.id,
            'student': student.USN,
            'present': attendance_record.present,
            'student_full_name': student.get_full_name(),
        })

    AttendanceFormSet = modelformset_factory(
        Attendance,
        form=AttendanceForm,
        extra=0,
        can_delete=False
    )

    if request.method == 'POST':
        # Re-initialize date_form for POST context if needed, though usually not directly used here
        date_form = AttendanceDateForm(request.POST) # Just for validation if needed, not to change selected date for formset
        formset = AttendanceFormSet(request.POST, queryset=Attendance.objects.filter(pk__in=[d['id'] for d in initial_data]))

        # We should also ensure the date form is valid if it's part of the submission
        # In this setup, date is passed via GET for initial load, and only POST for attendance
        # If date could be changed on POST, you'd add: `if date_form.is_valid() and formset.is_valid():`
        if formset.is_valid():
            with transaction.atomic():
                for form in formset:
                    if form.cleaned_data:
                        form.save()
            messages.success(request, f"Attendance for {selected_date.strftime('%Y-%m-%d')} saved successfully!")
            # Redirect to the same page with the selected date to show updated status
            return redirect('attendance:take_daily_attendance')
        else:
            messages.error(request, "There were errors saving attendance. Please check the form.")
            print(formset.errors)
            print(formset.non_form_errors())
    else:
        formset = AttendanceFormSet(queryset=Attendance.objects.filter(pk__in=[d['id'] for d in initial_data]))
        for i, form in enumerate(formset):
            form.initial['student_full_name'] = initial_data[i]['student_full_name']

    context = {
        'date_form': date_form, # Pass the date form to the template
        'formset': formset,
        'selected_date': selected_date, # Pass the selected date for display
        'teacher': teacher,
    }
    return render(request, 'attendance/test2_take_attendance.html', context)



# ATTENDANCE REPORT
login_required
def attendance_report(request):
    # ... (initial setup remains unchanged) ...
    current_user = request.user
    teacher = None

    is_superuser = current_user.is_superuser

    if not is_superuser:
        try:
            teacher = Teacher.objects.get(user=current_user)
        except Teacher.DoesNotExist:
            pass
    
    report_form = AttendanceReportForm(request.GET or None, teacher=teacher, is_superuser=is_superuser)
    
    attendance_data = {}
    student_attendance_summary = {} 
    
    today = date.today()
    default_start_date = today - timedelta(days=6)
    default_end_date = today

    context_start_date = default_start_date
    context_end_date = default_end_date
    selected_student_id = None

    if report_form.is_valid():
        form_start_date = report_form.cleaned_data.get('start_date')
        form_end_date = report_form.cleaned_data.get('end_date')
        selected_student = report_form.cleaned_data.get('student')
        
        # NEW: Get the selected class filter
        selected_class = report_form.cleaned_data.get('current_class')

        if form_start_date:
            context_start_date = form_start_date
        if form_end_date:
            context_end_date = form_end_date

        if selected_student:
            selected_student_id = selected_student.id

        attendance_records_query = Attendance.objects.filter(
            date__range=(context_start_date, context_end_date)
        )
        
        # Determine the base set of students to report on (Teacher/Superuser/Selected Student)
        students_to_report = Student.objects.all()

        if selected_student:
            students_to_report = students_to_report.filter(pk=selected_student.pk)
        elif not is_superuser and teacher:
            students_to_report = students_to_report.filter(form_teacher=teacher)

        # NEW: Apply the class filter to the student set
        if selected_class:
            students_to_report = students_to_report.filter(current_class=selected_class)
            
        # Filter the attendance records by the final list of students
        attendance_records_query = attendance_records_query.filter(student__in=students_to_report)


        for record in attendance_records_query.order_by('student__last_name', 'date'):
            # ... (data processing loop remains unchanged) ...
            student = record.student
            record_date = record.date

            if student not in attendance_data:
                attendance_data[student] = {}
                student_attendance_summary[student] = {'present': 0, 'absent': 0, 'total_days': 0}

            attendance_data[student][record_date] = record
            
            if record.present:
                student_attendance_summary[student]['present'] += 1
            else:
                student_attendance_summary[student]['absent'] += 1
            student_attendance_summary[student]['total_days'] += 1

    # ... (context remains unchanged) ...
    context = {
        'report_form': report_form,
        'attendance_data': attendance_data,
        'selected_student_id': selected_student_id,
        'start_date': context_start_date,
        'end_date': context_end_date,
        'teacher': teacher,
        'is_superuser': is_superuser,
        'student_attendance_summary': student_attendance_summary,
    }
    return render(request, 'attendance/test_attendance_report.html', context)


# STUDENT ATTENDANCE REPORT ADVANCE -ENABLES STUDENTS TO SEE THEIR ATTENDANCE BETTER

# =========================================================================
# HELPERS & AUTHORIZATION
# =========================================================================

def get_current_student(user):
    """Retrieves the Student profile linked to the logged-in user."""
    try:
        # Assuming Student model has a OneToOneField or ForeignKey to auth.User
        return Student.objects.get(user=user)
    except Student.DoesNotExist:
        raise Http404("Student profile not found for this user.")

def is_authorized_to_view_student(user, student_id):
    """
    Checks if the user is authorized (Staff, Form Teacher, or the Student themselves) 
    to view the specified student's records.
    """
    if not user.is_authenticated:
        return False
        
    # 1. Allow Admins/Staff
    if user.is_staff:
        return True
    
    try:
        # Check student access (either form teacher or student themselves)
        student_profile = Student.objects.select_related('form_teacher__user').get(pk=student_id)
        
        # 2. Allow the Student themselves (Self-View)
        if hasattr(student_profile, 'user') and student_profile.user == user:
            return True
            
        # 3. Allow the Form Teacher
        if student_profile.form_teacher and student_profile.form_teacher.user == user:
            return True
            
    except Student.DoesNotExist:
        return False
        
    return False

# =========================================================================
# 1. STUDENT LIST VIEW (Roster for Staff/Teachers)
# =========================================================================

@login_required
def student_list_view(request):
    """
    Displays a list of students the logged-in user is authorized to see (All, Form Class, or Self).
    """
    user = request.user
    students = Student.objects.none()
    title = "Attendance Roster"
    
    # 1. Staff/Admin View (See All)
    if user.is_staff:
        students = Student.objects.select_related('current_class').all().order_by('current_class__name', 'first_name')
        title = "All Students Attendance Records"
    
    # 2. Teacher/Student View (Filtered)
    else:
        try:
            # Check if user is a Teacher/Form Teacher
            teacher_profile = Teacher.objects.get(user=user)
            
            # Filter students where the form_teacher is the logged-in user's Teacher profile
            students = Student.objects.filter(form_teacher=teacher_profile).select_related('current_class').order_by('current_class__name', 'first_name')
            title = f"Your Assigned Class Attendance"
            
        except Teacher.DoesNotExist:
            # If not a recognized Teacher profile, check if they are a Student viewing themselves
            try:
                # FIX: Corrected Student.objects.objects to Student.objects
                students = Student.objects.filter(user=user).select_related('current_class')
                title = "Your Attendance Record"
            except:
                # Still no match (e.g., a generic authenticated user)
                students = Student.objects.none() 
                title = "No Students Found"

    context = {
        'students': students,
        'title': title,
        'is_staff': user.is_staff,
    }
    return render(request, 'attendance/student_attendance_list.html', context)


# =========================================================================
# 2. STAFF/TEACHER: ATTENDANCE SUMMARY VIEW (Uses student_id from URL)
# =========================================================================

@login_required
def student_attendance_summary(request, student_id):
    """
    Shows the attendance summary for the student specified by student_id.
    """
    # 1. AUTHORIZATION CHECK: SECURITY FIRST
    if not is_authorized_to_view_student(request.user, student_id):
        return HttpResponseForbidden("You are not authorized to view this student's records.")
        
    context = {}
    current_student = get_object_or_404(Student, pk=student_id)

    try:
        # 2. Get the current active Session and Term
        current_session = Session.objects.get(is_current=True)
        current_term = Term.objects.get(is_current=True) 
        
        # 3. Filter Attendance Records using the date range of the current Term
        attendance_records = Attendance.objects.filter(
            student=current_student,
            date__gte=current_term.start_date, 
            date__lte=current_term.end_date 
        )
        
        # 4. Calculate Summary (relies on 'present' boolean field in Attendance model)
        days_present = attendance_records.filter(present=True).count()
        days_absent = attendance_records.filter(present=False).count()
        total_days = days_present + days_absent
        
        # 5. Calculate Attendance Percentage
        percent_present = 0.0
        if total_days > 0:
            percent_present = round((days_present / total_days) * 100, 1)

        # 6. Build Context
        context.update({
            'student': current_student,
            'days_present': days_present,
            'days_absent': days_absent,
            'total_days': total_days,
            'current_session': current_session,
            'current_term': current_term,
            'percent_present': percent_present,
        })
        
    except (Session.DoesNotExist, Term.DoesNotExist):
        context['error'] = "No current school session or term found for reporting."
    except Exception as e:
        context['error'] = f"An unexpected error occurred: {e}"

    return render(request, 'attendance/student_attendance_summary.html', context)


# =========================================================================
# 3. STAFF/TEACHER: ATTENDANCE DETAIL VIEW (Uses student_id from URL)
# =========================================================================

@login_required
def student_attendance_detail(request, student_id):
    """
    Displays a calendar view of the student's attendance records for the term.
    """
    # 1. AUTHORIZATION CHECK: SECURITY FIRST
    if not is_authorized_to_view_student(request.user, student_id):
        return HttpResponseForbidden("You are not authorized to view this student's records.")
    
    context = {}
    current_student = get_object_or_404(Student, pk=student_id)
    
    try:
        # 2. Get the current active Session and Term
        current_session = Session.objects.get(is_current=True)
        current_term = Term.objects.get(is_current=True) 

        # 3. Fetch all attendance records for the term
        attendance_records = Attendance.objects.filter(
            student=current_student,
            date__gte=current_term.start_date, 
            date__lte=current_term.end_date 
        ).order_by('date')

        # 4. Prepare data for JavaScript: { "YYYY-MM-DD": "Present" / "Absent" }
        # FIX: Uses the 'present' boolean field, which prevents the 'AttributeError: status'
        attendance_map = {}
        for record in attendance_records:
            date_str = record.date.strftime('%Y-%m-%d')
            status = "Present" if record.present else "Absent"
            attendance_map[date_str] = status

        # 5. Build Context
        context.update({
            'student': current_student,
            'current_session': current_session,
            'current_term': current_term,
            # Pass the map as a JSON string for safe use in JavaScript
            'attendance_data_json': json.dumps(attendance_map) 
        })
        
    except (Session.DoesNotExist, Term.DoesNotExist):
        context['error'] = "No current school session or term found for reporting."
    except Exception as e:
        context['error'] = f"An unexpected error occurred: {e}"
    
    return render(request, 'attendance/student_attendance_detail.html', context)


# =========================================================================
# 4. STUDENT SELF-SERVICE: SUMMARY VIEW (Does NOT use student_id from URL)
# =========================================================================

@login_required
def self_attendance_summary(request):
    """
    Allows a logged-in student to view their own attendance summary.
    This view uses the same logic as student_attendance_summary but gets the ID from the user.
    """
    # Get the student associated with the logged-in user
    try:
        current_student = get_current_student(request.user)
    except Http404:
        return redirect('pages:portal-home') # Redirect non-students
    
    # We now have the student object, we can apply the same logic as the staff view.
    context = {}

    try:
        # 1. Get the current active Session and Term
        current_session = Session.objects.get(is_current=True)
        current_term = Term.objects.get(is_current=True) 
        
        # 2. Filter Attendance Records using the date range of the current Term
        attendance_records = Attendance.objects.filter(
            student=current_student,
            date__gte=current_term.start_date, 
            date__lte=current_term.end_date 
        )
        
        # 3. Calculate Summary (relies on 'present' boolean field in Attendance model)
        days_present = attendance_records.filter(present=True).count()
        days_absent = attendance_records.filter(present=False).count()
        total_days = days_present + days_absent
        
        # 4. Calculate Attendance Percentage
        percent_present = 0.0
        if total_days > 0:
            percent_present = round((days_present / total_days) * 100, 1)

        # 5. Build Context
        context.update({
            'student': current_student,
            'days_present': days_present,
            'days_absent': days_absent,
            'total_days': total_days,
            'current_session': current_session,
            'current_term': current_term,
            'percent_present': percent_present,
        })
        
    except (Session.DoesNotExist, Term.DoesNotExist):
        context['error'] = "No current school session or term found for reporting."
    except Exception as e:
        context['error'] = f"An unexpected error occurred: {e}"

    return render(request, 'attendance/student_attendance_summary.html', context)


# =========================================================================
# 5. STUDENT SELF-SERVICE: DETAIL VIEW (Does NOT use student_id from URL)
# =========================================================================

@login_required
def self_attendance_detail(request):
    """
    Allows a logged-in student to view their own detailed attendance calendar.
    This view uses the same logic as student_attendance_detail but gets the ID from the user.
    """
    # Get the student associated with the logged-in user
    try:
        current_student = get_current_student(request.user)
    except Http404:
        return redirect('pages:portal-home') # Redirect non-students

    context = {}
    
    try:
        # 1. Get the current active Session and Term
        current_session = Session.objects.get(is_current=True)
        current_term = Term.objects.get(is_current=True) 

        # 2. Fetch all attendance records for the term
        attendance_records = Attendance.objects.filter(
            student=current_student,
            date__gte=current_term.start_date, 
            date__lte=current_term.end_date 
        ).order_by('date')

        # 3. Prepare data for JavaScript: { "YYYY-MM-DD": "Present" / "Absent" }
        attendance_map = {}
        for record in attendance_records:
            date_str = record.date.strftime('%Y-%m-%d')
            status = "Present" if record.present else "Absent"
            attendance_map[date_str] = status

        # 4. Build Context
        context.update({
            'student': current_student,
            'current_session': current_session,
            'current_term': current_term,
            # Pass the map as a JSON string for safe use in JavaScript
            'attendance_data_json': json.dumps(attendance_map) 
        })
        
    except (Session.DoesNotExist, Term.DoesNotExist):
        context['error'] = "No current school session or term found for reporting."
    except Exception as e:
        context['error'] = f"An unexpected error occurred: {e}"
    
    return render(request, 'attendance/student_attendance_detail.html', context)


# Scan Attendance ID

@login_required
def attendance_scanner_view(request):
    today = timezone.now().date()
    total_students = Student.objects.count()
    present_count = Attendance.objects.filter(date=today, present=True).count()
    
    return render(request, 'attendance/attendance_scanner.html', {
        'total_students': total_students,
        'present_count': present_count,
    })



@csrf_exempt
@login_required
def scan_attendance_ajax(request, usn):
    # Clean the USN (remove spaces and convert to uppercase to match DB)
    clean_usn = usn.strip()
    
    try:
        # We use __iexact to ignore case (e.g., 'student036' vs 'STUDENT036')
        # student = Student.objects.get(USN__iexact=clean_usn)
        student = Student.objects.get(USN__iexact=usn.strip())
        today = timezone.now().date()

        attendance, created = Attendance.objects.get_or_create(
            student=student,
            date=today,
            defaults={'present': True}
        )

        if not created and not attendance.present:
            attendance.present = True
            attendance.save()

        # Get updated count for the UI
        current_present = Attendance.objects.filter(date=today, present=True).count()

        return JsonResponse({
            'status': 'success', 
            'message': f'{student.get_full_name()} marked Present',
            'present_count': current_present
        })
        
    except Student.DoesNotExist:
        # This tells us exactly what USN the server tried to find
        return JsonResponse({
            'status': 'error', 
            'message': f'ID "{clean_usn}" not found in database.'
        }, status=200) # Use 200 so our JS handles the error message nicely