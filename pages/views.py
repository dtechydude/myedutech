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
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import  DetailView
import csv
from django.http import HttpResponse


# Create your views here.
def schoolly_home(request):
    return render(request, 'pages/schoollyedtech.html')

def landing_page(request):
    return render(request, 'pages/landingpage.html')

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

@login_required        
def help_center(request):
    return render(request, 'pages/help_center.html')

@login_required
def support_info(request):
    school_contact = SchoolIdentity.objects.all()
    return render(request, 'pages/support_info.html', {'school_contact':school_contact})

@login_required
def lock_screen(request):
    return render(request, 'pages/lockscreen.html')

@login_required
def success_submission(request):
    return render(request, 'pages/success_submission.html')


# email list
@login_required
def email_list(request):
    users = User.objects.all()

    
    context = {        
        'users': users,   
    }
    return render(request, 'pages/email_list.html', context )

# birthday list
@login_required
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

@login_required
def payment_instruction(request):
    return render(request, 'pages/payment_instruction.html')

@login_required
def payment_chart(request):
    return render(request, 'pages/payment_chart.html')



# birthday list
@login_required
def bank_detail(request):
    bank_detail = BankDetail.objects.all()   
    context = {        
        'bank_detail': bank_detail,
    }
    return render(request, 'pages/bank_detail.html', context)

# students phone list
@login_required
def student_phone_list_view(request):
    """
    A view to display a phone list of all students and allows for CSV export.
    """
    students = Student.objects.select_related('user__profile').all().order_by('last_name', 'first_name')

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="student_phone_list.csv"'

        writer = csv.writer(response)
        writer.writerow(['Student Name', 'Student Phone', 'Guardian Name', 'Guardian Phone'])

        for student in students:
            writer.writerow([
                student.get_full_name(),
                student.user.profile.phone,
                student.guardian_name,
                student.guardian_phone,
            ])
        return response

    context = {
        'students': students,
    }

    return render(request, 'pages/students_phone_list.html', context)

# Students Email List
@login_required
def student_email_list_view(request):
    """
    A view to display a list of student and guardian emails and allows for CSV export.
    """
    students = Student.objects.all().order_by('last_name', 'first_name')

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="student_email_list.csv"'

        writer = csv.writer(response)
        writer.writerow(['Student Name', 'Student Email', 'Guardian Name', 'Guardian Email'])

        for student in students:
            writer.writerow([
                student.get_full_name(),
                student.user.email,
                student.guardian_name,
                student.guardian_email,
            ])
        return response

    context = {
        'students': students,
    }

    return render(request, 'pages/students_email_list.html', context)

# Teachers/guarantors Phone List
@login_required
def teacher_guarantor_phone_list_view(request):
    """
    A view to display a list of teacher guarantor phone numbers and allows for CSV export.
    """
    teachers = Teacher.objects.all().order_by('last_name', 'first_name')

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="teacher_guarantor_phone_list.csv"'

        writer = csv.writer(response)
        writer.writerow(['Teacher Name', 'Profile Phone', 'Guarantor Name', 'Guarantor Phone'])

        for teacher in teachers:
            writer.writerow([
                teacher.get_full_name(),
                teacher.phone_home,
                teacher.guarantor_name,
                teacher.guarantor_phone,
            ])
        return response

    context = {
        'teachers': teachers,
    }

    return render(request, 'pages/teachers_phone_list.html', context)

# Teachers Email List
@login_required
def teacher_guarantor_email_list_view(request):
    """
    A view to display a list of teacher guarantor emails and allows for CSV export.
    """
    teachers = Teacher.objects.all().order_by('last_name', 'first_name')

    if request.GET.get('export') == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="teacher_guarantor_email_list.csv"'

        writer = csv.writer(response)
        writer.writerow(['Teacher Name', 'Profile Email', 'Guarantor Name', 'Guarantor Email'])

        for teacher in teachers:
            writer.writerow([
                teacher.get_full_name(),
                teacher.user.email,
                teacher.guarantor_name,
                teacher.guarantor_email,
            ])
        return response

    context = {
        'teachers': teachers,
    }

    return render(request, 'pages/teachers_email_list.html', context)



@login_required
def video_guides_view(request):
    # A placeholder list of video data with an 'is_staff_only' flag
    video_list = [
         {
            'title': 'Smart Intro - KwikSchools',
            'youtube_url': 'https://www.youtube.com/embed/lMgWQgFQrrY',
            'description': 'A Smart Intro To KwikSchools.',
            'is_staff_only': False
        },
        # Add more videos here
        {
            'title': 'A KwikSchools Quick Guide',
            'youtube_url': 'https://www.youtube.com/embed/KwjiFOwDOl4',
            'description': 'A walk-through video on how to use the features.',
            'is_staff_only': False
        },
        {
            'title': 'Admin - School Set-Up (Admin)',
            'youtube_url': 'https://www.youtube.com/embed/dGpsPRIlkH4',
            'description': 'Set Up - Initial portal set up',
            'is_staff_only': True  # This video is for staff only
        },
         {
            'title': 'Admin - Payment Module 1 (Admin)',
            'youtube_url': 'https://www.youtube.com/embed/_DeB_8i-3jc',
            'description': 'Set Up - Payment Module',
            'is_staff_only': True  # This video is for staff only
        },
         {
            'title': 'Admin - Student Enrolment & Teachers Signup',
            'youtube_url': 'https://www.youtube.com/embed/EHOePJXKWp0',
            'description': 'Set Up - Initial portal set up',
            'is_staff_only': True  # This video is for staff only
        },
         {
            'title': 'Admin - Assign Form Teachers To Classes',
            'youtube_url': 'https://www.youtube.com/embed/jnm5nk58L-Q',
            'description': 'How to assign form teachers to classes',
            'is_staff_only': True  # This video is for staff only
        },
        {
            'title': 'STUDENTS - The Student Dashboard 1',
            'youtube_url': 'https://www.youtube.com/embed/jnm5nk58L-Q',
            'description': 'Exploring the student dashboard',
            'is_staff_only': False  # This video is for staff only
        },
       
    ]

    # Filter videos based on the user's staff status
    if request.user.is_staff:
        # Staff users see all videos
        visible_videos = video_list
    else:
        # Non-staff users only see videos that are NOT staff only
        visible_videos = [video for video in video_list if not video['is_staff_only']]

    context = {
        'title': 'MyEduTech Video Guides',
        'videos': visible_videos,
    }
    return render(request, 'pages/video_guides.html', context)