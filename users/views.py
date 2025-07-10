from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from users.forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm, StudentEnrollmentForm, TeacherEmploymentUpdateForm, UserTwoUpdateForm
from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm

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
       

    


#Student Enrollment
@login_required
def student_enrollment(request):
    if request.method == 'POST':
        u_form = UserRegisterForm(request.POST)
        p_form = StudentEnrollmentForm(request.POST, request.FILES)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, f'Your profile has been updated successfully')
            return redirect('profile')
    else:
        u_form = UserRegisterForm(instance=request.user)
        p_form = StudentEnrollmentForm(instance=request.user.profile)

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


# def user_login(request):
#     if request.method == 'POST':
#         username = request.POST.get('username')
#         password = request.POST.get('password')

#         user = authenticate(username=username, password=password)

#         if user:
#             if user.is_active:
#                 login(request,user)
#                 return HttpResponseRedirect(reverse('users:profile'))
#             else:
#                 return HttpResponse("ACCOUNT IS DEACTIVATED")

#         else:
#             return HttpResponse("Please use correct id and password")
#     else:
#         return render(request, 'users/login.html')
    
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


@login_required
def user_logout(request):
    logout(request)
    # return HttpResponseRedirect(reverse('users:user_logout'))
    return render(request, 'users/logout.html')

@login_required
def users_home(request):
    return render(request, 'pages/portal_home.html')

@login_required
def all_users(request):
    all_users = User.objects.all()
    user = request.user
    if user.is_superuser or user.is_staff:
        return render(request, 'users/all_users.html', {'all_users':all_users})
    else:
        return render(request, 'pages/portal_home.html')

