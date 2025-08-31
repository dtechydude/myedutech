from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse, reverse_lazy
from django.db.models import F, Sum, Q
from transport.models import Route, StudentOnRoute, BusPayment
from transport.forms import StudentOnRouteForm, BusEnrollmentForm, BusPaymentForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
import os
from students.models import Student
from curriculum.models import Session, Term


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
            return redirect('some_success_url') # Redirect to a success page
    else:
        # For a GET request, create an empty form
        # If you're editing an existing StudentOnRoute object:
        # student_on_route_instance = StudentOnRoute.objects.get(some_condition)
        # form = StudentOnRouteForm(instance=student_on_route_instance)
        # Otherwise, for a new signup:
        form = StudentOnRouteForm()

    return render(request, 'transport/signup_for_bus.html', {'form': form})



# @login_required
# def my_route(request):
#     # Assuming you want to get the StudentOnRoute for the current user
#     # You'll need to adapt this logic to how you identify the specific StudentOnRoute
#     # For example, if StudentOnRoute has a ForeignKey to User or StudentProfile:
#     try:
#         student_on_route_details = StudentOnRoute.objects.get(student__user=request.user)
#     except StudentOnRoute.DoesNotExist:
#         student_on_route_details = None # Or handle the case where no details exist

#     return render(request, 'transport/my_route.html', {'student_details': student_on_route_details})



def submission_success(request):
    return render(request, 'transport/bus_signup_success.html')


# @login_required
# def create_bus_signup(request):
#     if request.method == 'POST':
#         form = BusSignupForm(request.POST, request=request) # Pass request to the form
#         if form.is_valid():
#             # Before saving, associate the student
#             signup = form.save(commit=False)
#             signup.student = request.user # Assign the current logged-in student
#             signup.save()
#             messages.success(request, 'Successfully signed up for the bus route! 🚌')
#             return redirect('transport:submission_success')
#         else:
#             # If form is invalid (e.g., duplicate), errors will be in form.errors
#             messages.error(request, 'There was an issue with your signup. Please check the form.')
#     else:
#         form = BusSignupForm(request=request) # Pass request to the form for initial display
    
#     context = {
#         'form': form
#     }
#     return render(request, 'transport/create_bus_signup.html', context)


@login_required
def bus_signup_list(request):
    """
    Displays a list of all students signed up for bus routes.
    """
    # Fetch all StudentOnRoute objects.
    # .select_related('student', 'route') efficiently fetches the related
    # User (for student) and Route objects in the same database query,
    # preventing N+1 query problems.
    student_signups = StudentOnRoute.objects.all().select_related('student', 'route').order_by('signup_date')
    
    context = {
        'student_signups': student_signups
    }
    return render(request, 'transport/bus_signup_list.html', context)

# students see their route details
@login_required
def student_own_route_detail(request):
    """
    Displays the bus route details for the currently logged-in student.
    """
    try:
        # This is the correct line: Filter directly by 'student=request.user'
        student_signup = StudentOnRoute.objects.select_related('route').get(student=request.user)
        # student_signup = StudentOnRoute.objects.filter(payee=User.objects.get(username=request.user))

    except StudentOnRoute.DoesNotExist:
        student_signup = None # No signup found for this student

    context = {
        'student_signup': student_signup
    }
    return render(request, 'transport/student_own_route_detail.html', context)

# # Keep your other view as well
# @login_required
# def bus_signup_list(request):
#     # Fetch all StudentOnRoute objects.
#     student_signups = StudentOnRoute.objects.all().select_related('student', 'route').order_by('signup_date')
    
#     context = {
#         'student_signups': student_signups
#     }
#     return render(request, 'transport/bus_signup_list.html', context)



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
            return redirect('bus:payment_pass', enrollment_id=enrollment.id)
    else:
        form = BusEnrollmentForm(request=request)

    context = {
        'form': form,
        'student': current_student
    }
    return render(request, 'transport/bus_signup.html', context)


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
            return redirect('bus:payment_pass', enrollment_id=enrollment.id)
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
    
    total_paid = payments.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0.0
    balance = enrollment.route.bus_fee - total_paid
    is_fully_paid = balance <= 0
    
    # Check if a printable version is requested
    if 'printable' in request.GET:
        context = {
            'enrollment': enrollment,
            'balance': balance,
            'total_paid': total_paid,
            'is_fully_paid': is_fully_paid,
        }
        return render(request, 'printable_bus_pass.html', context)
    
    # Otherwise, render the standard payment pass page
    payment_form = None
    if not is_fully_paid:
        payment_form = BusPaymentForm()
        if request.method == 'POST':
            payment_form = BusPaymentForm(request.POST)
            if payment_form.is_valid():
                payment = payment_form.save(commit=False)
                payment.enrollment = enrollment
                payment.save()
                messages.success(request, "Payment has been recorded successfully.")
                return redirect('bus:payment_pass', enrollment_id=enrollment.id)

    context = {
        'enrollment': enrollment,
        'balance': balance,
        'total_paid': total_paid,
        'is_fully_paid': is_fully_paid,
        'payment_form': payment_form,
    }
    return render(request, 'student_payment_pass.html', context)


def is_staff_or_superuser(user):
    return user.is_staff or user.is_superuser

@user_passes_test(is_staff_or_superuser)
def bus_enrollment_list_view(request):
    """
    Displays a list of all students signed up for bus transport.
    Accessible only to staff.
    """
    enrollments = StudentOnRoute.objects.all().order_by('student__first_name')

    # Add calculated fields for each enrollment
    for enrollment in enrollments:
        total_paid = enrollment.payments.filter(is_approved=True).aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0.0
        enrollment.total_paid = total_paid
        enrollment.balance = enrollment.route.bus_fee - total_paid

    context = {
        'enrollments': enrollments,
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
            return redirect('bus:payment_pass', enrollment_id=enrollment.id)
        else:
            messages.info(request, "You are not currently signed up for a bus route. Please sign up first.")
            return redirect('bus:signup') # Redirect to the signup page if no active pass is found
    except Student.DoesNotExist:
        # Handle the case where the user is not a student
        messages.error(request, "User is not associated with a student account.")
        return redirect('some_other_page')
