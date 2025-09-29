from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse, reverse_lazy
from django.db.models import F, Sum, Q
from transport.models import Route, StudentOnRoute, BusPayment
from transport.forms import StudentOnRouteForm, BusEnrollmentForm, BusPaymentForm, BusEnrollmentForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
import os
from students.models import Student
from curriculum.models import Session, Term, SchoolIdentity
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from decimal import Decimal # ⬅️ Import the Decimal class




# bus route list
@login_required
def bus_route_list(request):
    routelist = Route.objects.all()

    context = {
        'routelist': routelist,

    }
    return render (request, 'transport/bus_route_list.html', context )


# Students Approved On Bus
@login_required
def student_on_bus(request): 
    student_on_bus = StudentOnRoute.objects.all()   

    context = {
        'student_on_bus' : student_on_bus,              

    }
    
    return render (request, 'transport/student_onbus.html', context )

@login_required
def sign_up_bus(request):
    if request.method == 'POST':
        # If you are saving data from the form
        form = StudentOnRouteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('transport:bus_signup_success') # Redirect to a success page
    else:
        # For a GET request, create an empty form
        # If you're editing an existing StudentOnRoute object:
        # student_on_route_instance = StudentOnRoute.objects.get(some_condition)
        # form = StudentOnRouteForm(instance=student_on_route_instance)
        # Otherwise, for a new signup:
        form = StudentOnRouteForm()

    return render(request, 'transport/signup_for_bus.html', {'form': form})


@login_required
def submission_success(request):
    return render(request, 'transport/bus_signup_success.html')


@login_required
def bus_signup_list(request):
    """
    Displays a list of all bus signups.
    """
    # 🆕 Corrected field name from 'signup_date' to 'created_at'
    student_signups = StudentOnRoute.objects.all().select_related('student', 'route').order_by('created_at')

    context = {
        'student_signups': student_signups,
        'page_title': "Bus Signups"
    }
    return render(request, 'transport/bus_signup_list.html', context)


# students see their route details
@login_required
def student_own_route_detail(request):
    """
    Displays the bus route details for the currently logged-in student.
    """
    try:
        # Step 1: Get the Student object associated with the current User
        # The 'user' field on your Student model should be a OneToOneField to the User model
        current_student = Student.objects.get(user=request.user)

        # Step 2: Use the Student object to filter the StudentOnRoute model
        student_signup = StudentOnRoute.objects.select_related('route').get(student=current_student)
        
    except Student.DoesNotExist:
        # Handle the case where the logged-in user is not a Student
        student_signup = None
    except StudentOnRoute.DoesNotExist:
        # Handle the case where the student is not enrolled on a route
        student_signup = None

    context = {
        'student_signup': student_signup
    }
    return render(request, 'transport/student_own_route_detail.html', context)


# staff sign up for student
def is_staff_or_superuser(user):
    return user.is_staff or user.is_superuser

# Student-specific signup view
@login_required
def student_bus_signup_view(request):
    """
    Allows a logged-in student to sign themselves up for a bus route.
    """
    current_student = get_object_or_404(Student, user=request.user)

    if request.method == 'POST':
        form = BusEnrollmentForm(request.POST, request=request)
        if form.is_valid():
            enrollment = form.save(commit=False)
            enrollment.is_active = True
            enrollment.save()
            messages.success(request, 'Successfully signed up for the bus route!')
            return redirect('transport:payment_pass', enrollment_id=enrollment.id)
    else:
        form = BusEnrollmentForm(request=request)

    context = {
        'form': form,
        'student': current_student
    }
    return render(request, 'transport/test_bus_signup.html', context)


# Staff-specific signup view
@user_passes_test(is_staff_or_superuser)
def staff_bus_signup_view(request):
    """
    Allows staff members to sign up a student on their behalf.
    """
    if request.method == 'POST':
        form = BusEnrollmentForm(request.POST, request=request)
        if form.is_valid():
            enrollment = form.save(commit=False)
            enrollment.is_active = True
            enrollment.save()
            messages.success(request, 'Student successfully signed up for the bus route!')
            return redirect('transport:payment_pass', enrollment_id=enrollment.id)
    else:
        form = BusEnrollmentForm(request=request)

    context = {
        'form': form,
        'student': None,  # No single student context for staff view
    }
    return render(request, 'transport/test_bus_signup.html', context)


# Common view for payment pass, accessible by both student and staff
def student_payment_pass_view(request, enrollment_id):
    """
    Displays a student's bus payment pass, with an option for a printable version.
    """
    enrollment = get_object_or_404(StudentOnRoute, id=enrollment_id)
    payments = BusPayment.objects.filter(enrollment=enrollment, is_approved=True)
    
    total_paid_float = payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0.0
    
    # 🆕 Convert the total_paid float to a Decimal object
    total_paid = Decimal(str(total_paid_float))
    
    # 🆕 Now perform the subtraction with both values as Decimals
    balance = enrollment.route.bus_fee - total_paid
    is_fully_paid = balance <= 0
    
    try:
        school_info = SchoolIdentity.objects.first()
    except SchoolIdentity.DoesNotExist:
        school_info = None

    if 'printable' in request.GET:
        context = {
            'enrollment': enrollment,
            'balance': balance,
            'total_paid': total_paid,
            'is_fully_paid': is_fully_paid,
            'school_info': school_info,
        }
        return render(request, 'transport/test_printable_bus_pass.html', context)
    
    payment_form = None
    if not is_fully_paid:
        if request.method == 'POST':
            payment_form = BusPaymentForm(request.POST)
            if payment_form.is_valid():
                payment = payment_form.save(commit=False)
                payment.enrollment = enrollment
                payment.save()
                messages.success(request, "Payment has been recorded successfully.")
                return redirect('transport:payment_pass', enrollment_id=enrollment.id)
        else:
            payment_form = BusPaymentForm()

    context = {
        'enrollment': enrollment,
        'balance': balance,
        'total_paid': total_paid,
        'is_fully_paid': is_fully_paid,
        'payment_form': payment_form,
        'school_info': school_info,
    }
    return render(request, 'transport/test_student_payment_pass.html', context)


# staff enroll student for bus
def is_staff_or_superuser(user):
    return user.is_staff or user.is_superuser

def bus_enrollment_list_view(request):
    """
    Displays a list of all bus enrollments, including payment status.
    """
    enrollments = StudentOnRoute.objects.all().select_related('student', 'route')

    # Add payment details to each enrollment object
    for enrollment in enrollments:
        # Get total paid by this student for this enrollment
        total_paid_float = BusPayment.objects.filter(
            # Assuming 'enrollment' is the correct ForeignKey name in BusPayment model
            enrollment=enrollment,
            is_approved=True
        ).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0.0

        # Convert the float result from aggregate to a Decimal for accurate math
        total_paid = Decimal(str(total_paid_float))

        # --- THE FIX: Assign the calculated total paid to the enrollment object ---
        enrollment.total_paid = total_paid  # <--- THIS IS THE MISSING LINE

        # Now, perform the balance subtraction with both operands as Decimal
        # Note: If enrollment.route.bus_fee is a DecimalField, Decimal(str()) is not strictly needed for it.
        enrollment.balance = enrollment.route.bus_fee - total_paid

        # Calculate a more readable status (this part is not used in the table)
        if enrollment.balance <= 0:
            enrollment.payment_status = "Paid in Full"
            enrollment.status_class = "text-success"
        else:
            enrollment.payment_status = f"Balance: ${enrollment.balance}"
            enrollment.status_class = "text-danger"

    context = {
        'enrollments': enrollments,
        'page_title': "Bus Enrollments"
    }
    return render(request, 'transport/test_bus_enrollment_list.html', context)


@login_required
def my_payment_pass_redirect_view(request):
    """
    Redirects a logged-in student to their specific bus payment pass page.
    """
    try:
        # Get the student object for the logged-in user
        current_student = Student.objects.get(user=request.user)
        
        # Find the active bus enrollment for the student
        enrollment = StudentOnRoute.objects.filter(student=current_student, is_active=True).first()

        if enrollment:
            # Redirect to the specific payment pass using the enrollment ID
            return redirect('transport:payment_pass', enrollment_id=enrollment.id)
        else:
            messages.info(request, "You are not currently signed up for a bus route. Please sign up first.")
            return redirect('transport:signup') # Redirect to the signup page if no active pass is found
    except Student.DoesNotExist:
        # Handle the case where the user is not a student
        messages.error(request, "User is not associated with a student account.")
        return redirect('transport:some_other_page')


def is_staff_or_superuser(user):
    return user.is_staff or user.is_superuser

@user_passes_test(is_staff_or_superuser)
def bus_payment_report_view(request):
    """
    Generates a report showing bus payment income and balance per route,
    with an option to filter by a specific route.
    """
    # Get all routes for the dropdown filter
    all_routes = Route.objects.all().order_by('name')
    
    # Get the selected route ID from the request, default to None
    selected_route_id = request.GET.get('route')
    
    # Filter the routes based on the selected route ID
    if selected_route_id:
        routes_to_report = Route.objects.filter(id=selected_route_id)
    else:
        routes_to_report = all_routes

    report_data = []
    
    for route in routes_to_report:
        enrollments = StudentOnRoute.objects.filter(route=route)
        
        total_income = BusPayment.objects.filter(
            enrollment__route=route,
            is_approved=True
        ).aggregate(
            total=Sum('amount_paid')
        )['total'] or 0
        
        total_potential_income = enrollments.aggregate(
            total=Sum('route__bus_fee')
        )['total'] or 0

        total_balance = total_potential_income - total_income
        
        student_count = enrollments.count()
        
        report_data.append({
            'route_name': route.name,
            'bus_fee': route.bus_fee,
            'student_count': student_count,
            'total_income': total_income,
            'total_potential_income': total_potential_income,
            'total_balance': total_balance,
        })
        
    # Grand totals are still calculated for all data, regardless of filtering
    grand_total_income = sum(item['total_income'] for item in report_data)
    grand_total_potential_income = sum(item['total_potential_income'] for item in report_data)
    grand_total_balance = sum(item['total_balance'] for item in report_data)
    
    # ... (Paginator logic remains the same)
    paginator = Paginator(report_data, 10)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)

    context = {
        'page_obj': page_obj,
        'all_routes': all_routes,  # Pass all routes to the template for the filter dropdown
        'selected_route_id': selected_route_id,
        'grand_total_income': grand_total_income,
        'grand_total_potential_income': grand_total_potential_income,
        'grand_total_balance': grand_total_balance,
    }
    
    return render(request, 'transport/test_bus_payment_report.html', context)



def bus_enrollment_form(request, student_id=None):
    """
    Renders the bus enrollment form, pre-filling the student's name if an ID is provided.
    """
    initial_data = {}
    student = None
    
    if student_id:
        # Get the student using the USN (Unique Student Number)
        student = get_object_or_404(Student, USN=student_id)
        initial_data['student'] = student
        
    if request.method == 'POST':
        form = BusEnrollmentForm(request.POST, initial=initial_data)
        if form.is_valid():
            # Process the form data
            form.save()
            # Redirect to a success page or back to the student list
            return redirect('transport:bus_signup_success')
    else:
        # Create an empty form or pre-filled form based on initial data
        form = BusEnrollmentForm(initial=initial_data)

    context = {
        'form': form,
        'student': student,
    }
    
    return render(request, 'transport/test_bus_enrollment_form.html', context)



def is_staff_or_superuser(user):
    return user.is_staff or user.is_superuser

@user_passes_test(is_staff_or_superuser)
def enroll_or_pay_redirect(request, student_id):
    """
    Checks if a student is enrolled for bus services and redirects
    to the appropriate form (enrollment or payment).
    """
    student = get_object_or_404(Student, USN=student_id)
    
    try:
        # Check if a StudentOnRoute record exists for this student
        student_on_route = StudentOnRoute.objects.get(student=student)
        
        # If enrolled, redirect to the bus payment form
        messages.info(request, f'{student.first_name} {student.last_name} is not yet enrolled for bus services. Please complete the enrollment form.')
        return redirect('transport:bus_payment_form', student_id=student.USN)
        
    except StudentOnRoute.DoesNotExist:
        # If not enrolled, redirect to the bus enrollment form
        messages.info(request, f'{student.first_name} {student.last_name} is not yet enrolled for bus services. Please complete the enrollment form.')
        return redirect('transport:bus_enrollment_form', student_id=student.USN)
    


def is_staff_or_superuser(user):
    return user.is_staff or user.is_superuser

@user_passes_test(is_staff_or_superuser)
def bus_payment_form_view(request, student_id=None):
    """
    Renders the bus payment form, pre-filling the student and enrollment details.
    """
    initial_data = {}
    student = None
    
    if student_id:
        student = get_object_or_404(Student, USN=student_id)
        try:
            # Get the related StudentOnRoute instance to link the payment
            student_on_route = StudentOnRoute.objects.get(student=student)
            initial_data['enrollment'] = student_on_route
        except StudentOnRoute.DoesNotExist:
            messages.error(request, 'This student is not enrolled for bus services. Please enroll them first.')
            return redirect('transport:bus_enrollment_form', student_id=student.USN)
    
    if request.method == 'POST':
        form = BusPaymentForm(request.POST, initial=initial_data)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.is_approved = True  # Admins can approve payments directly
            payment.save()
            messages.success(request, f'Bus payment for {student.get_full_name()} was successfully recorded.')
            return redirect('transport:payment_report')
    else:
        form = BusPaymentForm(initial=initial_data)

    context = {
        'form': form,
        'student': student,
    }
    
    return render(request, 'transport/test_bus_payment_form.html', context)


def bus_signup_success(request):
    return render(request, 'transport/test_bus_signup_success.html')