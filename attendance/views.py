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
from curriculum.models import Session, Term, Standard
from decimal import Decimal
from .forms import AttendanceDateForm, AttendanceForm, AttendanceReportForm # Import new forms
import json
from django.http import HttpResponseForbidden, Http404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import logging
from attendance.services import get_student_attendance
from .models import AttendanceConfiguration, AttendanceSummary
from .forms import AttendanceConfigurationForm
from django.forms import formset_factory
from .forms import SimpleAttendanceEntryForm




# ======================================================
# ATTENDANCE AUTHORIZATION HELPERS
# ======================================================

def _is_staff_or_superuser(user):
    """
    Returns True for any Admin or Staff user.
    """
    return user.is_authenticated and (
        user.is_staff or user.is_superuser
    )


def get_teacher_profile(user):
    """
    Returns the Teacher profile for a logged-in user.
    """
    try:
        return Teacher.objects.get(user=user)
    except Teacher.DoesNotExist:
        return None

# Helper to get teacher profile, handles not found case
# def get_teacher_profile(user):
#     try:
#         return user.teacher
#     except Teacher.DoesNotExist:
#         return None



@login_required
def take_daily_attendance(request):
    teacher = get_teacher_profile(request.user)
    if not teacher:
        messages.error(request, "You are not authorized to view this page as a teacher.")
        return redirect('/dashboard/')

    date_form = AttendanceDateForm(request.GET or None)
    selected_date = timezone.localdate()
    if date_form.is_valid():
        selected_date = date_form.cleaned_data['date']

    # Weekend/holiday block (unchanged from earlier)
    from curriculum.models import Term
    from curriculum.services import is_non_schooling_day

    matching_term = Term.objects.filter(start_date__lte=selected_date, end_date__gte=selected_date).first()
    if matching_term and is_non_schooling_day(matching_term, selected_date):
        reason = "a weekend" if selected_date.weekday() >= 5 else "a public holiday"
        messages.error(request, f"{selected_date.strftime('%A, %B %d, %Y')} is {reason}. Attendance cannot be taken for this date.")
        empty_formset = formset_factory(SimpleAttendanceEntryForm, extra=0)(initial=[])
        return render(request, 'attendance/test2_take_attendance.html', {
            'date_form': date_form, 'formset': empty_formset,
            'selected_date': selected_date, 'teacher': teacher,
        })

    students = Student.objects.filter(form_teacher=teacher).order_by('first_name', 'last_name')

    # READ existing records for display only — never writes.
    existing = {
        a.student_id: a.present
        for a in Attendance.objects.filter(student__in=students, date=selected_date)
    }

    AttendanceFormSet = formset_factory(SimpleAttendanceEntryForm, extra=0)

    if request.method == 'POST':
        formset = AttendanceFormSet(request.POST)
        if formset.is_valid():
            with transaction.atomic():
                for form in formset:
                    student_id = form.cleaned_data['student']
                    present = form.cleaned_data['present']
                    Attendance.objects.update_or_create(
                        student_id=student_id,
                        date=selected_date,
                        defaults={'present': present}
                    )
            messages.success(request, f"Attendance for {selected_date.strftime('%Y-%m-%d')} saved successfully!")
            return redirect(f"{request.path}?date={selected_date}")
        else:
            messages.error(request, "There were errors saving attendance. Please check the form.")
    else:
        initial_data = [
            {
                'student': student.id,
                'student_full_name': student.get_full_name(),
                'present': existing.get(student.id, False),
            }
            for student in students
        ]
        formset = AttendanceFormSet(initial=initial_data)

    context = {
        'date_form': date_form,
        'formset': formset,
        'selected_date': selected_date,
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
        # attendance_records = Attendance.objects.filter(
        #     student=current_student,
        #     date__gte=current_term.start_date, 
        #     date__lte=current_term.end_date 
        # )
        
        # # 4. Calculate Summary (relies on 'present' boolean field in Attendance model)
        # days_present = attendance_records.filter(present=True).count()
        # days_absent = attendance_records.filter(present=False).count()
        # total_days = days_present + days_absent
        
        # # 5. Calculate Attendance Percentage
        # percent_present = 0.0
        # if total_days > 0:
        #     percent_present = round((days_present / total_days) * 100, 1)

        attendance_info = get_student_attendance(
            student=current_student,
            session=current_session,
            term=current_term
        )

        days_present = attendance_info['days_present']
        days_absent = attendance_info['days_absent']
        total_days = attendance_info['total_days']
        percent_present = attendance_info['attendance_percentage']
        attendance_source = attendance_info['source']

        # 6. Build Context
        context.update({
            'attendance_source': attendance_source, # new logic
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
        # attendance_records = Attendance.objects.filter(
        #     student=current_student,
        #     date__gte=current_term.start_date, 
        #     date__lte=current_term.end_date 
        # )
        
        # # 3. Calculate Summary (relies on 'present' boolean field in Attendance model)
        # days_present = attendance_records.filter(present=True).count()
        # days_absent = attendance_records.filter(present=False).count()
        # total_days = days_present + days_absent
        
        # # 4. Calculate Attendance Percentage
        # percent_present = 0.0
        # if total_days > 0:
        #     percent_present = round((days_present / total_days) * 100, 1)

        attendance_info = get_student_attendance(
            student=current_student,
            session=current_session,
            term=current_term
        )

        days_present = attendance_info['days_present']
        days_absent = attendance_info['days_absent']
        total_days = attendance_info['total_days']
        percent_present = attendance_info['attendance_percentage']
        attendance_source = attendance_info['source']

        # 5. Build Context
        context.update({
            'attendance_source': attendance_source, #new logic
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

        #new----------------------
        from curriculum.models import Term
        from curriculum.services import is_non_schooling_day

        matching_term = Term.objects.filter(start_date__lte=today, end_date__gte=today).first()
        if matching_term and is_non_schooling_day(matching_term, today):
            reason = "a weekend" if today.weekday() >= 5 else "a public holiday"
            return JsonResponse({
                'status': 'error',
                'message': f"Today is {reason}. Attendance scanning is disabled."
            }, status=200)

        #--------------------------------------

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




@login_required
def attendance_summary_class_bulk(request):
    """
    Bulk manual attendance entry for a whole class, per session+term.
    days_present is the only value a teacher enters — days_absent is
    ALWAYS derived (config.total_school_days - days_present), never
    entered directly, so it can never conflict with the configured
    total school days for the term.

    Access: staff/superuser (any class), or the class's form teacher
    (own class only).
    """
      
    user = request.user

    # ======================================================
    # ADMIN / STAFF USERS
    # ======================================================

    if user.is_staff or user.is_superuser:

        available_standards = (
            Standard.objects
            .all()
            .order_by("name")
        )

    # ======================================================
    # FORM TEACHERS
    # ======================================================

    else:

        teacher = get_teacher_profile(user)

        if teacher is None:
            messages.error(
                request,
                "You are not authorized to manage attendance."
            )
            return redirect("/dashboard/")

        available_standards = (
            Standard.objects.filter(
                students__form_teacher=teacher
            )
            .distinct()
            .order_by("name")
        )

    # ======================================================
    # NO CLASS ASSIGNED
    # ======================================================

    if not available_standards.exists():

        messages.warning(
            request,
            "No class has been assigned to you."
        )

        return redirect("/dashboard/")

    sessions = Session.objects.all().order_by('-start_date')

    session_id = request.GET.get('session') or request.POST.get('session_id')
    standard_id = request.GET.get('standard') or request.POST.get('standard_id')
    term_id = request.GET.get('term') or request.POST.get('term_id')

    session = get_object_or_404(sessions, id=session_id) if session_id else sessions.first()
    standard = get_object_or_404(available_standards, id=standard_id) if standard_id else available_standards.first()
    terms_in_session = Term.objects.filter(session=session).order_by('start_date') if session else Term.objects.none()
    term = get_object_or_404(terms_in_session, id=term_id) if term_id else terms_in_session.first()

    config = AttendanceConfiguration.objects.filter(session=session, term=term).first() if session and term else None

    rows = []
    if session and term and standard:
        students = Student.objects.filter(current_class=standard).order_by('last_name', 'first_name')

        if request.method == 'POST':
            if not config:
                messages.error(
                    request,
                    "Set the total school days for this session/term in Attendance Configuration "
                    "before entering manual attendance."
                )
                return redirect(f"{request.path}?session={session.id}&term={term.id}&standard={standard.id}")

            updated_count = 0
            for student in students:
                present_val = request.POST.get(f'days_present_{student.id}', '').strip()
                remarks_val = request.POST.get(f'remarks_{student.id}', '').strip()

                if present_val == '':
                    continue  # blank — keep using daily records for this student

                days_present = min(int(present_val) if present_val.isdigit() else 0, config.total_school_days)
                days_absent = max(config.total_school_days - days_present, 0)  # always derived

                summary, _ = AttendanceSummary.objects.get_or_create(
                    student=student, session=session, term=term,
                    defaults={'entered_by': user}
                )
                summary.days_present = days_present
                summary.remarks = remarks_val
                summary.entered_by = user
                summary.save()
                updated_count += 1

            messages.success(request, f"Saved manual attendance for {updated_count} student(s).")
            return redirect(f"{request.path}?session={session.id}&term={term.id}&standard={standard.id}")

        existing = {
            s.student_id: s for s in AttendanceSummary.objects.filter(
                student__in=students, session=session, term=term
            )
        }
        rows = [{'student': s, 'summary': existing.get(s.id)} for s in students]

    context = {
        'sessions': sessions, 'available_standards': available_standards,
        'terms_in_session': terms_in_session, 'session': session,
        'standard': standard, 'term': term, 'config': config, 'rows': rows,
    }
    return render(request, 'attendance/attendance_summary_class_bulk.html', context)