from django.shortcuts import render, redirect, get_object_or_404
from django.forms import modelformset_factory
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.contrib import messages # Import messages for error handling
from .models import Attendance
from students.models import Student
from datetime import date, timedelta # Make sure to import these!
from staff.models import Teacher
from curriculum.models import SchoolIdentity
from .forms import AttendanceDateForm, AttendanceForm, AttendanceReportForm # Import new forms

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