from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.http import JsonResponse
from .models import Quiz, Question, Answer, QuizResult, QuizAttempt
from .models import Examination
from .forms import AdminQuizForm, QuestionForm, BulkQuestionUploadForm
from staff.models import Teacher
from django.core.exceptions import PermissionDenied
import csv
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Q, F
from curriculum.models import Standard, Subject
import csv
import io

from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import ListFlowable, ListItem
from reportlab.platypus import Table
from reportlab.platypus import TableStyle
from reportlab.platypus import KeepTogether
from reportlab.platypus import HRFlowable
from reportlab.platypus import PageBreak
from reportlab.platypus import Image
from reportlab.platypus import Frame
from reportlab.platypus import BaseDocTemplate
from reportlab.platypus import FrameBreak
from reportlab.platypus import NextPageTemplate
from reportlab.platypus import PageTemplate
from reportlab.platypus import Indenter
from reportlab.platypus import Flowable
from reportlab.platypus import Preformatted
from reportlab.platypus import XPreformatted
from reportlab.platypus import LongTable
from reportlab.platypus import ListFlowable
from reportlab.platypus import ListItem
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Spacer
from reportlab.lib.units import inch
from reportlab.platypus import Table
from reportlab.platypus import TableStyle
from reportlab.lib import colors


@login_required
def export_questions(request, quiz_id, export_type):
    user = request.user
    teacher = None if user.is_superuser or user.is_staff else get_object_or_404(Teacher, user=user)

    quiz = get_object_or_404(Quiz, id=quiz_id)

    # Security check
    if not (user.is_superuser or user.is_staff):
        if quiz.examination.standard not in teacher.standards_assigned.all():
            messages.error(request, "Access Denied.")
            return redirect('cbt:main-view')

    questions = quiz.question_set.all()

    # ================= CSV EXPORT =================
    if export_type == "csv":
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{quiz.subject}_questions.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Question",
            "Question Type",
            "Option A",
            "Option B",
            "Option C",
            "Option D",
            "Correct Answer",
        ])

        for q in questions:
            writer.writerow([
                q.content,
                q.question_type,
                q.option_a,
                q.option_b,
                q.option_c,
                q.option_d,
                q.correct_answer,
            ])

        return response

    # ================= PDF EXPORT =================
    elif export_type == "pdf":
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{quiz.subject}_questions.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        title = Paragraph(
            f"<b>{quiz.subject} - {quiz.examination}</b>",
            styles['Heading2']
        )
        elements.append(title)
        elements.append(Spacer(1, 0.3 * inch))

        for index, q in enumerate(questions, start=1):
            question_text = Paragraph(f"<b>Q{index}:</b> {q.content}", styles['Normal'])
            elements.append(question_text)
            elements.append(Spacer(1, 0.1 * inch))

            if q.question_type == "MCQ":
                elements.append(Paragraph(f"A. {q.option_a}", styles['Normal']))
                elements.append(Paragraph(f"B. {q.option_b}", styles['Normal']))
                elements.append(Paragraph(f"C. {q.option_c}", styles['Normal']))
                elements.append(Paragraph(f"D. {q.option_d}", styles['Normal']))
                elements.append(Spacer(1, 0.1 * inch))

            elements.append(
                Paragraph(f"<b>Correct Answer:</b> {q.correct_answer}", styles['Normal'])
            )
            elements.append(Spacer(1, 0.3 * inch))

        doc.build(elements)
        return response

    return redirect('cbt:main-view')




# Create your views here.
@login_required
def cbt_home(request):
    return render(request, 'cbt/cbt_home.html')
@login_required
def cbt_order(request):
    return render(request, 'cbt/cbt_order_form.html')

@login_required
def cbt_teacher_order(request):
    return render(request, 'cbt/cbt_teacher_request.html')

@login_required
def student_cbt_home(request):
    """
    Renders the CBT student landing page.
    """
    return render(request, 'cbt/cbt_student_request.html')


@login_required
def submit_cbt_request(request):
    """
    Handles the submission of a CBT exam request form from a teacher.
    Processes the data and sends an email to the school administration.
    """
    if request.method == 'POST':
        teacher_name = request.POST.get('teacher_name')
        subject = request.POST.get('subject')
        class_level = request.POST.get('class_level')
        proposed_date = request.POST.get('proposed_date')
        details = request.POST.get('details')

        email_subject = f"New CBT Exam Request from {teacher_name}"
        email_body = render_to_string('cbt/email_template.html', {
            'teacher_name': teacher_name,
            'subject': subject,
            'class_level': class_level,
            'proposed_date': proposed_date,
            'details': details,
            'user_email': request.user.email,
        })

        try:
            # Send the email to the school administration
            send_mail(
                subject=email_subject,
                message="",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.ADMIN_EMAIL],  # Use the ADMIN_EMAIL from settings
                html_message=email_body,
            )
            messages.success(request, "Your request has been successfully submitted! The administration will contact you shortly.")
        except Exception as e:
            messages.error(request, "An error occurred while submitting your request. Please try again or contact the administrator.")

        return redirect(reverse('cbt:cbt_teacher_order'))

    return render(request, 'cbt/request_exam.html')



# CBT Logics

@login_required
def quiz_list_view(request):
    user = request.user
    teacher_profile = None

    today = timezone.localdate()
    now = timezone.localtime().time()

    # Base Active Quiz Filter (DO NOT TOUCH – your timing logic remains)
    quizzes_qs = Quiz.objects.select_related(
        'examination',
        'subject',
        'examination__standard',
        'session'
    ).filter(
        active=True,
        start_date__lte=today,
        end_date__gte=today,
        start_time__lte=now,
        end_time__gte=now
    )

    # ================= STUDENT =================
    if hasattr(user, 'student'):
        student_profile = user.student

        if student_profile.student_status == 'active':
            student_class = student_profile.current_class
            quizzes = quizzes_qs.filter(standard=student_class)
        else:
            quizzes = Quiz.objects.none()

    # ================= STAFF / ADMIN =================
    elif user.is_staff and not hasattr(user, 'teacher'):
        # Admin or staff without teacher profile
        quizzes = quizzes_qs

    # ================= TEACHER =================
    elif hasattr(user, 'teacher'):
        teacher_profile = Teacher.objects.prefetch_related(
            'standards_assigned',
            'subjects_taught'
        ).get(user=user)

        quizzes = quizzes_qs.filter(
            standard__in=teacher_profile.standards_assigned.all(),
            subject__in=teacher_profile.subjects_taught.all()
        )

    else:
        quizzes = Quiz.objects.none()

    return render(request, 'cbt/main.html', {
        'quizzes': quizzes,
        'teacher_profile': teacher_profile
    })



@login_required
def quiz_detail_view(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    return render(request, 'cbt/quiz.html', {'obj': quiz})



@login_required
def quiz_data_view(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk)
    user = request.user

    # 1️⃣ Block if user already has a VALID completed result
    existing_result = QuizResult.objects.filter(
        user=user,
        quiz=quiz,
        cancelled=False
    ).exists()

    if existing_result:
        return JsonResponse(
            {'error': 'You have already completed this examination.'},
            status=403
        )

    # 2️⃣ Check for existing active attempt (not cancelled)
    attempt = QuizAttempt.objects.filter(
        user=user,
        quiz=quiz,
        completed=False,
        cancelled=False
    ).first()

    # 3️⃣ If no valid attempt exists, create a new one
    if not attempt:
        attempt = QuizAttempt.objects.create(
            user=user,
            quiz=quiz
        )

    # 4️⃣ Format the questions for the JS frontend
    questions = []
    for q in quiz.get_questions():
        questions.append({
            'id': q.id,
            'text': q.content,
            'type': q.question_type,
            'image': q.direct_image_url,
            'options': {
                'A': q.option_a,
                'B': q.option_b,
                'C': q.option_c,
                'D': q.option_d,
            } if q.question_type == 'MCQ' else None
        })

    # 5️⃣ Return data + time remaining
    return JsonResponse({
        'data': questions,
        'time_left': attempt.get_time_left(),
    })


    
@login_required
def save_quiz_view(request, pk):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        quiz = get_object_or_404(Quiz, pk=pk)
        user = request.user

        # Block if valid (non-cancelled) result already exists
        existing_result = QuizResult.objects.filter(
            quiz=quiz,
            user=user,
            cancelled=False
        ).exists()

        if existing_result:
            return JsonResponse({'error': 'Already submitted'}, status=400)

        data = request.POST
        score = 0
        results = []
        questions = quiz.get_questions()

        for q in questions:
            student_answer = data.get(str(q.id))
            is_correct = False

            if student_answer:
                if q.check_answer(student_answer):
                    score += 1
                    is_correct = True

            results.append({
                'question': q.content,
                'correct': q.correct_answer,
                'answered': student_answer if student_answer else "No Answer",
                'is_correct': is_correct
            })

        multiplier = 100 / quiz.number_of_questions
        final_score = score * multiplier
        passed = final_score >= quiz.required_score_to_pass

        # ✅ Save Result
        QuizResult.objects.create(
            quiz=quiz,
            user=user,
            score=final_score,
            passed=passed
        )

        # ✅ IMPORTANT: Mark active attempt as completed
        QuizAttempt.objects.filter(
            user=user,
            quiz=quiz,
            completed=False,
            cancelled=False
        ).update(completed=True)

        return JsonResponse({
            'passed': passed,
            'score': round(final_score, 2),
            'results': results
        })




@login_required
def admin_add_quiz(request):
    """
    Only accessible to superuser or staff.
    Admin creates quizzes for teachers to add questions to.
    """
    # 1️⃣ Access Control
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "Access Denied: Only admin/staff can create quizzes.")
        return redirect('cbt:main-view')

    if request.method == 'POST':
        form = AdminQuizForm(request.POST)

        if form.is_valid():
            quiz = form.save(commit=False)

            # Auto-fill system fields
            quiz.session = quiz.examination.session
            quiz.standard = quiz.examination.standard
            quiz.number_of_questions = 0  # Start at 0 questions

            # Prevent duplicates using get_or_create
            quiz_obj, created = Quiz.objects.get_or_create(
                examination=quiz.examination,
                subject=quiz.subject,
                term=quiz.term,
                session=quiz.session,
                defaults={
                    "required_score_to_pass": 50,
                    "active": True,
                    "standard": quiz.standard,
                    "number_of_questions": 0,
                }
            )

            if not created:
                messages.warning(
                    request,
                    "A quiz already exists for this Examination, Subject, Term, and Session. "
                    "You can continue adding questions below."
                )
            else:
                messages.success(
                    request,
                    f"Quiz for {quiz_obj.subject} created successfully! Now, add questions."
                )

            # Redirect to add question page (teacher/admin can add)
            return redirect('cbt:teacher-add-question', quiz_id=quiz_obj.id)

    else:
        form = AdminQuizForm()

    return render(request, 'cbt/admin_add_quiz.html', {
        'form': form
    })



# @login_required
# def teacher_add_question(request, quiz_id=None):
#     """
#     Teachers can see a list of quizzes and add questions to assigned quizzes.
#     Staff and superuser can add to any quiz.
#     """
#     user = request.user

#     # 1️⃣ No quiz_id → show quiz selection page
#     if not quiz_id:
#         teacher = None
#         try:
#             teacher = Teacher.objects.get(user=user)
#         except Teacher.DoesNotExist:
#             pass

#         if user.is_staff or user.is_superuser:
#             quizzes = Quiz.objects.all()
#         elif teacher:
#             quizzes = Quiz.objects.filter(
#                 subject__in=teacher.subjects_taught.all(),
#                 examination__standard__in=teacher.standards_assigned.all()
#             )
#         else:
#             messages.error(request, "Access Denied.")
#             return redirect('cbt:main-view')

#         return render(request, "cbt/teacher_select_quiz.html", {"quizzes": quizzes})

#     # 2️⃣ quiz_id provided → go to add question form
#     quiz = get_object_or_404(Quiz, id=quiz_id)

#     # Security check for teachers
#     if not (user.is_staff or user.is_superuser):
#         try:
#             teacher = Teacher.objects.get(user=user)
#         except Teacher.DoesNotExist:
#             raise PermissionDenied("You must be a registered teacher.")

#         is_authorized_standard = quiz.examination.standard in teacher.standards_assigned.all()
#         is_authorized_subject = quiz.subject in teacher.subjects_taught.all()
#         if not (is_authorized_standard and is_authorized_subject):
#             messages.error(request, "Access Denied: You are not assigned to this Class or Subject.")
#             return redirect('cbt:main-view')

#     # 3️⃣ Handle form submission
#     if request.method == 'POST':
#         form = QuestionForm(request.POST)
#         if form.is_valid():
#             question = form.save(commit=False)
#             question.quiz = quiz
#             question.save()

#             # Update quiz question count
#             Quiz.objects.filter(id=quiz.id).update(number_of_questions=F('number_of_questions') + 1)

#             messages.success(request, "Question added successfully!")

#             if 'add_another' in request.POST:
#                 return redirect('cbt:teacher-add-question-quiz', quiz_id=quiz.id)

#             return redirect('cbt:main-view')
#     else:
#         form = QuestionForm()

#     return render(request, 'cbt/teacher_add_question.html', {
#         'form': form,
#         'quiz': quiz
#     })

@login_required
def teacher_add_question(request, quiz_id=None):
    """
    Teachers can see a list of quizzes and add questions to assigned quizzes.
    Staff and superuser can add to any quiz.
    """
    user = request.user

    # 1️⃣ No quiz_id → show quiz selection page
    if not quiz_id:
        teacher = None
        try:
            teacher = Teacher.objects.get(user=user)
        except Teacher.DoesNotExist:
            pass
     
        # ===== BASE QUERYSET (UNCHANGED LOGIC) =====
        if user.is_staff or user.is_superuser:
            quizzes = Quiz.objects.select_related(
                'subject',
                'examination',
                'standard'
            ).all()
        elif teacher:
            quizzes = Quiz.objects.select_related(
                'subject',
                'examination',
                'standard'
            ).filter(
                subject__in=teacher.subjects_taught.all(),
                examination__standard__in=teacher.standards_assigned.all()
            )
        else:
            messages.error(request, "Access Denied.")
            return redirect('cbt:main-view')

        # ===== FILTER PARAMETERS (NEW – SAFE) =====
        standard_id = request.GET.get('standard')
        subject_id = request.GET.get('subject')
        term = request.GET.get('term')

        if standard_id:
            quizzes = quizzes.filter(standard_id=standard_id)

        if subject_id:
            quizzes = quizzes.filter(subject_id=subject_id)

        if term:
            quizzes = quizzes.filter(term=term)

        # ===== FILTER DROPDOWN DATA =====
        standards = Standard.objects.all()
        subjects = Subject.objects.all()
        terms = Quiz.objects.values_list('term', flat=True).distinct()

        return render(request, "cbt/teacher_select_quiz.html", {
            "quizzes": quizzes,
            "standards": standards,
            "subjects": subjects,
            "terms": terms,
        })

    # 2️⃣ quiz_id provided → go to add question form
    quiz = get_object_or_404(Quiz, id=quiz_id)

    # Security check for teachers (UNCHANGED)
    if not (user.is_staff or user.is_superuser):
        try:
            teacher = Teacher.objects.get(user=user)
        except Teacher.DoesNotExist:
            raise PermissionDenied("You must be a registered teacher.")

        is_authorized_standard = quiz.examination.standard in teacher.standards_assigned.all()
        is_authorized_subject = quiz.subject in teacher.subjects_taught.all()

        if not (is_authorized_standard and is_authorized_subject):
            messages.error(request, "Access Denied: You are not assigned to this Class or Subject.")
            return redirect('cbt:main-view')

    # 3️⃣ Handle form submission (UNCHANGED)
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            question.save()

            # Update quiz question count
            Quiz.objects.filter(id=quiz.id).update(
                number_of_questions=F('number_of_questions') + 1
            )

            messages.success(request, "Question added successfully!")

            if 'add_another' in request.POST:
                return redirect('cbt:teacher-add-question-quiz', quiz_id=quiz.id)

            return redirect('cbt:main-view')
    else:
        form = QuestionForm()

    return render(request, 'cbt/teacher_add_question.html', {
        'form': form,
        'quiz': quiz,

    })


# TEACHER VIEW QUESTIONS

@login_required
def teacher_view_questions(request, quiz_id=None):
    user = request.user
    teacher = None if user.is_superuser or user.is_staff else get_object_or_404(Teacher, user=user)

    # Filter quizzes based on access
    if user.is_superuser or user.is_staff:
        quizzes = Quiz.objects.all().select_related('subject', 'examination', 'standard')
    else:
        quizzes = Quiz.objects.filter(
            examination__standard__in=teacher.standards_assigned.all()
        ).select_related('subject', 'examination', 'standard')

    selected_quiz = None
    questions = None

    # ✅ FIX: support both URL param and GET param
    quiz_id = quiz_id or request.GET.get('quiz_id')

    if quiz_id:
        selected_quiz = get_object_or_404(Quiz, id=quiz_id)

        # Restrict access for normal teachers
        if not (user.is_superuser or user.is_staff) and \
           selected_quiz.examination.standard not in teacher.standards_assigned.all():
            messages.error(request, "Access Denied.")
            return redirect('cbt:main-view')

        questions = selected_quiz.question_set.all()

    return render(request, 'cbt/teacher_view_questions.html', {
        'quizzes': quizzes,
        'selected_quiz': selected_quiz,
        'questions': questions,
    })



@login_required
def teacher_results_view(request):
    user = request.user

    # 1. Base queryset (staff & superuser can see everything)
    if user.is_staff or user.is_superuser:
        results = QuizResult.objects.select_related(
            'user',
            'quiz',
            'quiz__examination',
            'quiz__subject'
        ).order_by('-timestamp')

        assigned_standards = Standard.objects.all()
        exams = Examination.objects.all()

    else:
        # 2. Normal teacher flow (UNCHANGED logic)
        teacher = get_object_or_404(Teacher, user=user)

        results = QuizResult.objects.filter(
            quiz__standard__in=teacher.standards_assigned.all()
        ).select_related(
            'user',
            'quiz',
            'quiz__examination',
            'quiz__subject'
        ).order_by('-timestamp')

        assigned_standards = teacher.standards_assigned.all()
        exams = Examination.objects.filter(
            standard__in=assigned_standards
        ).distinct()

    # 3. Apply filters (shared by both)
    exam_id = request.GET.get('examination')
    standard_id = request.GET.get('standard')

    if exam_id:
        results = results.filter(quiz__examination_id=exam_id)
    if standard_id:
        results = results.filter(quiz__standard_id=standard_id)

    # ✅ 4. ADD RETAKE DETECTION (NEW ADDITION)
    for res in results:
        attempt_count = QuizResult.objects.filter(
            user=res.user,
            quiz=res.quiz
        ).count()

        res.is_retake = attempt_count > 1

    return render(request, 'cbt/teacher_results.html', {
        'results': results,
        'exams': exams,
        'standards': assigned_standards,
    })


# CBT Results Dwonload
@login_required
def export_results_csv(request):
    examination = request.GET.get('examination')
    standard = request.GET.get('standard')
   

    results = QuizResult.objects.select_related(
        'user', 'quiz', 'quiz__standard'
    )

    # Apply same filters as the page
    if examination:
        results = results.filter(quiz__exam_id=examination)

    if standard:
        results = results.filter(quiz__standard_id=standard)

    response = HttpResponse(
        content_type='text/csv'
    )
    response['Content-Disposition'] = 'attachment; filename="student_CBT_results.csv"'

    writer = csv.writer(response)

    # CSV Header
    writer.writerow([
        'Student Name',
        'Username',
        'Class',
        'Examination',
        'Term',
        'Session',
        'Subject',
        'Score (%)',
        'Status',
        'Date Taken'
    ])

    # CSV Rows
    for res in results:
        writer.writerow([
            res.user.get_full_name() or res.user.username,
            res.user.username,
            res.quiz.standard.name if res.quiz.standard else '',
            res.quiz.examination.name if res.quiz.examination.name else '',
            res.quiz.term if res.quiz.term else '',
            res.quiz.session.name if res.quiz.session.name else '',


            res.quiz.subject,
            round(res.score, 1),
            'Passed' if res.passed else 'Failed',
            res.timestamp.strftime('%Y-%m-%d %H:%M')
        ])

    return response


# Bulk CBT Upload

# @login_required
# def teacher_bulk_upload_questions(request, quiz_id):
#     """
#     Allows teachers and admins to bulk upload questions for a quiz via CSV.
#     Does not alter any existing view logic.
#     """
#     user = request.user
#     quiz = get_object_or_404(Quiz, id=quiz_id)

#     # ── PERMISSION CHECK (mirrors teacher_add_question logic) ──────────────
#     if not (user.is_staff or user.is_superuser):
#         try:
#             teacher = Teacher.objects.get(user=user)
#         except Teacher.DoesNotExist:
#             raise PermissionDenied("You must be a registered teacher.")

#         is_authorized_standard = quiz.examination.standard in teacher.standards_assigned.all()
#         is_authorized_subject = quiz.subject in teacher.subjects_taught.all()

#         if not (is_authorized_standard and is_authorized_subject):
#             messages.error(request, "Access Denied: You are not assigned to this Class or Subject.")
#             return redirect('cbt:main-view')

#     # ── HANDLE CSV TEMPLATE DOWNLOAD ───────────────────────────────────────
#     if request.GET.get('download_template'):
#         import csv
#         from django.http import HttpResponse

#         response = HttpResponse(content_type='text/csv')
#         response['Content-Disposition'] = 'attachment; filename="questions_template.csv"'

#         writer = csv.writer(response)
#         # Header row
#         writer.writerow([
#             'content',
#             'question_type',
#             'option_a',
#             'option_b',
#             'option_c',
#             'option_d',
#             'correct_answer',
#             'image_url',
#         ])
#         # Two example rows so the teacher understands the format
#         writer.writerow([
#             'What is the capital of Nigeria?',
#             'MCQ',
#             'Lagos',
#             'Abuja',
#             'Kano',
#             'Ibadan',
#             'B',
#             '',
#         ])
#         writer.writerow([
#             'The largest planet in the solar system is ___',
#             'SHORT',
#             '',
#             '',
#             '',
#             '',
#             'Jupiter',
#             '',
#         ])
#         return response

#     # ── HANDLE CSV UPLOAD ──────────────────────────────────────────────────
#     form = BulkQuestionUploadForm()
#     errors = []
#     preview_rows = []
#     success_count = 0

#     if request.method == 'POST':
#         form = BulkQuestionUploadForm(request.POST, request.FILES)

#         if form.is_valid():
#             csv_file = request.FILES['csv_file']

#             # Validate file extension
#             if not csv_file.name.endswith('.csv'):
#                 messages.error(request, "Invalid file type. Please upload a .csv file.")
#                 return render(request, 'cbt/bulk_upload_questions.html', {
#                     'form': form,
#                     'quiz': quiz,
#                     'errors': errors,
#                     'success_count': success_count,
#                 })

#             # Decode the uploaded file safely
#             try:
#                 decoded = csv_file.read().decode('utf-8-sig')  # utf-8-sig handles Excel BOM
#             except UnicodeDecodeError:
#                 messages.error(request, "Could not read the file. Please ensure it is saved as UTF-8 CSV.")
#                 return render(request, 'cbt/bulk_upload_questions.html', {
#                     'form': form,
#                     'quiz': quiz,
#                     'errors': errors,
#                     'success_count': success_count,
#                 })

#             reader = csv.DictReader(io.StringIO(decoded))

#             # Validate headers
#             required_headers = {'content', 'question_type', 'correct_answer'}
#             if not required_headers.issubset(set(reader.fieldnames or [])):
#                 messages.error(
#                     request,
#                     f"Missing required columns. Your CSV must have at least: "
#                     f"{', '.join(required_headers)}. Download the template for reference."
#                 )
#                 return render(request, 'cbt/bulk_upload_questions.html', {
#                     'form': form,
#                     'quiz': quiz,
#                     'errors': errors,
#                     'success_count': success_count,
#                 })

#             questions_to_create = []

#             for row_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header

#                 row_errors = []

#                 # ── Validate content ───────────────────────────────────────
#                 content = row.get('content', '').strip()
#                 if not content:
#                     row_errors.append(f"Row {row_num}: 'content' is empty — skipped.")
#                     errors.extend(row_errors)
#                     continue

#                 # ── Validate question_type ─────────────────────────────────
#                 question_type = row.get('question_type', 'MCQ').strip().upper()
#                 if question_type not in ('MCQ', 'SHORT'):
#                     row_errors.append(
#                         f"Row {row_num}: Invalid question_type '{question_type}'. "
#                         f"Use MCQ or SHORT — defaulting to MCQ."
#                     )
#                     question_type = 'MCQ'

#                 # ── Validate correct_answer ────────────────────────────────
#                 correct_answer = row.get('correct_answer', '').strip()
#                 if not correct_answer:
#                     row_errors.append(f"Row {row_num}: 'correct_answer' is empty — skipped.")
#                     errors.extend(row_errors)
#                     continue

#                 if question_type == 'MCQ':
#                     if correct_answer.upper() not in ('A', 'B', 'C', 'D'):
#                         row_errors.append(
#                             f"Row {row_num}: For MCQ, correct_answer must be A, B, C, or D. "
#                             f"Got '{correct_answer}' — skipped."
#                         )
#                         errors.extend(row_errors)
#                         continue

#                 # ── Optional fields ────────────────────────────────────────
#                 option_a = row.get('option_a', '').strip() or None
#                 option_b = row.get('option_b', '').strip() or None
#                 option_c = row.get('option_c', '').strip() or None
#                 option_d = row.get('option_d', '').strip() or None
#                 image_url = row.get('image_url', '').strip() or None

#                 # Warn if MCQ has no options
#                 if question_type == 'MCQ' and not any([option_a, option_b, option_c, option_d]):
#                     row_errors.append(
#                         f"Row {row_num}: MCQ question has no options (A–D). "
#                         f"Question will be saved but options are blank."
#                     )

#                 # Collect non-fatal warnings
#                 errors.extend(row_errors)

#                 questions_to_create.append(
#                     Question(
#                         quiz=quiz,
#                         content=content,
#                         question_type=question_type,
#                         option_a=option_a,
#                         option_b=option_b,
#                         option_c=option_c,
#                         option_d=option_d,
#                         correct_answer=correct_answer,
#                         image_url=image_url,
#                     )
#                 )

#                 preview_rows.append({
#                     'row': row_num,
#                     'content': content[:60],
#                     'type': question_type,
#                     'answer': correct_answer,
#                     'status': 'Ready' if not row_errors else 'Warning',
#                 })

#             # ── Bulk insert all valid questions in one DB query ────────────
#             if questions_to_create:
#                 Question.objects.bulk_create(questions_to_create)
#                 success_count = len(questions_to_create)

#                 # Update quiz question count in one query
#                 Quiz.objects.filter(id=quiz.id).update(
#                     number_of_questions=F('number_of_questions') + success_count
#                 )

#                 messages.success(
#                     request,
#                     f"{success_count} question(s) uploaded successfully to '{quiz.exam_name}'."
#                 )
#             else:
#                 messages.warning(request, "No valid questions found in the file. Check the errors below.")

#     return render(request, 'cbt/bulk_upload_questions.html', {
#         'form': form,
#         'quiz': quiz,
#         'errors': errors,
#         'preview_rows': preview_rows,
#         'success_count': success_count,
#     })

@login_required
def teacher_bulk_upload_questions(request, quiz_id):
    user = request.user
    quiz = get_object_or_404(Quiz, id=quiz_id)

    # ── PERMISSION CHECK ───────────────────────────────────────────────────
    if not (user.is_staff or user.is_superuser):
        try:
            teacher = Teacher.objects.get(user=user)
        except Teacher.DoesNotExist:
            raise PermissionDenied("You must be a registered teacher.")

        is_authorized_standard = quiz.examination.standard in teacher.standards_assigned.all()
        is_authorized_subject = quiz.subject in teacher.subjects_taught.all()

        if not (is_authorized_standard and is_authorized_subject):
            messages.error(request, "Access Denied: You are not assigned to this Class or Subject.")
            return redirect('cbt:main-view')

    # ── HANDLE CSV TEMPLATE DOWNLOAD ───────────────────────────────────────
    if request.GET.get('download_template'):
        from django.http import HttpResponse  # this one is fine inline

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="questions_template.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'content', 'question_type', 'option_a', 'option_b',
            'option_c', 'option_d', 'correct_answer', 'image_url',
        ])
        writer.writerow([
            'What is the capital of Nigeria?', 'MCQ',
            'Lagos', 'Abuja', 'Kano', 'Ibadan', 'B', '',
        ])
        writer.writerow([
            'The largest planet in the solar system is ___',
            'SHORT', '', '', '', '', 'Jupiter', '',
        ])
        return response

    # ── HANDLE CSV UPLOAD ──────────────────────────────────────────────────
    form = BulkQuestionUploadForm()
    errors = []
    preview_rows = []
    success_count = 0

    if request.method == 'POST':
        form = BulkQuestionUploadForm(request.POST, request.FILES)

        if form.is_valid():
            csv_file = request.FILES['csv_file']

            if not csv_file.name.endswith('.csv'):
                messages.error(request, "Invalid file type. Please upload a .csv file.")
                return render(request, 'cbt/bulk_upload_questions.html', {
                    'form': form, 'quiz': quiz,
                    'errors': errors, 'success_count': success_count,
                })

            try:
                decoded = csv_file.read().decode('utf-8-sig')
            except UnicodeDecodeError:
                messages.error(request, "Could not read the file. Please ensure it is saved as UTF-8 CSV.")
                return render(request, 'cbt/bulk_upload_questions.html', {
                    'form': form, 'quiz': quiz,
                    'errors': errors, 'success_count': success_count,
                })

            reader = csv.DictReader(io.StringIO(decoded))

            required_headers = {'content', 'question_type', 'correct_answer'}
            if not required_headers.issubset(set(reader.fieldnames or [])):
                messages.error(
                    request,
                    f"Missing required columns. Your CSV must have at least: "
                    f"{', '.join(required_headers)}. Download the template for reference."
                )
                return render(request, 'cbt/bulk_upload_questions.html', {
                    'form': form, 'quiz': quiz,
                    'errors': errors, 'success_count': success_count,
                })

            questions_to_create = []

            for row_num, row in enumerate(reader, start=2):

                row_errors = []

                content = row.get('content', '').strip()
                if not content:
                    errors.append(f"Row {row_num}: 'content' is empty — skipped.")
                    continue

                question_type = row.get('question_type', 'MCQ').strip().upper()
                if question_type not in ('MCQ', 'SHORT'):
                    row_errors.append(
                        f"Row {row_num}: Invalid question_type '{question_type}'. "
                        f"Use MCQ or SHORT — defaulting to MCQ."
                    )
                    question_type = 'MCQ'

                correct_answer = row.get('correct_answer', '').strip()
                if not correct_answer:
                    errors.append(f"Row {row_num}: 'correct_answer' is empty — skipped.")
                    continue

                if question_type == 'MCQ' and correct_answer.upper() not in ('A', 'B', 'C', 'D'):
                    row_errors.append(
                        f"Row {row_num}: For MCQ, correct_answer must be A, B, C, or D. "
                        f"Got '{correct_answer}' — skipped."
                    )
                    errors.extend(row_errors)
                    continue

                option_a = row.get('option_a', '').strip() or None
                option_b = row.get('option_b', '').strip() or None
                option_c = row.get('option_c', '').strip() or None
                option_d = row.get('option_d', '').strip() or None
                image_url = row.get('image_url', '').strip() or None

                if question_type == 'MCQ' and not any([option_a, option_b, option_c, option_d]):
                    row_errors.append(
                        f"Row {row_num}: MCQ question has no options (A–D). "
                        f"Question will be saved but options are blank."
                    )

                errors.extend(row_errors)

                questions_to_create.append(
                    Question(
                        quiz=quiz,
                        content=content,
                        question_type=question_type,
                        option_a=option_a,
                        option_b=option_b,
                        option_c=option_c,
                        option_d=option_d,
                        correct_answer=correct_answer,
                        image_url=image_url,
                    )
                )

                preview_rows.append({
                    'row': row_num,
                    'content': content[:60],
                    'type': question_type,
                    'answer': correct_answer,
                    'status': 'Ready' if not row_errors else 'Warning',
                })

            if questions_to_create:
                Question.objects.bulk_create(questions_to_create)
                success_count = len(questions_to_create)

                Quiz.objects.filter(id=quiz.id).update(
                    number_of_questions=F('number_of_questions') + success_count
                )

                messages.success(
                    request,
                    f"{success_count} question(s) uploaded successfully to '{quiz.exam_name}'."
                )
            else:
                messages.warning(request, "No valid questions found in the file. Check the errors below.")

    return render(request, 'cbt/bulk_upload_questions.html', {
        'form': form,
        'quiz': quiz,
        'errors': errors,
        'preview_rows': preview_rows,
        'success_count': success_count,
    })


# =====================================================================
# ✅ NEW — STUDENT-FACING CBT RESULT HISTORY (ADDITIVE ONLY)
# ---------------------------------------------------------------------
# Nothing above this line was modified. This view only READS existing
# QuizResult / Quiz records — it does not create, alter, or delete
# anything, and it does not change any existing URL, view, template,
# or model. It is 100% safe to deploy on a live school without any
# risk to already-running CBT logic (exam taking, grading, teacher
# results, admin, exports, etc. are all untouched).
# =====================================================================

@login_required
def student_cbt_results_view(request):
    """
    Lets a logged-in student view their own CBT result history.

    - Defaults to the student's most recent term/session (their
      "current" term/session, inferred from their latest attempt —
      no assumptions are made about unseen Session model fields).
    - Supports filtering by session, term, and subject.
    - Supports an explicit "view full history" mode across all
      terms/sessions the student has ever sat an exam in.
    - Only ever touches QuizResult rows belonging to request.user —
      a student can never see another student's results here.
    """
    user = request.user

    # Restrict this page to students only. Staff/teachers already have
    # their own dedicated results views (teacher_results_view) and are
    # redirected there instead of erroring out.
    if not hasattr(user, 'student'):
        if user.is_staff or user.is_superuser or hasattr(user, 'teacher'):
            return redirect('cbt:teacher-results-view')
        messages.error(request, "This page is only available to students.")
        return redirect('cbt:main-view')

    student_profile = user.student

    # Every valid (non-cancelled) result for THIS student only.
    base_results = QuizResult.objects.filter(
        user=user,
        cancelled=False
    ).select_related(
        'quiz',
        'quiz__subject',
        'quiz__examination',
        'quiz__session',
        'quiz__standard',
    ).order_by('-timestamp')

    if not base_results.exists():
        return render(request, 'cbt/student_result_history.html', {
            'has_results': False,
            'student_profile': student_profile,
        })

    # Build filter dropdown choices strictly from results this student
    # actually has (so a student never sees an irrelevant filter option).
    session_choices = list(
        base_results.exclude(quiz__session__isnull=True)
        .values_list('quiz__session_id', 'quiz__session__name')
        .distinct()
        .order_by('-quiz__session_id')
    )
    term_choices = list(
        base_results.values_list('quiz__term', flat=True).distinct()
    )
    subject_choices = list(
        base_results.exclude(quiz__subject__isnull=True)
        .values_list('quiz__subject_id', 'quiz__subject__name')
        .distinct()
        .order_by('quiz__subject__name')
    )

    # "Current" term/session = term/session tied to the student's most
    # recent attempt. This avoids guessing at Session model fields that
    # aren't visible from the cbt app (e.g. an is_current flag) while
    # still giving a sensible default "current term" view.
    latest_result = base_results.first()
    current_session_id = latest_result.quiz.session_id if latest_result.quiz else None
    current_term = latest_result.quiz.term if latest_result.quiz else None

    show_all = request.GET.get('all') == '1'

    selected_session = request.GET.get(
        'session', str(current_session_id) if (current_session_id and not show_all) else ''
    )
    selected_term = request.GET.get('term', current_term if not show_all else '')
    selected_subject = request.GET.get('subject', '')

    results_qs = base_results
    if not show_all:
        if selected_session:
            results_qs = results_qs.filter(quiz__session_id=selected_session)
        if selected_term:
            results_qs = results_qs.filter(quiz__term=selected_term)
    if selected_subject:
        results_qs = results_qs.filter(quiz__subject_id=selected_subject)

    results = list(results_qs)

    # Attempt numbering / retake detection, scoped to this student only
    # (mirrors the existing pattern used in teacher_results_view).
    for res in results:
        attempt_ids = list(
            QuizResult.objects.filter(user=user, quiz=res.quiz)
            .order_by('timestamp')
            .values_list('id', flat=True)
        )
        res.attempt_number = (attempt_ids.index(res.id) + 1) if res.id in attempt_ids else 1
        res.is_retake = len(attempt_ids) > 1

    # Summary statistics for the currently filtered result set.
    total_taken = len(results)
    total_passed = sum(1 for r in results if r.passed)
    total_failed = total_taken - total_passed
    average_score = round(sum(r.score for r in results) / total_taken, 1) if total_taken else 0
    best_result = max(results, key=lambda r: r.score) if results else None
    worst_result = min(results, key=lambda r: r.score) if results else None

    # Pagination so long histories (multiple sessions/years) stay fast.
    paginator = Paginator(results, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'has_results': True,
        'student_profile': student_profile,
        'page_obj': page_obj,
        'results': page_obj.object_list,
        'session_choices': session_choices,
        'term_choices': term_choices,
        'subject_choices': subject_choices,
        'selected_session': selected_session,
        'selected_term': selected_term,
        'selected_subject': selected_subject,
        'current_session_id': current_session_id,
        'current_term': current_term,
        'show_all': show_all,
        'total_taken': total_taken,
        'total_passed': total_passed,
        'total_failed': total_failed,
        'average_score': average_score,
        'best_result': best_result,
        'worst_result': worst_result,
    }
    return render(request, 'cbt/student_result_history.html', context)


# =====================================================================
# ✅ NEW — QUESTION BANK / PAST QUESTIONS DOWNLOAD (ADDITIVE ONLY)
# ---------------------------------------------------------------------
# Nothing above this line was modified. Lets staff/teachers browse every
# past Quiz that already has questions attached, filter it by Class
# (Standard), Session, Term and Subject, and download either a single
# quiz's questions or every matching quiz's questions in one combined
# file — for reference/reuse when setting future exams.
#
# No new packages are used: CSV export uses Python's built-in `csv`
# module and PDF export reuses `reportlab`, which is already imported
# and already used by the existing `export_questions` view above.
# =====================================================================

@login_required
def question_bank_view(request):
    """
    Browse past CBT question sets (read-only) filtered by Class, Session,
    Term, Subject, and Examination. Staff/superuser see every quiz with
    questions; teachers only see quizzes for their assigned classes and
    subjects (same access rule already used elsewhere in this file).
    """
    user = request.user
    teacher = None

    # Only quizzes that actually have questions are worth listing here.
    quizzes_qs = Quiz.objects.select_related(
        'examination', 'subject', 'standard', 'session'
    ).filter(number_of_questions__gt=0)

    if user.is_staff or user.is_superuser:
        standards = Standard.objects.all()
        subjects = Subject.objects.all()
        examinations = Examination.objects.all()
    else:
        try:
            teacher = Teacher.objects.get(user=user)
        except Teacher.DoesNotExist:
            messages.error(request, "Access Denied: Only staff and teachers can access the Question Bank.")
            return redirect('cbt:main-view')

        quizzes_qs = quizzes_qs.filter(
            standard__in=teacher.standards_assigned.all(),
            subject__in=teacher.subjects_taught.all(),
        )
        standards = teacher.standards_assigned.all()
        subjects = teacher.subjects_taught.all()
        examinations = Examination.objects.filter(standard__in=standards).distinct()

    # Session/Term choices derived straight from what's actually available
    # to this user, so the dropdowns never show an option with 0 results.
    session_choices = list(
        quizzes_qs.exclude(session__isnull=True)
        .values_list('session_id', 'session__name')
        .distinct()
        .order_by('-session_id')
    )
    term_choices = list(
        quizzes_qs.values_list('term', flat=True).distinct()
    )

    # ── Apply filters ───────────────────────────────────────────────
    selected_standard = request.GET.get('standard', '')
    selected_session = request.GET.get('session', '')
    selected_term = request.GET.get('term', '')
    selected_subject = request.GET.get('subject', '')
    selected_examination = request.GET.get('examination', '')

    quizzes = quizzes_qs
    if selected_standard:
        quizzes = quizzes.filter(standard_id=selected_standard)
    if selected_session:
        quizzes = quizzes.filter(session_id=selected_session)
    if selected_term:
        quizzes = quizzes.filter(term=selected_term)
    if selected_subject:
        quizzes = quizzes.filter(subject_id=selected_subject)
    if selected_examination:
        quizzes = quizzes.filter(examination_id=selected_examination)

    quizzes = quizzes.order_by('standard__name', 'subject__name', 'term', '-session_id')

    return render(request, 'cbt/question_bank.html', {
        'quizzes': quizzes,
        'standards': standards,
        'subjects': subjects,
        'examinations': examinations,
        'session_choices': session_choices,
        'term_choices': term_choices,
        'selected_standard': selected_standard,
        'selected_session': selected_session,
        'selected_term': selected_term,
        'selected_subject': selected_subject,
        'selected_examination': selected_examination,
        'teacher_profile': teacher,
    })


@login_required
def export_question_bank(request, export_type):
    """
    Bulk-downloads EVERY question from EVERY quiz matching the current
    Question Bank filters (class/session/term/subject/examination) as a
    single CSV or PDF file. Mirrors the access rules and file-generation
    style of the existing single-quiz `export_questions` view above —
    just applied across a filtered set of quizzes instead of one.
    """
    user = request.user

    quizzes = Quiz.objects.select_related(
        'examination', 'subject', 'standard', 'session'
    ).filter(number_of_questions__gt=0)

    if not (user.is_staff or user.is_superuser):
        try:
            teacher = Teacher.objects.get(user=user)
        except Teacher.DoesNotExist:
            messages.error(request, "Access Denied: Only staff and teachers can access the Question Bank.")
            return redirect('cbt:main-view')

        quizzes = quizzes.filter(
            standard__in=teacher.standards_assigned.all(),
            subject__in=teacher.subjects_taught.all(),
        )

    # Same filters as question_bank_view, read from the querystring so the
    # "Download All (Filtered)" button can pass through whatever the user
    # currently has selected on the page.
    standard_id = request.GET.get('standard')
    session_id = request.GET.get('session')
    term = request.GET.get('term')
    subject_id = request.GET.get('subject')
    examination_id = request.GET.get('examination')

    if standard_id:
        quizzes = quizzes.filter(standard_id=standard_id)
    if session_id:
        quizzes = quizzes.filter(session_id=session_id)
    if term:
        quizzes = quizzes.filter(term=term)
    if subject_id:
        quizzes = quizzes.filter(subject_id=subject_id)
    if examination_id:
        quizzes = quizzes.filter(examination_id=examination_id)

    questions = Question.objects.filter(
        quiz__in=quizzes
    ).select_related(
        'quiz', 'quiz__subject', 'quiz__standard', 'quiz__examination', 'quiz__session'
    ).order_by('quiz__standard__name', 'quiz__subject__name', 'quiz__term', 'quiz_id', 'id')

    # ================= CSV EXPORT =================
    if export_type == "csv":
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="question_bank.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Class", "Subject", "Examination", "Term", "Session",
            "Question", "Question Type",
            "Option A", "Option B", "Option C", "Option D",
            "Correct Answer",
        ])

        for q in questions:
            writer.writerow([
                q.quiz.standard.name if q.quiz.standard else '',
                q.quiz.subject_name,
                q.quiz.exam_name,
                q.quiz.term,
                q.quiz.session.name if q.quiz.session else '',
                q.content,
                q.question_type,
                q.option_a,
                q.option_b,
                q.option_c,
                q.option_d,
                q.correct_answer,
            ])

        return response

    # ================= PDF EXPORT =================
    elif export_type == "pdf":
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="question_bank.pdf"'

        doc = SimpleDocTemplate(response, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()

        elements.append(Paragraph("<b>Question Bank — Past Questions</b>", styles['Heading1']))
        elements.append(Spacer(1, 0.2 * inch))

        if not questions:
            elements.append(Paragraph(
                "No questions matched the selected filters.", styles['Normal']
            ))

        current_group = None
        question_number = 0

        for q in questions:
            group_key = (
                q.quiz.standard_id, q.quiz.subject_id,
                q.quiz.term, q.quiz.session_id, q.quiz.examination_id,
            )

            if group_key != current_group:
                current_group = group_key
                question_number = 0
                elements.append(Spacer(1, 0.25 * inch))

                header_text = (
                    f"{q.quiz.standard.name if q.quiz.standard else 'N/A'} — "
                    f"{q.quiz.subject_name} — {q.quiz.exam_name} "
                    f"({q.quiz.term} Term, "
                    f"{q.quiz.session.name if q.quiz.session else 'N/A'})"
                )
                elements.append(Paragraph(header_text, styles['Heading3']))
                elements.append(HRFlowable(width="100%", color=colors.grey))
                elements.append(Spacer(1, 0.1 * inch))

            question_number += 1
            elements.append(
                Paragraph(f"<b>Q{question_number}:</b> {q.content}", styles['Normal'])
            )

            if q.question_type == "MCQ":
                elements.append(Paragraph(
                    f"A. {q.option_a}&nbsp;&nbsp;&nbsp; B. {q.option_b}", styles['Normal']
                ))
                elements.append(Paragraph(
                    f"C. {q.option_c}&nbsp;&nbsp;&nbsp; D. {q.option_d}", styles['Normal']
                ))

            elements.append(
                Paragraph(f"<b>Correct Answer:</b> {q.correct_answer}", styles['Normal'])
            )
            elements.append(Spacer(1, 0.15 * inch))

        doc.build(elements)
        return response

    return redirect('cbt:question-bank-view')