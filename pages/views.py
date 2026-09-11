from django.shortcuts import render
from django.core.mail import send_mail
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.contrib.auth.models import User
from students.models import Student
from attendance.models import Attendance
from staff.models import Teacher
from payments.models import BankDetail
from users.models import Profile
from curriculum.models import Standard, SchoolIdentity, Term, Session
from students.models import Parent
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import  DetailView
import csv
from django.http import HttpResponse
from datetime import date, timedelta
from django.core.mail import send_mass_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import Newsletter


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
    session = Session.objects.filter(is_current=True).first()
    student_num = Student.objects.count()
    student_num_current = Student.objects.filter(student_status__in=['active', 'inactive']).count()
    num_of_classes = Standard.objects.count()
    boarder_std = Student.objects.filter(student_type='boarder', student_status='active').count()
    day_std = Student.objects.filter(student_type='day_student', student_status='active').count()
    inactive_std = Student.objects.filter(student_status='inactive').count()

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
        'session': session,
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
        'student_num_current':student_num_current,
        'inactive_std ': inactive_std,
    

    }
        
    return render(request, 'pages/portal_home.html', context )    



@login_required
def help_center(request):
    user = request.user
    context = {
        "is_student": hasattr(user, "student"),
        "is_teacher": hasattr(user, "teacher"),
        "is_parent": hasattr(user, "parent"),
        "is_staff_or_admin": user.is_staff or user.is_superuser,
    }
    return render(request, "pages/help_center.html", context)




@login_required
def support_info(request):
    user = request.user
    context = {
        "is_student": hasattr(user, "student"),
        "is_teacher": hasattr(user, "teacher"),
        "is_parent": hasattr(user, "parent"),
        "is_staff_or_admin": user.is_staff or user.is_superuser,
    }
    return render(request, "pages/support_info.html", context)


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


# Bank Details
@login_required
def bank_detail(request):
    """
    Read-only display of the school's official bank accounts, visible to
    students and other logged-in users, so payments (tuition, hostel,
    etc.) always go to a verified account rather than word-of-mouth or
    outdated details.
    """
    bank_details = BankDetail.objects.all()

    return render(request, 'pages/bank_detail.html', {
        'bank_detail': bank_details,
    })


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
            'youtube_url': 'https://www.youtube.com/watch/lMgWQgFQrrY',
            'description': 'A Smart Intro To KwikSchools.',
            'is_staff_only': False
        },
        # Add more videos here
        {
            'title': 'A KwikSchools Quick Guide',
            'youtube_url': 'https://www.youtube.com/watch/KwjiFOwDOl4',
            'description': 'A walk-through video on how to use the features.',
            'is_staff_only': False
        },
        {
            'title': 'Admin - School Set-Up (Admin)',
            'youtube_url': 'https://www.youtube.com/watch/dGpsPRIlkH4',
            'description': 'Set Up - Initial portal set up',
            'is_staff_only': True  # This video is for staff only
        },
         {
            'title': 'Admin - Payment Module 1 (Admin)',
            'youtube_url': 'https://www.youtube.com/watch/_DeB_8i-3jc',
            'description': 'Set Up - Payment Module',
            'is_staff_only': True  # This video is for staff only
        },
         {
            'title': 'Admin - Student Enrolment & Teachers Signup',
            'youtube_url': 'https://www.youtube.com/watch/EHOePJXKWp0',
            'description': 'Set Up - Initial portal set up',
            'is_staff_only': True  # This video is for staff only
        },
         {
            'title': 'Admin - Assign Form Teachers To Classes',
            'youtube_url': 'https://www.youtube.com/watch/jnm5nk58L-Q',
            'description': 'How to assign form teachers to classes',
            'is_staff_only': True  # This video is for staff only
        },
        {
            'title': 'STUDENTS - The Student Dashboard 1',
            'youtube_url': 'https://www.youtube.com/watch/xK9He7qwJLE',
            'description': 'Exploring the student dashboard',
            'is_staff_only': False  # This video is for staff only
        },
        {
            'title': 'TEACHERS - The Teachers Dashboard 1',
            'youtube_url': 'https://www.youtube.com/watch/HiRL_cLb8Z8',
            'description': 'Exploring the teachers dashboard',
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
        'title': 'Kwikschools Video Guides',
        'videos': visible_videos,
    }
    return render(request, 'pages/video_guides.html', context)


# NEWSLETTER LOGIC

def send_newsletter_task(newsletter_id):
    newsletter = Newsletter.objects.get(id=newsletter_id)
    subject = newsletter.subject
    
    # 1. Determine the Recipients
    users = User.objects.filter(is_active=True)
    
    if newsletter.target_audience == 'PARENTS':
        users = users.filter(parent__isnull=False)
    elif newsletter.target_audience == 'STUDENTS':
        users = users.filter(student__isnull=False)
    elif newsletter.target_audience == 'STAFF':
        users = users.filter(teacher__isnull=False)
    elif newsletter.target_audience == 'ADMINS':
        users = users.filter(is_staff=True)
    
    recipient_list = users.values_list('email', flat=True)

    # 2. Prepare the Email Template
    # You can reuse a professional wrapper template
    html_content = render_to_string('emails/newsletter_template.html', {
        'message': newsletter.message,
        'subject': newsletter.subject,
    })
    text_content = strip_tags(newsletter.message)

    # 3. Send via Anymail (Efficiently)
    for email in recipient_list:
        if email:
            msg = EmailMultiAlternatives(subject, text_content, None, [email])
            msg.attach_alternative(html_content, "text/html")
            msg.send()

    newsletter.sent = True
    newsletter.save()


# New View For Chart Reporting
import logging
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import render
from django.db.models import Sum, Avg, Count, Q
from curriculum.models import Term,  Session

logger = logging.getLogger(__name__)


@method_decorator(login_required(login_url='login'), name='dispatch')
class PerformanceDashboardView(View):
    """
    Role-aware performance & analytics dashboard.
    Extends portal_home.html and only overrides content_body — so the
    header, sidebar, nav, and footer are 100% reused, not duplicated.

    NOTE: Adjust the import paths below (finance.models, results.models,
    attendance.models, teachers.models/staff.models) if your actual app
    names differ. Each query is wrapped in try/except so one missing
    model never breaks the whole page — it just shows that section as
    empty/zero instead of crashing.
    """
    template_name = 'pages/performance_dashboard.html'

    def get(self, request):
        user = request.user
        context = {}

        try:
            from curriculum.models import Term
            current_term = Term.objects.filter(is_current=True).select_related('session').first()
        except Exception:
            current_term = None
            logger.warning('PerformanceDashboardView: could not resolve current Term.')

        context['current_term'] = current_term

        if user.is_superuser or user.is_staff:
            context['role'] = 'admin'
            context.update(self._school_wide_context(current_term))
        elif getattr(user, 'teacher', None):
            context['role'] = 'teacher'
            context.update(self._teacher_context(user.teacher, current_term))
        elif getattr(user, 'student', None):
            context['role'] = 'student'
            context.update(self._student_context(user.student, current_term))
        elif getattr(user, 'parent', None):
            context['role'] = 'parent'
            context.update(self._parent_context(user.parent, current_term))
        else:
            context['role'] = 'none'

        return render(request, self.template_name, context)

    # ── School-wide (superuser / staff) ─────────────────────────────
    def _school_wide_context(self, term):
        ctx = {}

        try:
            from students.models import Student
            from django.db.models import F

            active_students = Student.objects.exclude(
                student_status__in=['graduated', 'dropped', 'expelled', 'suspended']
            )

            ctx['total_students'] = active_students.count()

            ctx['class_distribution'] = list(
                active_students
                .values(class_name=F('current_class__name'))
                .annotate(student_count=Count('id'))
                .order_by('class_name')
            )
        except Exception:
            logger.exception('PerformanceDashboardView: enrollment query failed')
            ctx['total_students'] = 0
            ctx['class_distribution'] = []

        try:
            from finance.models import Payment, Expense
            income_total = Payment.objects.aggregate(total=Sum('amount_received'))['total'] or 0
            expense_total = Expense.objects.aggregate(total=Sum('amount'))['total'] or 0
            ctx['finance_income'] = income_total
            ctx['finance_expense'] = expense_total
            ctx['finance_net'] = income_total - expense_total
        except Exception:
            logger.exception('PerformanceDashboardView: finance query failed')
            ctx['finance_income'] = 0
            ctx['finance_expense'] = 0
            ctx['finance_net'] = 0

        try:
            from attendance.models import AttendanceSummary
            if term:
                summaries = AttendanceSummary.objects.filter(term=term).select_related('session', 'term')
                if summaries.exists():
                    total_pct = sum(s.attendance_percentage for s in summaries)
                    avg_rate = round(total_pct / summaries.count(), 1)
                    # Sanity guard — attendance_percentage is already capped by the model logic,
                    # but this protects the display in case of bad config data upstream.
                    ctx['attendance_rate'] = avg_rate if 0 <= avg_rate <= 100 else None
                else:
                    ctx['attendance_rate'] = None
            else:
                ctx['attendance_rate'] = None
        except Exception:
            logger.exception('PerformanceDashboardView: attendance query failed')
            ctx['attendance_rate'] = None

        try:
            from results.models import Score
            if term:
                class_perf = (
                    Score.objects.filter(term=term, total_score__isnull=False)
                    .values('standard__name')
                    .annotate(avg_score=Avg('total_score'))
                    .order_by('standard__name')
                )
                ctx['class_performance'] = list(class_perf)
            else:
                ctx['class_performance'] = []
        except Exception:
            logger.exception('PerformanceDashboardView: score query failed')
            ctx['class_performance'] = []

        try:
            from staff.models import Teacher
            ctx['total_teachers'] = Teacher.objects.filter(active=True).count()
        except Exception:
            try:
                from staff.models import Teacher
                ctx['total_teachers'] = Teacher.objects.filter(active=True).count()
            except Exception:
                ctx['total_teachers'] = 0

        return ctx

    # ── Teacher ──────────────────────────────────────────────────────
    def _teacher_context(self, teacher, term):
        ctx = {'my_classes': [], 'class_performance': [], 'attendance_rate': None}

        try:
            standards = teacher.standards_assigned.all()
            ctx['my_classes'] = list(standards.values_list('name', flat=True))

            from results.models import Score
            if term:
                ctx['class_performance'] = list(
                    Score.objects.filter(term=term, standard__in=standards, total_score__isnull=False)
                    .values('standard__name')
                    .annotate(avg_score=Avg('total_score'))
                    .order_by('standard__name')
                )
        except Exception:
            logger.exception('PerformanceDashboardView: teacher class/performance query failed')
            standards = teacher.standards_assigned.none()
            ctx['my_classes'] = []
            ctx['class_performance'] = []

        try:
            from attendance.services import get_student_attendance
            if term:
                class_students = Student.objects.filter(current_class__in=standards).exclude(
                    student_status__in=['graduated', 'dropped', 'expelled', 'suspended']
                )
                rates = []
                for s in class_students:
                    info = get_student_attendance(student=s, session=term.session, term=term)
                    if info.get('has_data'):
                        rates.append(info['attendance_percentage'])
                ctx['attendance_rate'] = round(sum(rates) / len(rates), 1) if rates else None
        except Exception:
            logger.exception('PerformanceDashboardView: teacher attendance query failed')
            ctx['attendance_rate'] = None

        return ctx


    

    # ── Student ──────────────────────────────────────────────────────

    def _student_context(self, student, term):
        ctx = {'my_term_performance': [], 'my_attendance_trend': []}

        try:
            from results.models import Score
            ctx['my_term_performance'] = list(
                Score.objects.filter(student=student, total_score__isnull=False)
                .values('term__name')
                .annotate(avg_score=Avg('total_score'))
                .order_by('term__id')
            )
        except Exception:
            logger.exception('PerformanceDashboardView: student performance query failed')
            ctx['my_term_performance'] = []

        try:
            from attendance.services import get_student_attendance
            from curriculum.models import Term

            trend = []
            terms = Term.objects.select_related('session').order_by('start_date')
            for t in terms:
                info = get_student_attendance(student=student, session=t.session, term=t)
                if info.get('has_data'):
                    trend.append({
                        'term': t.name,
                        'rate': info['attendance_percentage'],
                        'is_current': (term is not None and t.pk == term.pk),
                    })
            ctx['my_attendance_trend'] = trend
        except Exception:
            logger.exception('PerformanceDashboardView: student attendance query failed')
            ctx['my_attendance_trend'] = []

        return ctx
     
      

    # # ── Parent ───────────────────────────────────────────────────────
    def _parent_context(self, parent, term):
        ctx = {'children_data': []}

        try:
            from results.models import Score
            from attendance.services import get_student_attendance
            from curriculum.models import Term

            terms = Term.objects.select_related('session').order_by('start_date')
            children_data = []

            for child in parent.children.all():
                try:
                    scores = list(
                        Score.objects.filter(student=child, total_score__isnull=False)
                        .values('term__name')
                        .annotate(avg_score=Avg('total_score'))
                        .order_by('term__id')
                    )
                except Exception:
                    logger.exception(f'PerformanceDashboardView: parent performance query failed for child {child.pk}')
                    scores = []

                try:
                    trend = []
                    for t in terms:
                        info = get_student_attendance(student=child, session=t.session, term=t)
                        if info.get('has_data'):
                            trend.append({
                                'term': t.name,
                                'rate': info['attendance_percentage'],
                                'is_current': (term is not None and t.pk == term.pk),
                            })
                except Exception:
                    logger.exception(f'PerformanceDashboardView: parent attendance query failed for child {child.pk}')
                    trend = []

                children_data.append({'student': child, 'performance': scores, 'attendance': trend})

            ctx['children_data'] = children_data
        except Exception:
            logger.exception('PerformanceDashboardView: parent context failed')
            ctx['children_data'] = []

        return ctx





# ----------------------------------------------------------------------------
# 2) views.py
# ----------------------------------------------------------------------------
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import NoReverseMatch, reverse
from django.views import View

from .models import HybridIntegrationSettings  # adjust import path


def _safe_reverse(url_name, default=None):
    """
    Resolves an internal URL name if it exists in this deployment;
    otherwise returns `default` (None) so the calling code can mark the
    tile as "not yet available" instead of the page throwing a 500
    because an app's URL names differ from what's assumed here.
    """
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return default


class HybridIntegrationHubView(LoginRequiredMixin, View):
    """
    Central 'Hybrid Integration' hub. Surfaces role-appropriate shortcuts
    to internal KwikSchools resources (lesson notes, live classes,
    downloadable materials, bulk SMS/communication center) and external
    EdTech platforms (Google for Education, Microsoft Teams for
    Education), segregated into Student / Teacher / School sections.
    School admins (superuser/staff) see all three sections plus a
    settings panel to edit the external links inline.
    """
    template_name = 'pages/hybrid_integration_hub.html'

    def get(self, request, *args, **kwargs):
        integration_settings = HybridIntegrationSettings.get_solo()

        is_school_admin = request.user.is_superuser or request.user.is_staff
        is_teacher = hasattr(request.user, 'teacher')
        is_student = hasattr(request.user, 'student')

        # ---------------- STUDENT RESOURCES ----------------
        student_resources = [
            {
                'title': 'Lesson Notes',
                'description': 'Browse notes, PDFs, and materials uploaded by your teachers.',
                'icon': 'bi-journal-text',
                'url': _safe_reverse('elearning:student_notes_list'),   # ⚠️ VERIFY url name
                'external': False,
            },
            {
                'title': 'Live Classes',
                'description': 'Join scheduled live classes for your subjects.',
                'icon': 'bi-camera-video',
                'url': _safe_reverse('elearning:live_classes_list'),    # ⚠️ VERIFY url name
                'external': False,
            },
            {
                'title': 'Downloadable Materials',
                'description': 'Download assignments, videos, and study resources.',
                'icon': 'bi-cloud-download',
                'url': _safe_reverse('elearning:materials_list'),       # ⚠️ VERIFY url name
                'external': False,
            },
            {
                'title': 'Google Classroom',
                'description': "Sign in with your school Google account to access Classroom.",
                'icon': 'bi-google',
                'url': integration_settings.google_classroom_url,
                'external': True,
            },
            {
                'title': 'Microsoft Teams',
                'description': 'Sign in to Microsoft Teams for Education.',
                'icon': 'bi-microsoft',
                'url': integration_settings.microsoft_teams_url,
                'external': True,
            },
        ]

        # ---------------- TEACHER RESOURCES ----------------
        teacher_resources = [
            {
                'title': 'Upload Lesson Notes',
                'description': 'Post notes, PDFs, and assignments for your classes.',
                'icon': 'bi-journal-plus',
                'url': _safe_reverse('elearning:teacher_notes_manage'),        # ⚠️ VERIFY url name
                'external': False,
            },
            {
                'title': 'Manage Live Classes',
                'description': 'Schedule or start a live class session.',
                'icon': 'bi-broadcast',
                'url': _safe_reverse('elearning:teacher_live_class_manage'),   # ⚠️ VERIFY url name
                'external': False,
            },
            {
                'title': 'Grade Submissions',
                'description': 'Review and grade student assignment submissions.',
                'icon': 'bi-check2-square',
                'url': _safe_reverse('elearning:submissions_list'),            # ⚠️ VERIFY url name
                'external': False,
            },
            {
                'title': 'Google Classroom',
                'description': 'Sign in to manage your Google Classroom classes.',
                'icon': 'bi-google',
                'url': integration_settings.google_classroom_url,
                'external': True,
            },
            {
                'title': 'Microsoft Teams',
                'description': 'Sign in to Microsoft Teams for Education.',
                'icon': 'bi-microsoft',
                'url': integration_settings.microsoft_teams_url,
                'external': True,
            },
        ]
        if integration_settings.bulk_sms_enabled:
            teacher_resources.append({
                'title': 'Send Bulk SMS',
                'description': f"Message parents/students via {integration_settings.bulk_sms_provider_name or 'your SMS provider'}.",
                'icon': 'bi-chat-dots',
                'url': integration_settings.bulk_sms_provider_url or _safe_reverse('communication:bulk_sms_dashboard'),  # ⚠️ VERIFY url name
                'external': bool(integration_settings.bulk_sms_provider_url),
            })

        # ---------------- SCHOOL (ADMIN) RESOURCES ----------------
        school_resources = [
            {
                'title': 'Bulk SMS / Communication Center',
                'description': 'Send announcements and bulk SMS to parents, teachers, and students.',
                'icon': 'bi-megaphone',
                'url': integration_settings.bulk_sms_provider_url or _safe_reverse('communication:bulk_sms_dashboard'),  # ⚠️ VERIFY url name
                'external': bool(integration_settings.bulk_sms_provider_url),
            },
            {
                'title': 'Google Workspace Admin',
                'description': "Manage your school's Google for Education domain.",
                'icon': 'bi-google',
                'url': integration_settings.google_workspace_admin_url or 'https://admin.google.com/',
                'external': True,
            },
            {
                'title': 'Microsoft 365 Admin Center',
                'description': "Manage your school's Microsoft Teams for Education tenant.",
                'icon': 'bi-microsoft',
                'url': integration_settings.microsoft_365_admin_url or 'https://admin.microsoft.com/',
                'external': True,
            },
            {
                'title': 'E-Learning Overview',
                'description': 'Monitor lesson notes, materials, and live class activity school-wide.',
                'icon': 'bi-mortarboard',
                'url': _safe_reverse('elearning:admin_dashboard'),   # ⚠️ VERIFY url name
                'external': False,
            },
        ]

        context = {
            'is_school_admin': is_school_admin,
            'is_teacher': is_teacher,
            'is_student': is_student,
            'student_resources': student_resources if (is_student or is_school_admin) else [],
            'teacher_resources': teacher_resources if (is_teacher or is_school_admin) else [],
            'school_resources': school_resources if is_school_admin else [],
            'integration_settings': integration_settings,
        }
        return render(request, self.template_name, context)


class HybridIntegrationSettingsUpdateView(LoginRequiredMixin, View):
    """
    Lets school admins (superuser/staff) update the external integration
    links directly from the hub page, instead of going through /admin/.
    """

    def post(self, request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.is_staff):
            messages.error(request, "You are not authorized to update integration settings.")
            return redirect('pages:hybrid_integration_hub')  # ⚠️ VERIFY url name

        integration_settings = HybridIntegrationSettings.get_solo()

        integration_settings.google_classroom_url = request.POST.get(
            'google_classroom_url', integration_settings.google_classroom_url).strip()
        integration_settings.google_meet_url = request.POST.get(
            'google_meet_url', integration_settings.google_meet_url).strip()
        integration_settings.google_workspace_admin_url = request.POST.get(
            'google_workspace_admin_url', integration_settings.google_workspace_admin_url).strip()

        integration_settings.microsoft_teams_url = request.POST.get(
            'microsoft_teams_url', integration_settings.microsoft_teams_url).strip()
        integration_settings.microsoft_365_admin_url = request.POST.get(
            'microsoft_365_admin_url', integration_settings.microsoft_365_admin_url).strip()

        integration_settings.bulk_sms_enabled = request.POST.get('bulk_sms_enabled') == 'on'
        integration_settings.bulk_sms_provider_name = request.POST.get(
            'bulk_sms_provider_name', integration_settings.bulk_sms_provider_name).strip()
        integration_settings.bulk_sms_provider_url = request.POST.get(
            'bulk_sms_provider_url', integration_settings.bulk_sms_provider_url).strip()

        integration_settings.zoom_url = request.POST.get('zoom_url', integration_settings.zoom_url).strip()

        integration_settings.updated_by = request.user
        integration_settings.save()

        messages.success(request, "Integration settings updated successfully.")
        return redirect('pages:hybrid_integration_hub')  # ⚠️ VERIFY url name