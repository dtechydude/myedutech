from django.shortcuts import render, redirect, get_object_or_404
from django.forms import modelformset_factory
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from django.contrib import messages # Import messages for error handling
from .models import Attendance
from students.models import Student
from staff.models import Teacher
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
    return render(request, 'attendance/take_attendance.html', context)

@login_required
def attendance_report(request):
    teacher = get_teacher_profile(request.user)
    if not teacher:
        messages.error(request, "You are not authorized to view this page as a teacher.")
        return redirect('/dashboard/')

    report_form = AttendanceReportForm(teacher=teacher, data=request.GET or None) # Pass teacher to form for queryset
    attendance_data = {} # Dictionary to hold structured report data

    if report_form.is_valid():
        student_filter = report_form.cleaned_data.get('student')
        start_date = report_form.cleaned_data.get('start_date')
        end_date = report_form.cleaned_data.get('end_date')

        # Build query for attendance records
        attendance_records_query = Attendance.objects.filter(
            student__form_teacher=teacher, # Filter by teacher's students
            date__range=[start_date, end_date]
        ).select_related('student').order_by('student__first_name', 'student__last_name', 'date')

        if student_filter:
            attendance_records_query = attendance_records_query.filter(student=student_filter)

        # Structure data for the template
        # Key: Student object, Value: Dictionary of {date: Attendance object}
        for record in attendance_records_query:
            if record.student not in attendance_data:
                attendance_data[record.student] = {}
            attendance_data[record.student][record.date] = record

    context = {
        'report_form': report_form,
        'attendance_data': attendance_data,
        'teacher': teacher,
    }
    return render(request, 'attendance/attendance_report.html', context)

# You can keep the attendance_success view or remove it and just use messages.success
# @login_required
# def attendance_success(request):
#     return render(request, 'myapp/attendance_success.html')
