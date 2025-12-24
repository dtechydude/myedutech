from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse # Import HttpResponse
from django.db.models import Sum, Avg, F # F object for database expressions
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Sum, Avg, Q, Max, Min # Import Q for complex queries if needed
from curriculum.models import Session, Term, Standard, Subject
from attendance.models import Attendance
from students.models import Student
from students.models import Parent
from django.contrib import messages # Import messages

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.db import transaction
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.forms import formset_factory, modelformset_factory
from .models import Score, MotorAbilityScore, MidTermScore, ResultPublication
from .forms import ScoreEntryForm, ReportCardFilterForm, SessionReportCardFilterForm, MotorAbilityScoreForm, MidTermScoreForm # Import new form
from .utils import get_grade, get_subject_remark, get_overall_remark # Import helper functions
from django.template.loader import render_to_string # Import render_to_string
from curriculum.models import SchoolIdentity
from transport.context_processors import school_identity as school_identity_processor
from django.core.paginator import Paginator

# For PDF generation using django-wkhtmltopdf
# from wkhtmltopdf.views import PDFTemplateResponse # Import this
from django.conf import settings # To access MEDIA_ROOT/STATIC_ROOT if needed for CSS/images

from xhtml2pdf import pisa # ADD THIS IMPORT
import io # Needed for file-like object
from django.template.loader import get_template


# important PLEASE DONT DELETE
def get_student_class_rank(student, standard, term):
    """
    Calculates the overall rank for a single student based on class averages.
    Returns: (student_rank, total_students_in_class)
    """

    # 1. Fetch all students in the class
    students_in_class = Student.objects.filter(current_class=standard)
    total_students = students_in_class.count()
    overall_ranking_data = []

    # 2. Calculate average for EVERY student in the class
    for s in students_in_class:
        # We need Sum imported from django.db.models
        scores = Score.objects.filter(student=s, term=term, total_score__isnull=False)

        total_scores_sum = scores.aggregate(total=Sum('total_score'))['total'] or 0
        subjects_with_scores_count = scores.count()

        overall_average = total_scores_sum / subjects_with_scores_count if subjects_with_scores_count > 0 else 0

        overall_ranking_data.append({
            'student_id': s.id,
            'overall_average': overall_average,
        })

    # 3. Sort and assign ranks (Handling ties)
    overall_ranking_data.sort(key=lambda x: x['overall_average'], reverse=True)

    current_rank = 0
    last_average = -1

    for i, data in enumerate(overall_ranking_data):
        # Tie handling logic: If the average is different from the last, the rank increments
        if data['overall_average'] != last_average:
            current_rank = i + 1
        data['rank'] = current_rank
        last_average = data['overall_average']

        # 4. Find the rank of the specific student
        if data['student_id'] == student.id:
            return current_rank, total_students

    return 'N/A', total_students




def student_session_report_view(request, student_id, session_id):
    student = get_object_or_404(Student, id=student_id)
    session = get_object_or_404(Session, id=session_id)

    # 1. Get all results for this student in this session, prefetching related data
    # We use prefetch_related for 'exam__term' because 'results' is a reverse relationship
    # and select_related for 'subject' as it's a direct FK on Result.
    all_results = Result.objects.filter(
        student=student,
        exam__term__session=session # Filter through exam and term to the session
    ).select_related('subject', 'exam__term', 'exam').order_by('exam__term__start_date', 'exam__date', 'subject__name')

    term_data = {}
    for result in all_results:
        term_name = result.exam.term.name
        if term_name not in term_data:
            term_data[term_name] = {
                'exams': {}, # To store results per exam within this term
                'term_total_score': 0,
                'term_subjects_count': 0
            }

        exam_name = result.exam.name
        if exam_name not in term_data[term_name]['exams']:
            term_data[term_name]['exams'][exam_name] = {
                'exam_date': result.exam.date,
                'subjects': [],
                'exam_total_score': 0
            }

        term_data[term_name]['exams'][exam_name]['subjects'].append({
            'subject_name': result.subject.name,
            'score': result.score
        })
        term_data[term_name]['exams'][exam_name]['exam_total_score'] += result.score
        term_data[term_name]['term_total_score'] += result.score
        term_data[term_name]['term_subjects_count'] += 1 # Count of individual subject scores within term

    # Calculate overall session aggregate
    session_total_score_aggregation = all_results.aggregate(overall_total=Sum('score'))
    session_total_score = session_total_score_aggregation['overall_total'] if session_total_score_aggregation['overall_total'] is not None else 0

    # Calculate overall session average (careful if some exams have more subjects than others)
    # A more precise average might be the average of averages, or total score / total subjects taken
    session_average_score_aggregation = all_results.aggregate(overall_average=Avg('score'))
    session_average_score = session_average_score_aggregation['overall_average'] if session_average_score_aggregation['overall_average'] is not None else 0

    context = {
        'student': student,
        'session': session,
        'term_data': term_data, # This is the structured data for the template
        'session_total_score': session_total_score,
        'session_average_score': session_average_score,
    }
    return render(request, 'results/student_session_report.html', context)




# Working 10/7/2025
@login_required
def my_term_results_view(request, term_id):
    """
    Displays detailed results for the logged-in student for a specific term,
    grouped by exam. This shows individual scores for each subject in each exam.
    """
    try:
        student = request.user.student
    except Student.DoesNotExist:
        return render(request, 'results/no_student_profile.html', {
            'message': 'No student profile linked to your account. Please contact administration.'
        })

    # Get the specific Term object, or return 404 if not found
    term = get_object_or_404(Term, id=term_id)

    # Security check: Ensure the requested term actually has results for *this* student.
    # Although the query below filters by student, this explicit check prevents users
    # from probing invalid term IDs if no data exists for them in that term.
    # It provides a clearer "no results" message rather than an empty table.
    if not Result.objects.filter(student=student, exam__term=term).exists():
        context = {
            'student': student,
            'term': term,
            'results_by_exam': {}, # Empty dictionary for the template
            'term_total_score': 0,
            'term_average_score': 0,
            'message': 'No results available for this term.'
        }
        return render(request, 'results/my_term_results.html', context)


    # Get all results for this student in this specific term.
    # .select_related() is crucial for performance: it fetches related Subject and Exam objects
    # in the same database query, avoiding N+1 query problems in the template loop.
    results = Result.objects.filter(
        student=student,
        exam__term=term
    ).select_related('subject', 'exam').order_by('exam__date', 'subject__name')

    # Organize results by exam within the term for display purposes.
    # This structure makes it easy to loop through exams, then subjects within each exam in the template.
    results_by_exam = {}
    term_total_score = 0
    term_subject_score_count = 0 # To count individual scores for the term average

    for result in results:
        exam_name = result.exam.name

        if exam_name not in results_by_exam:
            results_by_exam[exam_name] = {
                'exam_obj': result.exam, # Store the actual Exam object for details like date
                'subjects': [],
                'exam_total_score': 0,
                'exam_score_count': 0, # Count of scores for this specific exam
            }

        results_by_exam[exam_name]['subjects'].append({
            'subject_name': result.subject.name,
            'score': result.score,
        })
        results_by_exam[exam_name]['exam_total_score'] += result.score
        results_by_exam[exam_name]['exam_score_count'] += 1

        term_total_score += result.score
        term_subject_score_count += 1

    # Calculate term average
    term_average_score = term_total_score / term_subject_score_count if term_subject_score_count > 0 else 0

    context = {
        'student': student,
        'term': term,
        'results_by_exam': results_by_exam, # The structured data for the template
        'term_total_score': term_total_score,
        'term_average_score': term_average_score,
        'message': None # Clear any previous "no results" message if data exists
    }
    return render(request, 'results/my_term_results.html', context)





@login_required
def my_all_results_view(request):
    """
    Displays all detailed results for the logged-in student across all terms and exams.
    """
    try:
        student = request.user.student
    except Student.DoesNotExist:
        return render(request, 'results/no_student_profile.html', {
            'message': 'No student profile linked to your account. Please contact administration.'
        })

    # Get all results for the student, ordered by term, then exam date, then subject name
    all_results = Result.objects.filter(student=student).select_related(
        'subject', 'exam', 'exam__term', 'exam__term__session'
    ).order_by('exam__term__start_date', 'exam__date', 'subject__name')

    # Organize results (optional, but good for display)
    results_by_term = {}
    total_score_overall = 0
    total_subjects_overall = 0

    for result in all_results:
        term_id = result.exam.term.id
        term_name = result.exam.term.name
        session_name = result.exam.term.session.name

        if term_id not in results_by_term:
            results_by_term[term_id] = {
                'term_obj': result.exam.term,
                'session_name': session_name,
                'exams': {},
                'term_total_score': 0,
                'term_subject_count': 0
            }

        exam_id = result.exam.id
        exam_name = result.exam.name
        exam_date = result.exam.date

        if exam_id not in results_by_term[term_id]['exams']:
            results_by_term[term_id]['exams'][exam_id] = {
                'exam_obj': result.exam,
                'subjects': [],
                'exam_total_score': 0,
                'exam_subject_count': 0
            }

        results_by_term[term_id]['exams'][exam_id]['subjects'].append({
            'subject_name': result.subject.name,
            'score': result.score,
        })
        results_by_term[term_id]['exams'][exam_id]['exam_total_score'] += result.score
        results_by_term[term_id]['exams'][exam_id]['exam_subject_count'] += 1

        results_by_term[term_id]['term_total_score'] += result.score
        results_by_term[term_id]['term_subject_count'] += 1

        total_score_overall += result.score
        total_subjects_overall += 1

    overall_average_score = total_score_overall / total_subjects_overall if total_subjects_overall > 0 else 0


    context = {
        'student': student,
        'results_by_term': results_by_term,
        'overall_total_score': total_score_overall,
        'overall_average_score': overall_average_score,
        'message': 'No results found for any term.' if not all_results.exists() else None
    }
    return render(request, 'results/my_all_results.html', context)

# ... (my_terms_list_view, my_term_results_view, student_term_report_card_view remain below this)


# working well 001
class TeacherRequiredMixin(UserPassesTestMixin):
    """Mixin to ensure only users linked to a Teacher profile can access the view."""
    def test_func(self):
        return hasattr(self.request.user, 'teacher')


# New adjustment 002
class ScoreEntryView(LoginRequiredMixin, TeacherRequiredMixin, View):
    template_name = 'results/score_entry.html'

    def get(self, request, *args, **kwargs):
        teacher = request.user.teacher

        current_term = Term.objects.filter(is_current=True).first()
        if not current_term:
            messages.error(request, 'No current term set. Please contact administration.')
            return render(request, self.template_name, {})

        assigned_subjects = teacher.subjects_taught.all()
        assigned_standards = teacher.standards_assigned.all()

        selected_subject = None
        selected_standard = None

        selected_subject_id = request.GET.get('subject', assigned_subjects.first().id if assigned_subjects.exists() else None)
        selected_standard_id = request.GET.get('standard', assigned_standards.first().id if assigned_standards.exists() else None)

        students_in_standard = []
        # Keep default extra=0 here
        ScoreFormSet = formset_factory(ScoreEntryForm, extra=0)
        formset = ScoreFormSet()

        if selected_subject_id and selected_standard_id:
            try:
                selected_subject = Subject.objects.get(id=selected_subject_id)
                selected_standard = Standard.objects.get(id=selected_standard_id)
            except (Subject.DoesNotExist, Standard.DoesNotExist):
                messages.error(request, 'Invalid subject or standard selected.')

            if selected_subject and selected_standard:
                students_in_standard = Student.objects.filter(current_class=selected_standard).order_by('first_name', 'last_name')

                initial_data = []
                for student in students_in_standard:
                    # Retrieve existing score instance (or None if not scored yet)
                    score_instance = Score.objects.filter(
                        student=student,
                        subject=selected_subject,
                        term=current_term
                    ).first()

                    # Populate initial data dictionary for this student
                    initial_data.append({
                        'student_id': student.id,
                        'student_name': student.get_full_name(),
                        'score_id': score_instance.id if score_instance else None,
                        'ca1': score_instance.ca1 if score_instance else None,
                        'ca2': score_instance.ca2 if score_instance else None,
                        'ca3': score_instance.ca3 if score_instance else None,
                        'exam_score': score_instance.exam_score if score_instance else None,
                    })

                # --- CORRECTED LINE: Ensure extra=0 is used when initializing with initial data ---
                ScoreFormSet = formset_factory(ScoreEntryForm, extra=0)
                formset = ScoreFormSet(initial=initial_data) # Size is determined by len(initial_data)

        # ... (context population remains the same)
        try:
            school_identity = SchoolIdentity.objects.first()
        except SchoolIdentity.DoesNotExist:
            school_identity = None

        context = {
            'current_term': current_term,
            'assigned_subjects': assigned_subjects,
            'assigned_standards': assigned_standards,
            'selected_subject_id': int(selected_subject_id) if selected_subject_id else None,
            'selected_standard_id': int(selected_standard_id) if selected_standard_id else None,
            'selected_subject': selected_subject,
            'selected_standard': selected_standard,
            'formset': formset,
            'students_in_standard': students_in_standard,
            'school_identity': school_identity,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        teacher = request.user.teacher

        current_term = Term.objects.filter(is_current=True).first()
        if not current_term:
            messages.error(request, 'No current term set. Please contact administration.')
            return render(request, self.template_name, {})

        selected_subject_id = request.POST.get('selected_subject_id')
        selected_standard_id = request.POST.get('selected_standard_id')

        if not selected_subject_id or not selected_standard_id:
            messages.error(request, 'Subject or standard not selected. Please try again.')
            return redirect('score_entry')

        try:
            selected_subject = Subject.objects.get(id=selected_subject_id)
            selected_standard = Standard.objects.get(id=selected_standard_id)
        except (Subject.DoesNotExist, Standard.DoesNotExist):
            messages.error(request, 'Invalid subject or standard selected.')
            return redirect('score_entry')

        if not teacher.subjects_taught.filter(id=selected_subject.id).exists() or \
           not teacher.standards_assigned.filter(id=selected_standard.id).exists():
            messages.error(request, 'You are not authorized to enter scores for this subject or standard.')
            return redirect('score_entry')

        students_in_standard = Student.objects.filter(current_class=selected_standard).order_by('first_name', 'last_name')

        # --- CORRECTED LINE: When handling POST data, Django expects the formset to match the number of forms submitted.
        # Since we set extra=0 and submit one form per student, we use len(students_in_standard) for total forms.
        # It's safest to define the formset size based on the submitted management data, but setting extra=0 here
        # is necessary to avoid adding *more* rows if the validation fails and we re-render.
        ScoreFormSet = formset_factory(ScoreEntryForm, extra=0)

        formset = ScoreFormSet(request.POST)

        if formset.is_valid():
            try:
                with transaction.atomic():
                    for form in formset:
                        # Since you're not using modelformset_factory, you must ensure the form is not empty here
                        if form.cleaned_data.get('student_id') is None:
                            continue # Skip empty/deleted forms, though this shouldn't happen with extra=0

                        student_id = form.cleaned_data['student_id']
                        score_id = form.cleaned_data['score_id']
                        ca1 = form.cleaned_data.get('ca1')
                        ca2 = form.cleaned_data.get('ca2')
                        ca3 = form.cleaned_data.get('ca3')
                        exam_score = form.cleaned_data.get('exam_score')
                        student = get_object_or_404(Student, id=student_id)

                        has_score_entry = any(s is not None for s in [ca1, ca2, ca3, exam_score])

                        if has_score_entry:
                            if score_id:
                                score_instance = get_object_or_404(Score, id=score_id)
                                score_instance.ca1 = ca1
                                score_instance.ca2 = ca2
                                score_instance.ca3 = ca3
                                score_instance.exam_score = exam_score
                                score_instance.save()
                            else:
                                Score.objects.create(
                                    student=student,
                                    subject=selected_subject,
                                    term=current_term,
                                    ca1=ca1,
                                    ca2=ca2,
                                    ca3=ca3,
                                    exam_score=exam_score
                                )
                        elif score_id:
                            # Trigger the model's deletion logic by saving all None scores to the existing instance
                            score_instance = get_object_or_404(Score, id=score_id)
                            score_instance.ca1, score_instance.ca2, score_instance.ca3, score_instance.exam_score = None, None, None, None
                            score_instance.save()

                messages.success(request, 'Scores saved successfully!')
                return redirect('results:score_entry_success')
            except ValidationError as e:
                for field, error_list in e.message_dict.items():
                    for error_msg in error_list:
                        messages.error(request, f"Validation Error: {error_msg}")
                pass # Fall through to rendering block

        # This block now serves as the single point for re-rendering the page on any error
        messages.error(request, 'Please correct the errors below.')
        assigned_subjects = teacher.subjects_taught.all()
        assigned_standards = teacher.standards_assigned.all()

        try:
            school_identity = SchoolIdentity.objects.first()
        except SchoolIdentity.DoesNotExist:
            school_identity = None

        context = {
            'current_term': current_term,
            'assigned_subjects': assigned_subjects,
            'assigned_standards': assigned_standards,
            'selected_subject_id': int(selected_subject_id) if selected_subject_id else None,
            'selected_standard_id': int(selected_standard_id) if selected_standard_id else None,
            'selected_subject': selected_subject,
            'selected_standard': selected_standard,
            'formset': formset,
            'students_in_standard': students_in_standard,
            'school_identity': school_identity,
        }
        return render(request, self.template_name, context)


# Simple success view
class ScoreEntrySuccessView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return render(request, 'results/score_entry_success.html')




# Currently working Logics
class ReportCardListView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """
    Allows teachers/admins to select a term and standard,
    then view a list of students to generate their report cards.
    """
    template_name = 'results/termly_report_card_list.html'

    def get(self, request, *args, **kwargs):
        form = ReportCardFilterForm(request.GET) # Bind GET data to form for initial selection
        students = []
        selected_term = None
        selected_standard = None

        if form.is_valid():
            selected_term = form.cleaned_data['term']
            selected_standard = form.cleaned_data['standard']

            if selected_term: # Term is always required by the form
                if selected_standard:
                    # Filter students by both term and standard
                    students = Student.objects.filter(
                        current_class=selected_standard
                    ).order_by('last_name', 'first_name')
                else:
                    # If only term is selected, show all students who have scores for that term
                    # This avoids showing students who might not have taken any subjects in that term
                    students = Student.objects.filter(
                        scores__term=selected_term
                    ).distinct().order_by('last_name', 'first_name')
                    messages.info(request, f"Displaying all students with scores for {selected_term.name}. Select a Standard to filter further.")
            else:
                messages.warning(request, "Please select a term to view students.")

        # If no form data (first load), try to pre-select current term
        else:
            current_term = Term.objects.filter(is_current=True).first()
            if current_term:
                form = ReportCardFilterForm(initial={'term': current_term})
                messages.info(request, f"Showing students for the current term: {current_term.name}. Select a standard or another term.")
                # Show all students in current term (might be too many, but good starting point)
                students = Student.objects.filter(scores__term=current_term).distinct().order_by('last_name', 'first_name')
                selected_term = current_term # Set for template display


        context = {
            'form': form,
            'students': students,
            'selected_term': selected_term,
            'selected_standard': selected_standard,
        }
        return render(request, self.template_name, context)


#New Report Card View to capture the attendance
# Placeholder functions from the original code
def get_grade(score):
    if score >= 80:
        return "A"
    elif score >= 71:
        return "B+"
    elif score >= 60:
        return "B"
    elif score >= 50:
        return "C"
    elif score >= 45:
        return "D"
    elif score >= 40:
        return "E"
    else:
        return "F"

def get_subject_remark(score):
    if score >= 80:
        return "Excellent"
    elif score >= 71:
        return "Very Good"
    elif score >= 60:
        return "Good"
    elif score >= 50:
        return "Fair"
    elif score >= 40:
        return "Pass"
    else:
        return "Fail"

def get_overall_remark(average):
    if average >= 80:
        return "Outstanding"
    elif average >= 71:
        return "Very Good"
    elif average >= 60:
        return "Good"
    elif average >= 50:
        return "Fair"
    elif average >= 40:
        return "Poor"
    else:
        return "Very Poor"



class StudentReportCardView(LoginRequiredMixin, View):
    """
    Generates and displays a single student's report card for a specific term.
    Accessible by teachers/admins (for any student) and by the student themselves.
    """
    template_name = 'results/test_student_report_card_detail.html'
    pdf_template_name = 'results/test_student_report_card_pdf.html' # Dedicated template for PDF layout

    def get(self, request, student_id, term_id, *args, **kwargs):
        # Assumes Student, Term, etc. models are imported
        student = get_object_or_404(Student, id=student_id)
        term = get_object_or_404(Term, id=term_id)
        standard = student.current_class # Get the standard for ranking

        # Authorization Check (No change)
        if not hasattr(request.user, 'teacher'):
            if not (hasattr(request.user, 'student') and request.user.student == student):
                messages.error(request, "You are not authorized to view this report card.")
                return redirect('student_dashboard' if hasattr(request.user, 'student') else 'home')

        # --- ATTENDANCE and NEXT TERM ---
        student_attendance = Attendance.objects.filter(student=student, date__gte=term.start_date, date__lte=term.end_date)

        days_present = student_attendance.filter(present=True).count()
        days_absent = student_attendance.filter(present=False).count()

        total_school_days = Attendance.objects.filter(
            student__current_class=student.current_class,
            date__gte=term.start_date,
            date__lte=term.end_date
        ).values('date').distinct().count()

        next_term = Term.objects.filter(start_date__gt=term.end_date).order_by('start_date').first()
        next_term_start_date = next_term.start_date if next_term else None

        total_students_in_class = Student.objects.filter(current_class=student.current_class).count()

        # Fetch scores for the student in the selected term
        scores = Score.objects.filter(student=student, term=term).select_related('subject').order_by('subject__name')

        report_data = []
        total_scores_sum = 0
        subjects_with_scores_count = 0

        for score in scores:
            current_total_score = score.total_score

            if current_total_score is not None:
                # Assumes utility functions like get_grade, get_subject_remark are defined/imported
                total_ca = (score.ca1 or 0) + (score.ca2 or 0) + (score.ca3 or 0)

                report_data.append({
                    'subject': score.subject.name,
                    'ca1': score.ca1 if score.ca1 is not None else 'N/A',
                    'ca2': score.ca2 if score.ca2 is not None else 'N/A',
                    'ca3': score.ca3 if score.ca3 is not None else 'N/A',
                    'total_ca': total_ca,
                    'exam_score': score.exam_score if score.exam_score is not None else 'N/A',
                    'total_score': current_total_score,
                    'grade': get_grade(current_total_score),
                    'remark': get_subject_remark(current_total_score),
                })

                total_scores_sum += current_total_score
                subjects_with_scores_count += 1

        # --- Calculate Overall Average ---
        overall_average = None
        overall_remark = "No scores recorded for this term."
        if subjects_with_scores_count > 0:
            overall_average = total_scores_sum / subjects_with_scores_count
            overall_remark = get_overall_remark(overall_average)

        # --- RANKING LOGIC INTEGRATION ---
        student_rank, total_students = get_student_class_rank(student, standard, term)

        student_position_display = 'N/A (Unranked)'
        if student_rank != 'N/A' and subjects_with_scores_count > 0:
            student_position_display = f"{student_rank} out of {total_students}"
        # --------------------------------

        motor_ability_score = MotorAbilityScore.objects.filter(student=student, term=term).first()

        try:
            school_identity = SchoolIdentity.objects.first()
        except SchoolIdentity.DoesNotExist:
            school_identity = None

        context = {
            'student': student,
            'term': term,
            'report_data': report_data,
            'overall_average': overall_average,
            'overall_remark': overall_remark,
            'student_position_display': student_position_display,
            'motor_ability_score': motor_ability_score,
            'school_identity': school_identity,
            'total_school_days': total_school_days,
            'days_present': days_present,
            'days_absent': days_absent,
            'next_term_start_date': next_term_start_date,
            'total_students_in_class': total_students_in_class,
        }

        # --- PDF GENERATION LOGIC ---
        if 'download' in request.GET and request.GET['download'] == 'pdf':
            # Assumes render_to_pdf_xhtml2pdf function and HttpResponse are imported
            filename = f"{student.first_name.replace(' ', '_')}_{term.name.replace(' ', '_')}_TermlyReportCard.pdf"
            pdf_response = render_to_pdf_xhtml2pdf(self.pdf_template_name, context)

            if pdf_response:
                # Set the response content type and disposition for download
                pdf_response['Content-Disposition'] = f'attachment; filename="{filename}"'
                pdf_response['Content-Type'] = 'application/pdf' # Ensure correct content type for download
                return pdf_response
            else:
                return HttpResponse("Error generating PDF.", status=500)
        # ----------------------------

        return render(request, self.template_name, context)




# Helper function for rendering PDF (optional, but good practice)
def render_to_pdf_xhtml2pdf(template_src, context_dict={}):
    template = get_template(template_src)
    html = template.render(context_dict)
    result = io.BytesIO()

    # Create the PDF
    pdf = pisa.CreatePDF(
        io.StringIO(html), # Use StringIO for HTML content
        dest=result # File-like object to write PDF to
    )

    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')

    # If there's an error during PDF creation
    return HttpResponse("We had some errors <pre>%s</pre>" % html, status=500)


# Old Session Report Card View without attendance
class SessionReportCardListView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """
    Allows teachers/admins to select a session and standard,
    then view a list of students to generate their annual report cards.
    """
    template_name = 'results/test_session_report_card_list.html'

    def get(self, request, *args, **kwargs):
        form = SessionReportCardFilterForm(request.GET)
        students = []
        selected_session = None
        selected_standard = None

        if form.is_valid():
            selected_session = form.cleaned_data['session']
            selected_standard = form.cleaned_data['standard']

            if selected_session:
                # Filter students who have any scores in the selected session
                student_filter = Q(scores__term__session=selected_session)
                if selected_standard:
                    student_filter &= Q(current_class=selected_standard)

                students = Student.objects.filter(student_filter).distinct().order_by('last_name', 'first_name')

                if not students and (selected_standard or selected_session):
                     messages.info(request, f"No students with recorded scores found for {selected_session.name}" + (f" in {selected_standard.name}" if selected_standard else "."))
            else:
                messages.warning(request, "Please select an academic session to view students.")
        else: # On initial load, try to pre-select current session
            current_session = Session.objects.filter(is_current=True).first()
            if current_session:
                form = SessionReportCardFilterForm(initial={'session': current_session.id})
                students = Student.objects.filter(scores__term__session=current_session).distinct().order_by('last_name', 'first_name')
                selected_session = current_session
                if students:
                    messages.info(request, f"Showing students with scores for the current session: {current_session.name}.")
                else:
                    messages.info(request, f"No students with scores found for the current session: {current_session.name}.")


        context = {
            'form': form,
            'students': students,
            'selected_session': selected_session,
            'selected_standard': selected_standard,
        }
        return render(request, self.template_name, context)



# NEW SESSION REPORT CARD VIEW THAT CAPTURES ATTENDANCE
class StudentSessionReportCardView(LoginRequiredMixin, View):
    """
    Generates and displays a single student's cumulative report card for a specific academic session.
    Accessible by teachers/admins (for any student) and by the student themselves.
    """
    template_name = 'results/session_report_card_detail.html'
    pdf_template_name = 'results/session_report_card_pdf.html' # Dedicated PDF template (recommended)

    def get(self, request, student_id, session_id, *args, **kwargs):
        student = get_object_or_404(Student, id=student_id)
        session = get_object_or_404(Session, id=session_id)

        # Authorization Check: Teachers/Admins can view any, student can view their own.
        if not hasattr(request.user, 'teacher'): # If not a teacher
            if not (hasattr(request.user, 'student') and request.user.student == student):
                messages.error(request, "You are not authorized to view this report card.")
                return redirect('student_dashboard' if hasattr(request.user, 'student') else 'home')

        # Get all terms within this session, ordered chronologically for consistent display
        terms_in_session = session.terms.all().order_by('start_date')
        if not terms_in_session.exists():
            messages.warning(request, f"No terms defined for {session.name}. Cannot generate report card.")
            return redirect(request.META.get('HTTP_REFERER', 'session_report_card_list')) # Go back or to list

        # Aggregate scores for each subject across all terms in the session
        # This groups scores by subject and sums their total_score for the student within the session's terms.
        subject_cumulative_data = Score.objects.filter(
            student=student,
            term__in=terms_in_session # Filter by terms belonging to this session
        ).values('subject__name', 'subject__id').annotate(
            cumulative_total_score=Sum('total_score')
        ).order_by('subject__name')

        report_data = []
        overall_effective_average_sum = 0
        subjects_counted_for_overall_average = 0

        # Determine maximum possible cumulative score per subject for all terms in the session
        # Assuming each term's total_score is out of 100 (adjust if your max score per term differs)
        max_possible_score_per_term = 100 # Change this if your total_score for a single term is not out of 100
        max_possible_cumulative_score_per_subject = max_possible_score_per_term * terms_in_session.count()

        for item in subject_cumulative_data:
            subject_name = item['subject__name']
            cumulative_score_raw = item['cumulative_total_score']

            # Get individual term scores for this subject for display in the table
            term_scores_for_subject = {}
            for term in terms_in_session:
                try:
                    score_instance = Score.objects.get(student=student, subject__id=item['subject__id'], term=term)
                    # Display total_score, or 'N/A' if score is None for that term
                    term_scores_for_subject[term.name] = score_instance.total_score if score_instance.total_score is not None else 'N/A'
                except Score.DoesNotExist:
                    term_scores_for_subject[term.name] = 'N/A' # Mark as N/A if no score exists for that term/subject

            effective_subject_average = None
            if cumulative_score_raw is not None and max_possible_cumulative_score_per_subject > 0:
                # Calculate the effective average out of 100
                effective_subject_average = (cumulative_score_raw / max_possible_cumulative_score_per_subject) * 100

                # Only include subjects with a valid average in the overall average calculation
                overall_effective_average_sum += effective_subject_average
                subjects_counted_for_overall_average += 1

            report_data.append({
                'subject': subject_name,
                'term_scores': term_scores_for_subject, # Dictionary of {TermName: Score}
                'cumulative_total_score': f"{cumulative_score_raw:.2f}" if cumulative_score_raw is not None else 'N/A',
                'effective_subject_average': f"{effective_subject_average:.2f}" if effective_subject_average is not None else 'N/A',
                'grade': get_grade(effective_subject_average),
                'remark': get_subject_remark(effective_subject_average),
            })

        overall_session_average = None
        overall_remark = "No scores recorded for this session."

        if subjects_counted_for_overall_average > 0:
            overall_session_average = overall_effective_average_sum / subjects_counted_for_overall_average
            overall_remark = get_overall_remark(overall_session_average)

        # --- Aggregating Motor Ability Scores across all terms in the session ---
        # Get all MotorAbilityScore instances for this student within this session
        motor_ability_scores_for_session = MotorAbilityScore.objects.filter(
            student=student,
            term__session=session # Filter by terms belonging to this specific session
        )

        # Calculate the average score for each motor ability category across all relevant terms
        aggregated_motor_abilities = motor_ability_scores_for_session.aggregate(
            avg_honesty=Avg('honesty'),
            avg_politeness=Avg('politeness'),
            avg_neatness=Avg('neatness'),
            avg_cooperation=Avg('cooperation'),
            avg_obedience=Avg('obedience'),
            avg_attentiveness=Avg('attentiveness'),
            avg_punctuality=Avg('punctuality'),
            avg_perseverance=Avg('perseverance'),
            avg_emotional_stability=Avg('emotional_stability'),
            avg_attitude=Avg('attitude'),
            avg_leadership=Avg('leadership'),
            avg_physical_education=Avg('physical_education'),
            avg_games=Avg('games'),
            avg_musical=Avg('musical'),
            avg_handwriting=Avg('handwriting'),
            avg_reading=Avg('reading'),
            avg_verbal_fluency=Avg('verbal_fluency'),
            avg_handling_tools=Avg('handling_tools'),
        )

        # Process aggregated values: round to nearest integer and cap at 5
        # Also ensure values are 0 if no scores were present (Avg returns None for no data)
        processed_aggregated_motor_abilities = {}
        for key, value in aggregated_motor_abilities.items():
            if value is not None:
                # Round the average and cap it at the max score (5)
                processed_aggregated_motor_abilities[key] = round(min(value, 5))
            else:
                processed_aggregated_motor_abilities[key] = 0 # Default to 0 if no scores for that trait

        # ADDITION START
        # --- Attendance Report Logic ---
        # Assumes a model named `Attendance` exists with fields `student` and `date_present` (boolean) or similar.
        # This is a sample implementation. Adjust model and field names as needed.
        from django.db.models import Count
        from datetime import date

        # Get all attendance records for the student within the session's date range
        attendance_records = Attendance.objects.filter(
            student=student,
            date__gte=session.start_date,
            date__lte=session.end_date
        )

        # Calculate total school days, days present, and days absent
        # Assuming each attendance record represents a school day
        total_school_days = attendance_records.aggregate(total=Count('id'))['total'] or 0
        # days_present = attendance_records.filter(status='present').aggregate(count=Count('id'))['count'] or 0
        days_absent = attendance_records.filter(present=False).aggregate(count=Count('id'))['count'] or 0
        days_present = attendance_records.filter(present=True).aggregate(count=Count('id'))['count'] or 0
        # --- Next Session Logic ---
        # Find the next session chronologically
        next_session = Session.objects.filter(start_date__gt=session.end_date).order_by('start_date').first()
        next_session_start_date = next_session.start_date if next_session else None

        # --- Fetch School Identity ---
        try:
            school_identity = SchoolIdentity.objects.first()
        except SchoolIdentity.DoesNotExist:
            school_identity = None
        # ADDITION END

        context = {
            'student': student,
            'session': session,
            'terms_in_session': terms_in_session, # Pass terms for dynamic table headers
            'report_data': report_data,
            'overall_session_average': f"{overall_session_average:.2f}" if overall_session_average is not None else 'N/A',
            'overall_remark': overall_remark,
            'aggregated_motor_abilities': processed_aggregated_motor_abilities, # Pass the processed aggregated data
            'school_identity': school_identity,
            'total_school_days': total_school_days,
            'days_present': days_present,
            'days_absent': days_absent,
            'next_session_start_date': next_session_start_date
        }

        # PDF Download Logic using xhtml2pdf
        if 'download' in request.GET and request.GET['download'] == 'pdf':
            filename = f"{student.first_name.replace(' ', '_')}_{session.name.replace(' ', '_')}_AnnualReportCard.pdf"

            # Use the dedicated PDF template here
            pdf_response = render_to_pdf_xhtml2pdf(self.pdf_template_name, context)

            if pdf_response:
                pdf_response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return pdf_response
            else:
                return HttpResponse("Error generating PDF.", status=500)

        # If not download=pdf, render the regular HTML page
        return render(request, self.template_name, context)





# ... (your existing imports) ...

class StudentDashboardView(LoginRequiredMixin, View):
    template_name = 'results/student_dashboard.html'

    def get(self, request, *args, **kwargs):
        if hasattr(request.user, 'student'):
            student = request.user.student

            # Get terms for which the student has scores (for termly reports)
            terms_with_scores = Term.objects.filter(score__student=student).distinct().order_by('-start_date')

            # --- ADD THESE DEBUG PRINTS ---
            print(f"\n--- Debugging StudentDashboard for Student ID: {student.id} ---")
            if not terms_with_scores.exists():
                print("No terms with scores found for this student.")
            else:
                print("Terms found with scores:")
                for term_obj in terms_with_scores:
                    print(f"  Term ID: {term_obj.id}, Name: '{term_obj.name}'")
                    if term_obj.id is None or term_obj.id == '':
                        print(f"  !!! WARNING: Term ID is None or empty for Term: {term_obj.name} !!!")
            print("---------------------------------------------------\n")
            # --- END DEBUG PRINTS ---

            # Get sessions for which the student has scores (for annual reports)
            sessions_with_filter = Q(terms__score__student=student)
            sessions_with_scores = Session.objects.filter(sessions_with_filter).distinct().order_by('-start_date')

            context = {
                'student': student,
                'terms': terms_with_scores,
                'sessions': sessions_with_scores,
            }
            return render(request, self.template_name, context)
        else:
            messages.error(request, "Your user account is not linked to a student profile. Please contact administration.")
            return redirect('home')


# The new view with form_teacher ability to enter motor ability record
# In your results/views.py

class MotorAbilityScoreCreateUpdateView(LoginRequiredMixin, TeacherRequiredMixin, View):
    template_name = 'results/test_motor_ability_score_form.html'

    def dispatch(self, request, *args, **kwargs):
        student = get_object_or_404(Student, id=kwargs['student_id'])

        # Check if the logged-in user's teacher profile is the student's form_teacher.
        # It's important to check if form_teacher exists to prevent errors.
        if student.form_teacher and student.form_teacher == request.user.teacher:
            # Permission granted, proceed to the view's get or post method
            return super().dispatch(request, *args, **kwargs)

        # If the user is not the form teacher, show an error message and redirect.
        messages.error(request, "You do not have permission to record scores for this student.")
        return redirect('pages:portal-home')

    def get(self, request, student_id, term_id):
        # ... (Your existing get method code goes here)
        # It will only be reached if the dispatch method allows it.
        student = get_object_or_404(Student, id=student_id)
        term = get_object_or_404(Term, id=term_id)

        motor_ability_score = MotorAbilityScore.objects.filter(
            student=student,
            term=term
        ).first()

        if motor_ability_score:
            form = MotorAbilityScoreForm(instance=motor_ability_score)
        else:
            form = MotorAbilityScoreForm()

        context = {
            'student': student,
            'term': term,
            'form': form,
            'is_update': motor_ability_score is not None
        }
        return render(request, self.template_name, context)

    def post(self, request, student_id, term_id):
        # ... (Your existing post method code goes here)
        # It will only be reached if the dispatch method allows it.
        student = get_object_or_404(Student, id=student_id)
        term = get_object_or_404(Term, id=term_id)

        motor_ability_score = MotorAbilityScore.objects.filter(
            student=student,
            term=term
        ).first()

        if motor_ability_score:
            form = MotorAbilityScoreForm(request.POST, instance=motor_ability_score)
        else:
            form = MotorAbilityScoreForm(request.POST)

        if form.is_valid():
            new_score = form.save(commit=False)
            new_score.student = student
            new_score.term = term
            new_score.save()
            messages.success(request, f"Motor Ability scores for {student.first_name} ({term.name}) saved successfully!")
            return redirect(reverse('results:student_report_card_detail', args=[student.id, term.id]))
        else:
            messages.error(request, "Please correct the errors in the form.")
            context = {
                'student': student,
                'term': term,
                'form': form,
                'is_update': motor_ability_score is not None
            }
            return render(request, self.template_name, context)




class ClassRankingView(LoginRequiredMixin, View):
    template_name = 'results/class_ranking.html'

    def get(self, request, standard_id, term_id, *args, **kwargs):
        standard = get_object_or_404(Standard, id=standard_id)
        term = get_object_or_404(Term, id=term_id)

        students_in_class = Student.objects.filter(current_class=standard)

        # --- Overall Ranking Logic ---
        overall_ranking_data = []

        for student in students_in_class:
            scores = Score.objects.filter(student=student, term=term, total_score__isnull=False)

            total_scores_sum = scores.aggregate(total=Sum('total_score'))['total'] or 0
            subjects_with_scores_count = scores.count()

            overall_average = total_scores_sum / subjects_with_scores_count if subjects_with_scores_count > 0 else 0

            overall_ranking_data.append({
                'student': student,
                'overall_average': overall_average,
            })

        # Sort and assign ranks for the overall ranking
        overall_ranking_data.sort(key=lambda x: x['overall_average'], reverse=True)

        current_rank = 0
        last_average = -1
        for i, data in enumerate(overall_ranking_data):
            if data['overall_average'] != last_average:
                current_rank = i + 1
            data['rank'] = current_rank
            last_average = data['overall_average']

        # --- Refactored Subject-Specific Ranking Logic ---
        subject_ranking_data = {}

        # Dynamically get all subjects for which students in this class have scores.
        # This is the key change to avoid the Subject->Standard link.
        all_subjects_in_class = Score.objects.filter(
            student__in=students_in_class,
            term=term,
            total_score__isnull=False
        ).values('subject__name', 'subject_id').distinct().order_by('subject__name')

        for subject_info in all_subjects_in_class:
            subject_scores = []

            for student in students_in_class:
                score = Score.objects.filter(
                    student=student,
                    term=term,
                    subject_id=subject_info['subject_id']
                ).first()

                if score and score.total_score is not None:
                    subject_scores.append({
                        'student': student,
                        'total_score': score.total_score,
                    })

            # Sort and assign ranks for the current subject
            subject_scores.sort(key=lambda x: x['total_score'], reverse=True)

            current_rank_subject = 0
            last_score_subject = -1
            for i, data in enumerate(subject_scores):
                if data['total_score'] != last_score_subject:
                    current_rank_subject = i + 1
                data['rank'] = current_rank_subject
                last_score_subject = data['total_score']

            subject_ranking_data[subject_info['subject__name']] = subject_scores

        context = {
            'standard': standard,
            'term': term,
            'overall_ranking_data': overall_ranking_data,
            'subject_ranking_data': subject_ranking_data,
        }

        return render(request, self.template_name, context)


class StandardsAndTermsListView(LoginRequiredMixin, View):
    """
    Displays a list of all standards and terms, allowing users to select
    a combination to view class rankings.
    """
    template_name = 'results/standards_and_terms_list.html'

    def get(self, request, *args, **kwargs):
        # Fetch all standards and terms
        all_standards = Standard.objects.all().order_by('name')
        all_terms = Term.objects.all().order_by('-start_date')

        context = {
            'all_standards': all_standards,
            'all_terms': all_terms,
        }

        return render(request, self.template_name, context)

# #Parent Access to Students Results
# class ParentReportCardView(LoginRequiredMixin, View):
#     def get(self, request, student_id, term_id, *args, **kwargs):
#         try:
#             parent = Parent.objects.get(user=request.user)
#         except Parent.DoesNotExist:
#             return redirect('pages:portal-home')

#         student = get_object_or_404(Student, id=student_id, parent=parent)
#         term = get_object_or_404(Term, id=term_id)

#         # Fetch all scores for the specific student and term
#         scores = Score.objects.filter(student=student, term=term).select_related('subject')

#         # Fetch motor ability scores for the specific student and term
#         try:
#             motor_ability = MotorAbilityScore.objects.get(student=student, term=term)
#         except MotorAbilityScore.DoesNotExist:
#             motor_ability = None

#         context = {
#             'student': student,
#             'term': term,
#             'scores': scores,
#             'motor_ability': motor_ability,
#             # Add other data you need for the report card template
#         }
#         return render(request, 'results/parent_report_card_template.html', context)

# Parent Dashboard Termly REport Card View

class ParentReportCardView(LoginRequiredMixin, View):
    def get(self, request, student_id, term_id, *args, **kwargs):
        try:
            parent = Parent.objects.get(user=request.user)
        except Parent.DoesNotExist:
            return redirect('pages:portal-home')

        student = get_object_or_404(Student, id=student_id, parent=parent)
        term = get_object_or_404(Term, id=term_id)

        scores = Score.objects.filter(student=student, term=term).select_related('subject')

        motor_ability_fields = {}
        try:
            motor_ability = MotorAbilityScore.objects.get(student=student, term=term)

            for field in MotorAbilityScore._meta.fields:
                if field.name not in ['id', 'student', 'term']:
                    label = field.verbose_name.replace('_', ' ').title()
                    motor_ability_fields[label] = getattr(motor_ability, field.name)

        except MotorAbilityScore.DoesNotExist:
            motor_ability = None

        context = {
            'student': student,
            'term': term,
            'scores': scores,
            'motor_ability': motor_ability,
            'motor_ability_fields': motor_ability_fields,
            # Use the imported function to get the school identity data
            'school_identity': school_identity_processor(request).get('school_identity'),
        }
        return render(request, 'results/parent_report_card_template.html', context)



# Parent view student results
class ParentSessionReportCardView(LoginRequiredMixin, View):
    template_name = 'results/parent_session_report_card.html'

    def get(self, request, student_id, session_id):
        try:
            parent = Parent.objects.get(user=request.user)
            student = get_object_or_404(Student, id=student_id, parent=parent)
        except (Parent.DoesNotExist, Student.DoesNotExist):
            # Unauthorized access attempt
            return render(request, 'unauthorized_access.html', status=403)

        session = get_object_or_404(Session, id=session_id)

        # Get all scores for the student within the specified session
        scores_in_session = Score.objects.filter(
            student=student,
            term__session=session
        ).order_by('subject__name')

        context = {
            'student': student,
            'session': session,
            'scores': scores_in_session,
        }
        return render(request, self.template_name, context)


@login_required
def parent_report_card_detail(request, student_id, term_id):
    student = get_object_or_404(Student, id=student_id)
    term = get_object_or_404(Term, id=term_id)

    # Check for user authorization (parent or staff)
    authorized = False
    if request.user.is_staff:
        authorized = True
    elif hasattr(student, 'parent'):
        try:
            parent = Parent.objects.get(user=request.user)
            if student.parent == parent:
                authorized = True
        except Parent.DoesNotExist:
            pass
    # Add a check for the student themselves
    if hasattr(student, 'user') and request.user == student.user:
        authorized = True

    if not authorized:
        messages.warning(request, "You are not authorized to view this report card.")
        return redirect('students:parent-dashboard')

    scores = Score.objects.filter(student=student, term=term).select_related('subject')

    motor_ability = None
    try:
        motor_ability = MotorAbilityScore.objects.get(student=student, term=term)
    except MotorAbilityScore.DoesNotExist:
        pass

    # Fetch SchoolIdentity
    try:
        school_identity = SchoolIdentity.objects.first()
    except SchoolIdentity.DoesNotExist:
        school_identity = None

    context = {
        'student': student,
        'term': term,
        'scores': scores,
        'motor_ability': motor_ability,
        'school_identity': school_identity, # Add school_identity to the context
    }
    return render(request, 'results/parent_report_card_detail.html', context)

@login_required
def parent_session_report_card_detail(request, student_id, session_id):
    student = get_object_or_404(Student, id=student_id)
    session = get_object_or_404(Session, id=session_id)

    # Authorization logic
    authorized = False
    if request.user.is_staff:
        authorized = True
    elif hasattr(student, 'parent'):
        try:
            parent = Parent.objects.get(user=request.user)
            if student.parent == parent:
                authorized = True
        except Parent.DoesNotExist:
            pass
    if hasattr(student, 'user') and request.user == student.user:
        authorized = True

    if not authorized:
        messages.warning(request, "You are not authorized to view this report card.")
        return redirect('students:parent-dashboard')

    # Get all terms for the given session
    terms_in_session = Term.objects.filter(session=session)

    # Aggregate scores for the student across all terms in the session
    scores = Score.objects.filter(
        student=student,
        term__in=terms_in_session
    ).values(
        'subject__name'
    ).annotate(
        total_score__avg=Avg('total_score')
    ).order_by('subject__name')

    # Simple grading logic (you can customize this)
    for score in scores:
        avg_score = score['total_score__avg']
        if avg_score >= 70:
            score['grade'] = 'A'
            score['remarks'] = 'Excellent'
        elif avg_score >= 60:
            score['grade'] = 'B'
            score['remarks'] = 'Good'
        elif avg_score >= 50:
            score['grade'] = 'C'
            score['remarks'] = 'Fair'
        elif avg_score >= 40:
            score['grade'] = 'D'
            score['remarks'] = 'Pass'
        else:
            score['grade'] = 'F'
            score['remarks'] = 'Fail'

    # Fetch motor ability for the session (simple average or most recent)
    motor_ability = MotorAbilityScore.objects.filter(
        student=student,
        term__in=terms_in_session
    ).aggregate(
        honesty=Avg('honesty'),
        politeness=Avg('politeness'),
        punctuality=Avg('punctuality'),
        attendance=Avg('attendance')
    )

    # Fetch SchoolIdentity
    try:
        school_identity = SchoolIdentity.objects.first()
    except SchoolIdentity.DoesNotExist:
        school_identity = None

    context = {
        'student': student,
        'session': session,
        'scores': scores,
        'motor_ability': motor_ability,
        'school_identity': school_identity,
    }
    return render(request, 'results/parent_session_report_card.html', context)


# Result Publication View
class ResultPermissionGatekeeperView(View):
    """
    Acts as a gatekeeper to StudentReportCardView, checking the Admin-set
    ResultPublication permission for a specific student and term.
    """

    def get(self, request, student_id, term_id, *args, **kwargs):
        # 1. Bypass Check for Admins/Teachers
        # Admins or teachers should always see the result to do their job.
        if hasattr(request.user, 'teacher') or request.user.is_superuser:
            # Pass the request directly to the original view
            return StudentReportCardView.as_view()(request, student_id, term_id, *args, **kwargs)

        # 2. Student Authorization Check
        # Ensure only the actual student (if logged in) can proceed
        is_correct_student = hasattr(request.user, 'student') and request.user.student.id == student_id

        if is_correct_student:
            try:
                # 3. Check Admin Publication Status
                publication_status = ResultPublication.objects.get(
                    student_id=student_id,
                    term_id=term_id
                )

                if publication_status.is_published:
                    # Permission granted by Admin
                    return StudentReportCardView.as_view()(request, student_id, term_id, *args, **kwargs)
                else:
                    # Permission denied by Admin
                    messages.error(request, "Your report card viewing access has been temporarily restricted by the administration.")
                    return redirect('results:student_dashboard') # Redirect to student's safe page

            except ResultPublication.DoesNotExist:
                # If the Admin hasn't explicitly created the record, default to restricted access
                messages.error(request, "Access to this report card is pending administrative review.")
                return redirect('results:student_dashboard')

        # 4. Fallback for unauthorized users
        messages.error(request, "You are not authorized to view this report card.")
        return redirect('pages:portal-home')




# MID-TERM RESULTS VIEW
class MidTermScoreEntryView(LoginRequiredMixin, View):
    """
    Allows the assigned class teacher or Admin to enter/update Mid-Term Scores
    for all students in a specific class and subject for a term.
    """
    template_name = 'results/midterm_score_entry.html'

    def dispatch(self, request, *args, **kwargs):
        # 1. Permission Check: Only Teachers/Admins/Staff can access this
        if not (hasattr(request.user, 'teacher') or request.user.is_staff):
            messages.error(request, "You do not have permission to enter scores.")
            return redirect('pages:portal-home')
        return super().dispatch(request, *args, **kwargs)

    def get_formset_class(self, **kwargs):
        # Ensure MidTermScoreForm is the custom form designed to return None for empty input
        return modelformset_factory(
            MidTermScore,
            form=MidTermScoreForm, # Use the custom form
            extra=0,
            fields=('exam_total_score',)
        )

    def get(self, request, class_id, subject_id, term_id):
        # Object retrieval (Standard, Subject, Term)
        assigned_class = get_object_or_404(Standard, id=class_id)
        subject = get_object_or_404(Subject, id=subject_id)
        term = get_object_or_404(Term, id=term_id)

        # 2. Teacher-specific Authorization Check (Bypassed if user is staff/superuser)
        if hasattr(request.user, 'teacher') and not request.user.is_staff:
            teacher = request.user.teacher

            # Check if the teacher is assigned as Form Teacher to this class
            is_form_teacher = assigned_class in teacher.form_class.all()
            # Check if the teacher teaches this subject
            teaches_subject = subject in teacher.subjects_taught.all()

            if not (is_form_teacher and teaches_subject):
                messages.error(request, f"You are not authorized to enter scores for {subject.name} in {assigned_class.name}.")
                return redirect('results:teacher_dashboard')

        # Get students in the class
        students = Student.objects.filter(current_class=assigned_class).order_by('last_name')

        # --- Placeholder Creation Logic ---
        existing_student_ids = MidTermScore.objects.filter(student__in=students, subject=subject, term=term).values_list('student_id', flat=True)
        for student in students:
            if student.id not in existing_student_ids:
                # CRITICAL: exam_total_score MUST be created as None, not 0, to indicate 'not taken'
                MidTermScore.objects.create(student=student, subject=subject, term=term, exam_total_score=None)

        # Get the scores (including the newly created placeholders)
        queryset = MidTermScore.objects.filter(
            student__in=students,
            subject=subject,
            term=term
        ).select_related('student').order_by('student__last_name')

        MidTermScoreFormSet = self.get_formset_class()
        formset = MidTermScoreFormSet(queryset=queryset)

        context = {
            'formset': formset,
            'assigned_class': assigned_class,
            'subject': subject,
            'term': term,
            'students': students,
        }
        return render(request, self.template_name, context)

    def post(self, request, class_id, subject_id, term_id):
        # Object retrieval (Standard, Subject, Term)
        assigned_class = get_object_or_404(Standard, id=class_id)
        subject = get_object_or_404(Subject, id=subject_id)
        term = get_object_or_404(Term, id=term_id)

        # Re-run authorization check (omitted for brevity, assuming models are accessible)

        students = Student.objects.filter(current_class=assigned_class)
        queryset = MidTermScore.objects.filter(
            student__in=students,
            subject=subject,
            term=term
        ).select_related('student').order_by('student__last_name')

        MidTermScoreFormSet = self.get_formset_class()
        formset = MidTermScoreFormSet(request.POST, queryset=queryset)

        if formset.is_valid():

            instances_to_save = []
            instances_to_delete = []

            for form in formset:
                if form.has_changed():
                    instance = form.save(commit=False)
                    score_value = form.cleaned_data.get('exam_total_score')

                    # --- CRITICAL FIX: Custom save logic to delete blank entries ---
                    if score_value is None:
                        # If the score is cleared (None) and a record exists (instance.pk), mark for deletion.
                        if instance.pk:
                            instances_to_delete.append(instance)
                        # If it's a new instance with a None score, we ignore it (no save needed).
                    else:
                        # Score is 0 or positive, so we save/update it.
                        instances_to_save.append(instance)

            # 1. Save valid, non-empty instances (including those with score 0)
            for instance in instances_to_save:
                instance.save()

            # 2. Delete instances where the score was explicitly cleared (treat as 'not taken')
            for instance in instances_to_delete:
                instance.delete()

            # --- NEW SUCCESS REDIRECT LOGIC ---
            # Redirect to the dedicated success page instead of back to entry page
            return redirect('results:midterm_score_success',
                            class_id=class_id,
                            subject_id=subject_id,
                            term_id=term_id)
            # ----------------------------------

        context = {
            'formset': formset,
            'assigned_class': assigned_class,
            'subject': subject,
            'term': term,
            'students': students.order_by('last_name'),
        }
        messages.error(request, "There was an error in the score entry. Please check the scores entered.")
        return render(request, self.template_name, context)




class MidTermReportCardView(LoginRequiredMixin, View):
    template_name = 'results/mid_term_report_card_detail.html'
    pdf_template_name = 'results/mid_term_report_card_detail.html'

    def get(self, request, student_id, term_id, *args, **kwargs):
        student = get_object_or_404(Student, id=student_id)
        term = get_object_or_404(Term, id=term_id)

        # -----------------------------------------------------------
        # REFACTORED AUTHORIZATION LOGIC
        # -----------------------------------------------------------
        # 1. Superuser/Staff check
        is_admin = request.user.is_superuser or request.user.is_staff

        # 2. Student ownership check
        is_current_student = hasattr(request.user, 'student') and request.user.student.id == student_id

        # 3. Strict Form Teacher check
        # Only the teacher assigned to this specific student can view the report
        is_assigned_form_teacher = False
        if hasattr(request.user, 'teacher'):
            # This checks if the teacher logged in is the one referenced in the student's form_teacher column
            if student.form_teacher == request.user.teacher:
                is_assigned_form_teacher = True

        # Combine checks: If none are met, deny access
        if not (is_admin or is_current_student or is_assigned_form_teacher):
            return redirect('results:student_midterm_list')
        # -----------------------------------------------------------

        # Get student's scores (Existing logic below remains unchanged)
        midterm_scores = MidTermScore.objects.filter(
            student=student,
            term=term,
            exam_total_score__isnull=False
        ).select_related('subject').order_by('subject__name')

        report_data = []
        total_scores_sum = 0

        for score in midterm_scores:
            stats = MidTermScore.objects.filter(
                term=term,
                subject=score.subject,
                student__current_class=student.current_class,
                exam_total_score__isnull=False
            ).aggregate(
                class_max=Max('exam_total_score'),
                class_min=Min('exam_total_score'),
                class_avg=Avg('exam_total_score')
            )

            report_data.append({
                'subject': score.subject.name,
                'total_score': score.exam_total_score,
                'grade': get_grade(score.exam_total_score),
                'remark': get_subject_remark(score.exam_total_score),
                'class_high': stats['class_max'],
                'class_low': stats['class_min'],
                'class_avg': stats['class_avg'],
            })

            total_scores_sum += score.exam_total_score

        subjects_with_scores_count = len(report_data)
        overall_average = total_scores_sum / subjects_with_scores_count if subjects_with_scores_count > 0 else None
        overall_remark = get_overall_remark(overall_average) if overall_average else "No scores recorded."

        try:
            school_identity = SchoolIdentity.objects.first()
        except:
            school_identity = None

        context = {
            'student': student,
            'term': term,
            'report_data': report_data,
            'overall_average': overall_average,
            'overall_remark': overall_remark,
            'school_identity': school_identity,
            'total_subjects_scored': subjects_with_scores_count,
        }

        if 'download' in request.GET and request.GET['download'] == 'pdf':
            filename = f"{student.first_name}_{term.name}_MidTerm.pdf"
            pdf_response = render_to_pdf_xhtml2pdf(self.pdf_template_name, context)
            if pdf_response:
                pdf_response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return pdf_response

        return render(request, self.template_name, context)




# Mid Term List
class StudentMidTermListView(LoginRequiredMixin, View):
    template_name = 'results/student_midterm_list.html'

    def get(self, request):
        is_student = hasattr(request.user, 'student')
        is_teacher = hasattr(request.user, 'teacher')
        is_admin = request.user.is_staff or request.user.is_superuser

        # 1. Authorization Check
        if not (is_student or is_teacher or is_admin):
            messages.error(request, "Access denied.")
            return redirect('pages:portal-home')

        context = {}
        report_data = []

        # 2. Filtering Logic
        if is_student:
            student = request.user.student
            context['current_user_type'] = 'student'
            context['student'] = student

            queryset = Term.objects.filter(
                midtermscore__student=student
            ).values('id', 'name', 'session__name').distinct()

            for report in queryset:
                report_data.append({
                    'term_id': report['id'],
                    'term_name': report['name'],
                    'session_name': report['session__name'],
                    'student_id': student.id,
                })

        # --- COMBINED TEACHER & ADMIN LOGIC ---
        elif is_admin or is_teacher:
            context['current_user_type'] = 'admin' if is_admin else 'teacher'

            # Base Queryset
            scores_qs = MidTermScore.objects.all()

            # If NOT admin (meaning they are a teacher), filter by their class
            if not is_admin:
                try:
                    assigned_class = request.user.teacher.form_class.get()
                except:
                    assigned_class = request.user.teacher.form_class.first()

                if not assigned_class:
                    messages.warning(request, "No assigned class found.")
                    return render(request, self.template_name, {'available_reports': []})

                context['assigned_class'] = assigned_class
                scores_qs = scores_qs.filter(student__current_class=assigned_class)

            # Get Unique Student + Term combinations
            queryset = scores_qs.values(
                'student', 'term', 'term__name', 'term__session__name',
                'student__first_name', 'student__last_name', 'student__current_class__name'
            ).annotate(dummy_id=Max('id')).order_by('-term__session__name', 'student__last_name')

            for report in queryset:
                report_data.append({
                    'term_id': report['term'],
                    'term_name': report['term__name'],
                    'session_name': report['term__session__name'],
                    'student_id': report['student'],
                    'student_name': f"{report['student__first_name']} {report['student__last_name']} ({report['student__current_class__name']})",
                })

        context['available_reports'] = report_data
        return render(request, self.template_name, context)


class MidTermScoreSelectionView(LoginRequiredMixin, View):
    """
    Provides a form for the teacher to select the Subject and Term
    before navigating to the MidTermScoreEntryView, restricted to their
    assigned form class and the current term.
    """
    template_name = 'results/midterm_score_selection.html'

    def get(self, request):
        user = request.user

        # 1. Authorization Check (Must be a Teacher or Staff)
        if not (hasattr(user, 'teacher') or user.is_staff):
            messages.error(request, "Access denied. You must be a teacher or administrator.")
            return redirect('pages:portal-home')

        teacher = user.teacher

        # 2. Get Assigned Class (Using the confirmed reverse relationship)
        try:
            # teacher.form_class.get() fetches the Standard object linked as the form teacher
            assigned_class = teacher.form_class.get()
        except ObjectDoesNotExist:
            assigned_class = None
        except Exception:
            # Fallback for errors like multiple classes assigned (shouldn't happen)
            assigned_class = teacher.form_class.first()

        if not assigned_class:
            messages.warning(request, "You are not assigned as a Form Teacher to any class and cannot enter scores.")
            return redirect('pages:portal-home') # Or another appropriate landing page

        # 3. Get Available Subjects
        # Filters to subjects the teacher is assigned to teach.
        available_subjects = teacher.subjects_taught.all().order_by('name')

        # 4. FIX: Get ONLY the Current Term
        try:
            # This is the line that fetches only the current term
            available_terms = [Term.objects.get(is_current=True)]
        except ObjectDoesNotExist:
            messages.error(request, "Error: No current active academic term is configured.")
            available_terms = []

        # Check if any subjects are available to prevent empty dropdowns
        if not available_subjects.exists():
             messages.warning(request, f"You are assigned as the Form Teacher for {assigned_class.name}, but are not assigned to teach any subjects. Cannot enter scores.")
             return redirect('pages:portal-home')


        context = {
            'assigned_class': assigned_class,
            'available_subjects': available_subjects,
            'available_terms': available_terms,
            # Pass school_info context if you have a context processor, otherwise fetch it manually if needed.
        }

        return render(request, self.template_name, context)


class MidTermScoreSuccessView(LoginRequiredMixin, View):
    """
    Displays a success message after scores are entered and provides links to continue.
    """
    template_name = 'results/midterm_success.html'

    def get(self, request, class_id, subject_id, term_id):
        # Retrieve necessary objects for display/link context
        assigned_class = get_object_or_404(Standard, id=class_id)
        subject = get_object_or_404(Subject, id=subject_id)
        term = get_object_or_404(Term, id=term_id)

        context = {
            'assigned_class': assigned_class,
            'subject': subject,
            'term': term,
            # URL parameters for returning to the entry page
            'class_id': class_id,
            'subject_id': subject_id,
            'term_id': term_id,
        }
        return render(request, self.template_name, context)


# RESULT PUBLICATION VIEW

def staff_only(user):
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(staff_only)
@transaction.atomic # Ensure data consistency during creation
def result_publications_list(request):
    query = request.GET.get('q', '')
    class_id = request.GET.get('class', '')
    term_id = request.GET.get('term', '')

    publications = ResultPublication.objects.none() # Start with an empty queryset

    if class_id and term_id:
        # --- 1. Identify Target Students ---
        target_students = Student.objects.filter(current_class_id=class_id, student_status='active')

        # --- 2. Generate Missing Records (Admin-style) ---
        existing_pubs = ResultPublication.objects.filter(
            term_id=term_id,
            student__current_class_id=class_id
        ).values_list('student_id', flat=True)

        students_to_create = target_students.exclude(id__in=existing_pubs)

        new_pubs = []
        for student in students_to_create:
            new_pubs.append(ResultPublication(student=student, term_id=term_id, is_published=False))

        if new_pubs:
            ResultPublication.objects.bulk_create(new_pubs)


        # --- 3. Fetch Publications (Performance Optimized) ---
        # CRITICAL FIX A: Use select_related to load Student's Class and the Term (and Session) in ONE query.
        publications = ResultPublication.objects.filter(
            term_id=term_id,
            student__current_class_id=class_id
        ).select_related('student__current_class', 'term', 'term__session') # ADDED 'term__session'

        # --- Search Filter ---
        if query:
            publications = publications.filter(
                Q(student__first_name__icontains=query) |
                Q(student__last_name__icontains=query) |
                Q(student__USN__icontains=query)
            )

    # Ordering and Pagination
    publications = publications.order_by('student__current_class__name', 'student__last_name')
    paginator = Paginator(publications, 25)
    page = request.GET.get('page')
    publications = paginator.get_page(page)

    # CRITICAL FIX B: Ensure the 'terms' context variable is optimized with select_related
    all_terms_optimized = Term.objects.select_related('session').all() # ADDED select_related('session')

    context = {
        'publications': publications,
        'classes': Standard.objects.all(),
        'terms': all_terms_optimized, # Use the optimized queryset
        'search_query': query,
        'selected_class': class_id,
        'selected_term': term_id,
        'data_loaded': bool(class_id and term_id)
    }
    return render(request, 'results/result_publication_list.html', context)


# The rest of your views (toggle_publication_status and bulk_update_publications) remain unchanged
# as they do not need the session or class data to function.

@login_required
@user_passes_test(staff_only)
def toggle_publication_status(request, pk):
    publication = get_object_or_404(ResultPublication, pk=pk)
    publication.is_published = not publication.is_published
    publication.save()
    return JsonResponse({'success': True, 'status': publication.is_published})


@login_required
@user_passes_test(staff_only)
def bulk_update_publications(request):
    action = request.POST.get('action')
    class_id = request.POST.get('class_id')
    term_id = request.POST.get('term_id')
    student_id = request.POST.get('student_id')

    queryset = ResultPublication.objects.all()

    if class_id:
        queryset = queryset.filter(student__current_class_id=class_id)
    if term_id:
        queryset = queryset.filter(term_id=term_id)
    if student_id:
        queryset = queryset.filter(student_id=student_id)

    if action == 'publish':
        updated_count = queryset.update(is_published=True)
    elif action == 'unpublish':
        updated_count = queryset.update(is_published=False)

    return JsonResponse({'success': True, 'count': updated_count})