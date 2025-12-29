from django.shortcuts import render, redirect
import csv
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from users.forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm, StudentEnrollmentForm, TeacherEmploymentUpdateForm, UserTwoUpdateForm, UserRegistrationForm
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm
from django.http import JsonResponse
from curriculum.models import SchoolIdentity
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from students.models import Parent

from django.contrib.auth import views as auth_views
from django.db.utils import OperationalError, ProgrammingError
# Create your views here.

# Enrollment of new student
def user_registration(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'New user account has been created!' )
            return redirect('/')
    else:
        form = UserRegisterForm()
        user = request.user
        if user.is_superuser or user.is_staff:
            return render(request, 'users/user_registration.html', {'form': form})
       

    
# STUDENTS ENROLLMENT
@login_required
def student_enrollment(request):
    if request.method == 'POST':
        u_form = UserRegisterForm(request.POST)
        p_form = StudentEnrollmentForm(request.POST, request.FILES)

        if u_form.is_valid() and p_form.is_valid():
            # Get the cleaned data from the forms
            user_data = u_form.cleaned_data
            student_data = p_form.cleaned_data

            # Create the Student object, setting first_name and last_name from the user form
            student = Student(
                first_name=user_data.get('first_name'),
                last_name=user_data.get('last_name'),
                **student_data
            )
            student.save()

            messages.success(request, 'Student has been enrolled successfully')
            return redirect('some_success_url')  # Replace with a valid URL name
    else:
        u_form = UserRegisterForm()
        p_form = StudentEnrollmentForm()

    context = {
        'u_form': u_form,
        'p_form': p_form,
    }

    return render(request, 'users/student_enrollment.html', context)


def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'New user account has been created!' )
            return redirect('pages:success_submission')
    else:
        form = UserRegisterForm()
        user = request.user
        if user.is_superuser or user.is_staff:
            return render(request, 'users/register.html', {'form': form})
        else:
            return render(request, 'pages/portal_home.html')       
    

# BASIC PROFILE UPDATE
@login_required
def profile_edit(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your profile has been updated successfully')
            return redirect('pages:success_submission')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'u_form': u_form,
        'p_form': p_form,
    }

    return render(request, 'users/profile.html', context)

# BASIC PROFILE UPDATE For Staff
@login_required
def employment_edit(request):
    if request.method == 'POST':
        u_form = UserTwoUpdateForm(request.POST, instance=request.user)
        p_form = TeacherEmploymentUpdateForm(request.POST, request.FILES, instance=request.user.teacher)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your profile has been updated successfully')
            return redirect('pages:success_submission')
    else:
        u_form = UserTwoUpdateForm(instance=request.user)
        p_form = TeacherEmploymentUpdateForm(instance=request.user.teacher)

    context = {
        'u_form': u_form,
        'p_form': p_form,
    }

    return render(request, 'users/employment_profile.html', context)


 # new user login logic   
def user_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Handle 'next' parameter for redirection after login
            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('/dashboard/') # Redirect to a default page if no 'next'
    else:
        form = AuthenticationForm()
    return render(request, 'users/login.html', {'form': form})


def user_logout(request):
    logout(request)
    # Redirect to a new URL. You have a few options:
    
    # Option 1: Redirect to the homepage
    return redirect('logout_success')  # Assumes you have a URL named 'home'


def logout_success(request):
    return render (request, 'users/logout.html')


@login_required
def users_home(request):
    return render(request, 'pages/portal_home.html')


# all users
@login_required
def all_users(request):
    """
    A view to display all users and export them to a CSV,
    only accessible by staff users.
    """
    user = request.user
    
    # Restrict access to only staff users
    if not user.is_staff:
        return redirect('pages/portal_home.html') # Redirect to a safe URL for non-staff users

    all_users_list = User.objects.all().order_by('last_name', 'first_name')
    
    # Handle CSV export request
    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="all_users.csv"'

        writer = csv.writer(response)
        writer.writerow(['Username', 'First Name', 'Last Name', 'Email', 'Phone', 'State Of Origin', 'User Type', 'Registered Date'])

        for u in all_users_list:
            writer.writerow([u.username, u.first_name, u.last_name, u.email, u.profile.phone, u.profile.state_of_origin, u.profile.user_type, u.profile.created])
        return response

    # Normal template rendering
    context = {'all_users': all_users_list}
    return render(request, 'users/all_registered_users.html', context)


# Enroll students view
@login_required
def enroll_student(request):
    user_form = UserRegistrationForm(request.POST or None)
    student_form = StudentEnrollmentForm(request.POST or None)
    
    # Retrieve the school identity information
    try:
        school_identity = SchoolIdentity.objects.first()
    except SchoolIdentity.DoesNotExist:
        school_identity = None

    if request.method == 'POST':
        # Check which form was submitted using a hidden input or button name
        if 'user_submit' in request.POST:
            if user_form.is_valid():
                user_data = user_form.cleaned_data
                user = User.objects.create_user(
                    username=user_data['username'],
                    email=user_data['email'],
                    password=user_data['password'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name']
                )
                
                # Store user info in session to pass to the next step
                request.session['temp_user_id'] = user.id
                
                messages.success(request, 'User created successfully! Now, please provide the student details.')
                return redirect('enroll_student_details')  # Redirect to the next step

        elif 'student_submit' in request.POST:
            if 'temp_user_id' in request.session:
                user_id = request.session['temp_user_id']
                try:
                    user = User.objects.get(id=user_id)
                except User.DoesNotExist:
                    messages.error(request, 'An error occurred. Please restart the enrollment process.')
                    return redirect('enroll_student')
                
                # Bind the student form to the request data
                student_form = StudentEnrollmentForm(request.POST)
                if student_form.is_valid():
                    student = student_form.save(commit=False)
                    student.user = user  # Link the student record to the new user
                    student.USN = user.username # Ensure USN is the same as username
                    student.first_name = user.first_name # Sync first name
                    student.last_name = user.last_name # Sync last name
                    student.save()
                    
                    # Clear session data
                    del request.session['temp_user_id']

                    messages.success(request, f'Student {student.get_full_name()} has been successfully enrolled!')
                    return redirect('some_success_page') # Redirect to a success page

    return render(request, 'users/enroll_student.html', {
        'user_form': user_form,
        'student_form': student_form,
        'school_identity': school_identity, # Add school_identity to the context
    })

@login_required
def enroll_student_details(request):
    if 'temp_user_id' not in request.session:
        messages.error(request, 'Invalid session. Please start the enrollment process from the beginning.')
        return redirect('enroll_student')
    
    user_id = request.session['temp_user_id']
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found. Please restart the enrollment process.')
        return redirect('enroll_student')

    student_form = StudentEnrollmentForm(request.POST or None, initial={'USN': user.username})

    # Retrieve the school identity information for this view as well
    try:
        school_identity = SchoolIdentity.objects.first()
    except SchoolIdentity.DoesNotExist:
        school_identity = None

    if request.method == 'POST':
        if student_form.is_valid():
            student = student_form.save(commit=False)
            student.user = user
            student.USN = user.username
            student.first_name = user.first_name
            student.last_name = user.last_name
            student.save()
            
            del request.session['temp_user_id']
            
            messages.success(request, f'Student {student.get_full_name()} has been successfully enrolled!')
            return redirect('success_page')
    
    return render(request, 'users/enroll_student_details.html', {
        'student_form': student_form,
        'user_first_name': user.first_name,
        'user_last_name': user.last_name,
        'school_identity': school_identity, # Add school_identity to the context
    })


@login_required
def enroll_success(request):
    return render(request, 'users/enroll_success.html')


def check_username(request):
    """
    Checks if a username is already taken.
    """
    if request.method == 'GET':
        username = request.GET.get('username', None)
        is_taken = User.objects.filter(username__iexact=username).exists()
        data = {
            'is_taken': is_taken
        }
        return JsonResponse(data)
    
    return JsonResponse({'error': 'Invalid request method'}, status=400)



class CustomLoginView(LoginView):
    template_name = 'users/login.html'

    def get_success_url(self):
        # Check if the logged-in user is associated with a Parent object
        is_parent = Parent.objects.filter(user=self.request.user).exists()

        if is_parent:
            return reverse_lazy('students:parent-dashboard')
        
        # If not a parent, use the default redirect URL
        return super().get_success_url()
    



class SafePasswordResetView(auth_views.PasswordResetView):
    template_name = 'users/password_reset.html'
    email_template_name = 'registration/password_reset_email_text.txt'
    html_email_template_name = 'registration/password_reset_email.html'

    def get_extra_email_context(self):
        context = super().get_extra_email_context() or {}

        try:
            context['school_info'] = SchoolIdentity.objects.first()
        except (OperationalError, ProgrammingError):
            # Table does not exist yet (before migration)
            context['school_info'] = None

        return context
