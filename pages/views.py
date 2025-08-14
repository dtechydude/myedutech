from django.shortcuts import render
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.contrib.auth.models import User
from students.models import Student
from staff.models import Teacher
from payments.models import BankDetail
from users.models import Profile
from curriculum.models import Standard, SchoolIdentity, Term
from students.models import Parent
# from portal.models import Standard
# from payments.models import PaymentDetail1
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import  DetailView


# Create your views here.
def schoolly_home(request):
    return render(request, 'pages/schoollyedtech.html')

# def dashboard(request):
#     return render(request, 'pages/portal_home.html')

# Portal Home
@login_required
def dashboard(request):  
    users_num = User.objects.count()
    student_num = Student.objects.count()
    num_of_classes = Standard.objects.count()
    boarder_std = Student.objects.filter(student_type='boarder').count()
    day_std = Student.objects.filter(student_type='day_student').count()
    num_student_inclass = Student.objects.filter().count()
    graduated = Student.objects.filter(student_status='graduated').count()
    dropped = Student.objects.filter(student_status='dropped').count()
    expelled = Student.objects.filter(student_status='expelled').count()
    suspended = Student.objects.filter(student_status='suspended').count()
    active = Student.objects.filter(student_status='active').count()
    # payments = PaymentDetail1.objects.count()
    # staff_num = Staff.objects.count()
    teacher_num = Teacher.objects.count()    
    my_idcard = Student.objects.filter(user=User.objects.get(username=request.user))
    students = Student.objects.filter().order_by('current_class').values('current_class__name').annotate(count=Count('current_class__name'))
    my_students = Student.objects.filter(form_teacher__user=request.user).order_by('first_name')
    # no_inteacherclass = Assign.objects.filter(teacher__user=request.user).count()
    # no_inteacherclass = Student.objects.filter(form_teacher=request.user).count()

    classrooms = Standard.objects.all()

    try:
        num_inclass = Student.objects.filter(current_class = request.user.student.current_class).count()
    except Student.DoesNotExist:
        num_inclass = Student.objects.filter()
    # Build a paginator with function based view
    queryset = Teacher.objects.all().order_by("-id")
    page = request.GET.get('page', 1)
    paginator = Paginator(queryset, 40)
    try:
        events = paginator.page(page)
    except PageNotAnInteger:
        events = paginator.page(1)
    except EmptyPage:
        events = paginator.page(paginator.num_pages)
    
       
    context = {        
        'student_num': student_num,
        'boarder_std':boarder_std,
        'day_std': day_std,
        'students' : students,
        'users_num': users_num,
        'num_inclass': num_inclass,
        # 'staff_num': staff_num,
        'teacher_num':teacher_num,
        'graduated': graduated,
        'dropped': dropped,
        'expelled': expelled,
        'suspended': suspended,
        # 'payments': payments,
        'active': active,
        'queryset': queryset,
        'events':events,
        'my_idcard':my_idcard,
        'my_students':my_students,
        # 'no_inteacherclass': no_inteacherclass,
        'classrooms':classrooms,
        'num_of_classes':num_of_classes,
    

    }
        
    return render(request, 'pages/portal_home.html', context )    

        
def help_center(request):
    return render(request, 'pages/help_center.html')

def support_info(request):
    school_contact = SchoolIdentity.objects.all()
    return render(request, 'pages/support_info.html', {'school_contact':school_contact})

def lock_screen(request):
    return render(request, 'pages/lockscreen.html')

def success_submission(request):
    return render(request, 'pages/success_submission.html')

# phone list
def phone_list(request):
    users = User.objects.all()  
    
    context = {        
        'users': users,
      
    }    
    return render(request, 'pages/phone_list.html', context)

# email list
def email_list(request):
    users = User.objects.all()

    
    context = {        
        'users': users,   
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


# birthday list
def bank_detail(request):
    bank_detail = BankDetail.objects.all()   
    context = {        
        'bank_detail': bank_detail,
    }
    return render(request, 'pages/bank_detail.html', context)

