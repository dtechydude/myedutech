from django.shortcuts import render, redirect
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse, reverse_lazy
from django.db.models import F, Sum, Q
from transport.models import Route, StudentOnRoute
from transport.forms import StudentOnRouteForm, BusSignupForm
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
import os
from students.models import Student


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


@login_required
def create_bus_signup(request):
    if request.method == 'POST':
        form = BusSignupForm(request.POST, request=request) # Pass request to the form
        if form.is_valid():
            # Before saving, associate the student
            signup = form.save(commit=False)
            signup.student = request.user # Assign the current logged-in student
            signup.save()
            messages.success(request, 'Successfully signed up for the bus route! 🚌')
            return redirect('transport:submission_success')
        else:
            # If form is invalid (e.g., duplicate), errors will be in form.errors
            messages.error(request, 'There was an issue with your signup. Please check the form.')
    else:
        form = BusSignupForm(request=request) # Pass request to the form for initial display
    
    context = {
        'form': form
    }
    return render(request, 'transport/create_bus_signup.html', context)


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