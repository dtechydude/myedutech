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
from results.models import Examination
from .forms import TeacherQuizForm, QuestionForm
from staff.models import Teacher
from django.core.exceptions import PermissionDenied
import csv
from django.http import HttpResponse



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

# @login_required
# def quiz_list_view(request):
#     user = request.user
#     teacher_profile = None
    
#     # 1. Start with an optimized QuerySet (Fixes the Slowness)
#     # We join the related tables now so the template doesn't have to later
#     quizzes_qs = Quiz.objects.select_related(
#         'examination', 
#         'subject', 
#         'examination__standard', 
#         'session'
#     )

#     # 2. STUDENT LOGIC
#     if hasattr(user, 'student'):
#         student_profile = user.student
#         if student_profile.student_status == 'active':
#             student_class = student_profile.current_class
#             # Filter quizzes assigned to the student's specific class
#             quizzes = quizzes_qs.filter(standard=student_class, active=True)
#         else:
#             quizzes = Quiz.objects.none()
    
#     # 3. STAFF/TEACHER LOGIC
#     elif user.is_staff:
#         try:
#             # We prefetch the standards/subjects so the button-check in the template is instant
#             teacher_profile = Teacher.objects.prefetch_related(
#                 'standards_assigned', 
#                 'subjects_taught'
#             ).get(user=user)
#             quizzes = quizzes_qs.filter(active=True)
#         except Teacher.DoesNotExist:
#             quizzes = quizzes_qs.filter(active=True)
    
#     else:
#         quizzes = Quiz.objects.none()

#     return render(request, 'cbt/main.html', {
#         'quizzes': quizzes,
#         'teacher_profile': teacher_profile
#     })

from django.contrib.auth.decorators import login_required
from django.utils import timezone

@login_required
def quiz_list_view(request):
    user = request.user
    teacher_profile = None

    today = timezone.localdate()
    now = timezone.localtime().time()

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

    # STUDENT LOGIC
    if hasattr(user, 'student'):
        student_profile = user.student
        if student_profile.student_status == 'active':
            student_class = student_profile.current_class
            quizzes = quizzes_qs.filter(standard=student_class)
        else:
            quizzes = Quiz.objects.none()

    # STAFF / TEACHER LOGIC
    elif user.is_staff:
        try:
            teacher_profile = Teacher.objects.prefetch_related(
                'standards_assigned',
                'subjects_taught'
            ).get(user=user)
            quizzes = quizzes_qs
        except Teacher.DoesNotExist:
            quizzes = quizzes_qs

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
    
    # 1. Prevent access if the user has already submitted this quiz
    if QuizResult.objects.filter(user=user, quiz=quiz).exists():
        return JsonResponse({'error': 'You have already completed this examination.'}, status=403)

    # 2. Track the Attempt (to keep the timer consistent across refreshes)
    attempt, created = QuizAttempt.objects.get_or_create(
        user=user, 
        quiz=quiz, 
        completed=False
    )
    
    # 3. Format the questions for the JS frontend
    questions = []
    for q in quiz.get_questions():
        questions.append({
            'id': q.id,
            'text': q.content, 
            'type': q.question_type,
            # THE FIX: This calls the direct_image_url property from your model
            'image': q.direct_image_url, 
            'options': {
                'A': q.option_a,
                'B': q.option_b,
                'C': q.option_c,
                'D': q.option_d,
            } if q.question_type == 'MCQ' else None
        })
    
    # 4. Return the data and the calculated time remaining
    return JsonResponse({
        'data': questions,
        'time_left': attempt.get_time_left(), 
    })


@login_required
def save_quiz_view(request, pk):
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        quiz = get_object_or_404(Quiz, pk=pk)
        user = request.user
        
        if QuizResult.objects.filter(quiz=quiz, user=user).exists():
            return JsonResponse({'error': 'Already submitted'}, status=400)

        data = request.POST
        # We don't need data.lists() anymore if we loop through questions
        # as it's safer to pull from the DB than trust the POST keys
        
        score = 0
        results = []
        questions = quiz.get_questions() # Get the same questions sent to the user

        for q in questions:
            # Get the answer submitted for this specific question ID
            student_answer = data.get(str(q.id)) 
            
            is_correct = False
            if student_answer:
                # Use the helper method we created in the Question model
                if q.check_answer(student_answer):
                    score += 1
                    is_correct = True
            
            # Record the result for this question
            results.append({
                'question': q.content, # Updated field name from 'text' to 'content'
                'correct': q.correct_answer,
                'answered': student_answer if student_answer else "No Answer",
                'is_correct': is_correct
            })

        # Calculate score percentage
        multiplier = 100 / quiz.number_of_questions
        final_score = score * multiplier
        passed = final_score >= quiz.required_score_to_pass

        # Save the result
        QuizResult.objects.create(
            quiz=quiz, 
            user=user, 
            score=final_score, 
            passed=passed
        )

        return JsonResponse({
            'passed': passed, 
            'score': round(final_score, 2), 
            'results': results
        })
    


@login_required
def teacher_add_quiz(request):
    # 1. Fetch the teacher profile
    try:
        teacher = Teacher.objects.get(user=request.user)
    except Teacher.DoesNotExist:
        messages.error(request, "Access Denied. You must be a registered teacher.")
        return redirect('cbt:main-view')

    if request.method == 'POST':
        # Pass the teacher instance to the form for filtered querysets
        form = TeacherQuizForm(request.POST, teacher=teacher) 
        
        if form.is_valid():
            # 2. Create the object but don't save to DB yet (commit=False)
            quiz = form.save(commit=False)
            
            # 3. Fill in mandatory fields to prevent IntegrityError
            quiz.required_score_to_pass = 50  # Default pass mark
            quiz.active = True               # Make it active immediately
            
            # 4. Pull session and standard from the selected Examination object
            # This ensures the quiz is correctly categorized in the database
            quiz.session = quiz.examination.session
            quiz.standard = quiz.examination.standard
            
            # 5. Final Save to Database
            quiz.save()
            
            # 6. Redirect to Question Creation page instead of the list
            messages.success(request, f"Quiz for {quiz.subject} created! Now, add your questions below.")
            return redirect('cbt:teacher-add-question', quiz_id=quiz.id)
            
    else:
        # GET request: provide an empty form filtered by teacher's access
        form = TeacherQuizForm(teacher=teacher)

    return render(request, 'cbt/teacher_add_quiz.html', {
        'form': form,
        'teacher': teacher
    })

@login_required
def teacher_add_question(request, quiz_id):
    # 1. Get the Quiz
    quiz = get_object_or_404(Quiz, id=quiz_id)
    
    # 2. Get the Teacher Profile
    try:
        teacher = Teacher.objects.get(user=request.user)
    except Teacher.DoesNotExist:
        raise PermissionDenied("You must be a registered teacher to access this.")

    # 3. SECURITY CHECK: Validate Standard and Subject
    # We check if the quiz's standard and subject are in the teacher's allowed lists
    is_authorized_standard = quiz.examination.standard in teacher.standards_assigned.all()
    is_authorized_subject = quiz.subject in teacher.subjects_taught.all()

    if not (is_authorized_standard and is_authorized_subject):
        messages.error(request, "Access Denied: You are not assigned to this Class or Subject.")
        return redirect('cbt:main-view')

    # 4. Handle Form Processing
    if request.method == 'POST':
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.quiz = quiz
            question.save()
            
            messages.success(request, "Question added!")
            
            if 'add_another' in request.POST:
                return redirect('cbt:teacher-add-question', quiz_id=quiz.id)
            return redirect('cbt:main-view')
    else:
        form = QuestionForm()

    return render(request, 'cbt/teacher_add_question.html', {
        'form': form,
        'quiz': quiz
    })


@login_required
def teacher_view_questions(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    # Re-using the security check logic
    teacher = get_object_or_404(Teacher, user=request.user)
    if quiz.examination.standard not in teacher.standards_assigned.all():
        messages.error(request, "Access Denied.")
        return redirect('cbt:main-view')

    questions = quiz.question_set.all()
    return render(request, 'cbt/teacher_view_questions.html', {
        'quiz': quiz,
        'questions': questions
    })


@login_required
def teacher_results_view(request):
    # 1. Get the teacher profile
    teacher = get_object_or_404(Teacher, user=request.user)
    
    # 2. Get filters from the GET request (from the search form)
    exam_id = request.GET.get('examination')
    standard_id = request.GET.get('standard')

    # 3. Base queryset: only show results for standards/classes assigned to this teacher
    # We use select_related to join User, Quiz, and Exam tables in ONE query for speed
    results = QuizResult.objects.filter(
        quiz__standard__in=teacher.standards_assigned.all()
    ).select_related(
        'user', 
        'quiz', 
        'quiz__examination', 
        'quiz__subject'
    ).order_by('-timestamp')

    # 4. Apply Filters
    if exam_id:
        results = results.filter(quiz__examination_id=exam_id)
    if standard_id:
        results = results.filter(quiz__standard_id=standard_id)

    # 5. Data for the dropdown filters in the template
    # Only show exams/standards that this teacher is actually in charge of
    assigned_standards = teacher.standards_assigned.all()
    exams = Examination.objects.filter(standard__in=assigned_standards).distinct()

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
            res.quiz.subject,
            round(res.score, 1),
            'Passed' if res.passed else 'Failed',
            res.timestamp.strftime('%Y-%m-%d %H:%M')
        ])

    return response