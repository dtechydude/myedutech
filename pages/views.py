from django.shortcuts import render
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.contrib.auth.models import User
from students.models import Student
from staff.models import Teacher
from users.models import Profile
from curriculum.models import Standard, SchoolIdentity
# from portal.models import Standard
# from payments.models import PaymentDetail1
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import  DetailView


# Create your views here.
def schoolly_home(request):
    return render(request, 'pages/schoollyedtech.html')

def dashboard(request):
    return render(request, 'pages/portal_home.html')

        
def help_center(request):
    return render(request, 'pages/help_center.html')

def support_info(request):
    school_contact = SchoolIdentity.objects.all()
    return render(request, 'pages/support_info.html', {'school_contact':school_contact})

def lock_screen(request):
    return render(request, 'pages/lockscreen.html')

# phone list
def phone_list(request):
    user_phone = User.objects.all()
    guardian_phone = Profile.objects.all()
    guarantor_phone = User.objects.all()
    
    context = {        
        'user_phone': user_phone,
        'guardian_phone':guardian_phone,
        'guarantor_phone': guarantor_phone,
    }
    
    return render(request, 'pages/phone_list.html', context)

# email list
def email_list(request):
    user_email = User.objects.all()
    guardian_email = Student.objects.all()
    guarantor_email = Teacher.objects.all()
    
    context = {        
        'user_email': user_email,
        'guardian_email':guardian_email,
        'guarantor_email': guarantor_email,
    }
    return render(request, 'pages/email_list.html', context )

# birthday list
def birthday_list(request):
    user_birthday = Profile.objects.all()
    teacher_birthday = Teacher.objects.all()
    student_birthday = Student.objects.all()
    context = {        
        'user_birthday': user_birthday,
        'teacher_birthday':teacher_birthday,
        'student_birthday': student_birthday,
    }
    return render(request, 'pages/birthday_list.html', context)

def payment_instruction(request):
    return render(request, 'pages/payment_instruction.html')

def payment_chart(request):
    return render(request, 'pages/payment_chart.html')
