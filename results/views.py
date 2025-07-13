from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse # Import HttpResponse
from django.db.models import Sum, Avg, F # F object for database expressions
from .models import Student, Result, Examination # Adjust import path as needed
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Avg, Q # Import Q for complex queries if needed
from curriculum.models import Session, Term, Standard, Subject
from staff.models import Teacher
from students.models import Student
from django.contrib import messages # Import messages


from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.db import transaction
from django.forms import formset_factory
from .models import Score
from .forms import ScoreEntryForm # We'll create this form next

from .forms import ScoreEntryForm, ReportCardFilterForm, SessionReportCardFilterForm # Import new form
from .utils import get_grade, get_subject_remark, get_overall_remark # Import helper functions
from django.template.loader import render_to_string # Import render_to_string

# For PDF generation
# from weasyprint import HTML, CSS # Import HTML and CSS from WeasyPrint

# For PDF generation using django-wkhtmltopdf
# from wkhtmltopdf.views import PDFTemplateResponse # Import this
from django.conf import settings # To access MEDIA_ROOT/STATIC_ROOT if needed for CSS/images

from xhtml2pdf import pisa # ADD THIS IMPORT
import io # Needed for file-like object
from django.template.loader import get_template







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

class ScoreEntryView(LoginRequiredMixin, TeacherRequiredMixin, View):
    template_name = 'results/score_entry.html'

    def get(self, request, *args, **kwargs):
        teacher = request.user.teacher
        
        current_term = Term.objects.filter(is_current=True).first()
        if not current_term:
            messages.error(request, 'No current term set. Please contact administration.')
            return render(request, self.template_name, {})

        assigned_subjects = teacher.subjects_taught.all()
        assigned_standards = teacher.standards_assigned.all() # Changed assigned_classes to assigned_standards

        selected_subject = None
        selected_standard = None

        selected_subject_id = request.GET.get('subject', assigned_subjects.first().id if assigned_subjects.exists() else None)
        selected_standard_id = request.GET.get('standard', assigned_standards.first().id if assigned_standards.exists() else None) # Changed 'class' to 'standard'

        students_in_standard = [] # Changed students_in_class to students_in_standard
        ScoreFormSet = formset_factory(ScoreEntryForm, extra=0)

        if selected_subject_id and selected_standard_id:
            try:
                selected_subject = Subject.objects.get(id=selected_subject_id)
                selected_standard = Standard.objects.get(id=selected_standard_id) # Changed Class.objects.get to Standard.objects.get
            except (Subject.DoesNotExist, Standard.DoesNotExist): # Changed Class.DoesNotExist to Standard.DoesNotExist
                messages.error(request, 'Invalid subject or standard selected.')
                # Keep selected_subject and selected_standard as None to avoid trying to filter students
            
            if selected_subject and selected_standard:
                students_in_standard = Student.objects.filter(current_class=selected_standard).order_by('first_name', 'last_name') # Changed current_class to current_standard
                
                initial_data = []
                for student in students_in_standard:
                    score_instance, created = Score.objects.get_or_create(
                        student=student,
                        subject=selected_subject,
                        term=current_term,
                        defaults={'ca1': None, 'ca2': None, 'ca3': None, 'exam_score': None}
                    )
                    initial_data.append({
                        'student_id': student.id,
                        'student_name': student.first_name,
                        'score_id': score_instance.id,
                        'ca1': score_instance.ca1,
                        'ca2': score_instance.ca2,
                        'ca3': score_instance.ca3,
                        'exam_score': score_instance.exam_score,
                    })
                
                formset = ScoreFormSet(initial=initial_data)
            else:
                formset = ScoreFormSet() # Empty formset if subject/standard not found
        else:
            formset = ScoreFormSet() # Empty formset if no subject/standard selected initially


        context = {
            'current_term': current_term,
            'assigned_subjects': assigned_subjects,
            'assigned_standards': assigned_standards, # Changed assigned_classes to assigned_standards
            'selected_subject_id': int(selected_subject_id) if selected_subject_id else None,
            'selected_standard_id': int(selected_standard_id) if selected_standard_id else None, # Changed selected_class_id to selected_standard_id
            'selected_subject': selected_subject, # New: Pass the object
            'selected_standard': selected_standard, # New: Pass the object
            'formset': formset,
            'students_in_standard': students_in_standard, # Changed students_in_class to students_in_standard
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        teacher = request.user.teacher
        
        current_term = Term.objects.filter(is_current=True).first()
        if not current_term:
            messages.error(request, 'No current term set. Please contact administration.')
            return render(request, self.template_name, {}) # Render rather than redirect to keep POST data if possible

        selected_subject_id = request.POST.get('selected_subject_id')
        selected_standard_id = request.POST.get('selected_standard_id') # Changed selected_class_id to selected_standard_id

        if not selected_subject_id or not selected_standard_id:
            messages.error(request, 'Subject or standard not selected. Please try again.')
            return redirect('score_entry') # Redirect to clear POST data

        try:
            selected_subject = Subject.objects.get(id=selected_subject_id)
            selected_standard = Standard.objects.get(id=selected_standard_id) # Changed Class.objects.get to Standard.objects.get
        except (Subject.DoesNotExist, Standard.DoesNotExist): # Changed Class.DoesNotExist to Standard.DoesNotExist
            messages.error(request, 'Invalid subject or standard selected.')
            return redirect('score_entry') # Redirect if invalid IDs submitted

        if not teacher.subjects_taught.filter(id=selected_subject.id).exists() or \
           not teacher.standards_assigned.filter(id=selected_standard.id).exists(): # Changed classes_assigned to standards_assigned
            messages.error(request, 'You are not authorized to enter scores for this subject or standard.')
            return redirect('score_entry')

        students_in_standard = Student.objects.filter(current_class=selected_standard).order_by('first_name', 'last_name') # Changed current_class to current_standard
        ScoreFormSet = formset_factory(ScoreEntryForm)

        formset = ScoreFormSet(request.POST)

        if formset.is_valid():
            with transaction.atomic():
                for form in formset:
                    student_id = form.cleaned_data['student_id']
                    score_id = form.cleaned_data['score_id']
                    ca1 = form.cleaned_data['ca1']
                    ca2 = form.cleaned_data['ca2']
                    ca3 = form.cleaned_data['ca3']
                    exam_score = form.cleaned_data['exam_score']

                    student = get_object_or_404(Student, id=student_id)

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
            messages.success(request, 'Scores saved successfully!')
            return redirect('results:score_entry_success')
        else:
            messages.error(request, 'Please correct the errors below.')
            assigned_subjects = teacher.subjects_taught.all()
            assigned_standards = teacher.standards_assigned.all() # Changed assigned_classes to assigned_standards
            
            context = {
                'current_term': current_term,
                'assigned_subjects': assigned_subjects,
                'assigned_standards': assigned_standards, # Changed assigned_classes to assigned_standards
                'selected_subject_id': int(selected_subject_id) if selected_subject_id else None,
                'selected_standard_id': int(selected_standard_id) if selected_standard_id else None, # Changed selected_class_id to selected_standard_id
                'selected_subject': selected_subject, # Pass the object back on error
                'selected_standard': selected_standard, # Pass the object back on error
                'formset': formset,
                'students_in_standard': students_in_standard, # Pass for display
            }
            return render(request, self.template_name, context)

# Simple success view
class ScoreEntrySuccessView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return render(request, 'results/score_entry_success.html')



#in progress worked well 002
# schools/views.py


# # Existing TeacherRequiredMixin (no change)
# class TeacherRequiredMixin(UserPassesTestMixin):
#     """Mixin to ensure only users linked to a Teacher profile can access the view."""
#     def test_func(self):
#         return hasattr(self.request.user, 'teacher')

# Existing ScoreEntryView and ScoreEntrySuccessView (no change)
# ... (your existing ScoreEntryView and ScoreEntrySuccessView code here) ...


class ReportCardListView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """
    Allows teachers/admins to select a term and standard,
    then view a list of students to generate their report cards.
    """
    template_name = 'results/report_card_list.html'

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


class StudentReportCardView(LoginRequiredMixin, View):
    """
    Generates and displays a single student's report card for a specific term.
    Accessible by teachers/admins (for any student) and by the student themselves.
    """
    template_name = 'results/report_card_detail.html'

    def get(self, request, student_id, term_id, *args, **kwargs):
        student = get_object_or_404(Student, id=student_id)
        term = get_object_or_404(Term, id=term_id)

        # Authorization Check
        # If the user is NOT a teacher:
        if not hasattr(request.user, 'teacher'):
            # Check if the logged-in user is linked to this specific student
            # And if that student object matches the student_id in the URL
            if not (hasattr(request.user, 'student') and request.user.student == student):
                messages.error(request, "You are not authorized to view this report card.")
                # Redirect to a safer place, e.g., student dashboard or home
                return redirect('student_dashboard' if hasattr(request.user, 'student') else 'home') 
        
        # Fetch scores for the student in the selected term
        scores = Score.objects.filter(student=student, term=term).select_related('subject').order_by('subject__name')

        report_data = []
        total_scores_sum = 0
        subjects_with_scores_count = 0

        for score in scores:
            # The Score model's save method already calculates total_score.
            # We'll use that directly. If total_score is None, default to 0 for calculations.
            current_total_score = score.total_score if score.total_score is not None else 0

            report_data.append({
                'subject': score.subject.name,
                'ca1': score.ca1 if score.ca1 is not None else 'N/A',
                'ca2': score.ca2 if score.ca2 is not None else 'N/A',
                'ca3': score.ca3 if score.ca3 is not None else 'N/A',
                'exam_score': score.exam_score if score.exam_score is not None else 'N/A',
                'total_score': current_total_score, # Use the calculated total
                'grade': get_grade(current_total_score),
                'remark': get_subject_remark(current_total_score),
            })
            
            # Only include subjects with an actual total score in the overall average calculation
            if score.total_score is not None:
                total_scores_sum += current_total_score
                subjects_with_scores_count += 1

        overall_average = None
        overall_remark = "No scores recorded for this term."
        if subjects_with_scores_count > 0:
            overall_average = total_scores_sum / subjects_with_scores_count
            overall_remark = get_overall_remark(overall_average)


        context = {
            'student': student,
            'term': term,
            'report_data': report_data,
            'overall_average': f"{overall_average:.2f}" if overall_average is not None else 'N/A', # Format to 2 decimal places
            'overall_remark': overall_remark,
        }

        # PDF Download Logic using django-wkhtmltopdf
        if 'download' in request.GET and request.GET['download'] == 'pdf':
            filename = f"{student.first_name.replace(' ', '_')}_{term.name.replace(' ', '_')}_ReportCard.pdf"
            # Return PDFTemplateResponse directly
            return PDFTemplateResponse(
                request=request,
                template=self.template_name,
                context=context,
                filename=filename,
                show_content_in_browser=False, # True to display in browser, False to force download
                cmd_options={'enable-local-file-access': None, 'enable-javascript': True, 'no-stop-slow-scripts': True}
                # 'enable-local-file-access' for static files (CSS/Images) if they are referenced by file path
                # 'enable-javascript': If you have JS for rendering (unlikely for reports)
            )
        
        return render(request, self.template_name, context)
       


# class StudentDashboardView(LoginRequiredMixin, View):
#     """
#     A simple dashboard for students to view their own report cards.
#     """
#     template_name = 'results/student_dashboard.html'

#     def get(self, request, *args, **kwargs):
#         # Ensure the logged-in user has a linked Student profile
#         if hasattr(request.user, 'student'):
#             student = request.user.student
            
#             # Get terms for which the student actually has score entries
#             # This prevents showing empty report cards for terms with no data
#             terms_with_scores = Term.objects.filter(score__student=student).distinct().order_by('-start_date')

#             context = {
#                 'student': student,
#                 'terms': terms_with_scores,
#             }
#             return render(request, self.template_name, context)
#         else:
#             messages.error(request, "Your user account is not linked to a student profile. Please contact administration.")
#             # Redirect unlinked users to a different page or show a generic message
#             return redirect('some_general_dashboard_or_home_page') # Define 'some_general_dashboard_or_home_page' in your project's urls.py
        

# xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# schools/views.py

# Assume TeacherRequiredMixin is defined as in your previous setup:
# class TeacherRequiredMixin(UserPassesTestMixin):
#     def test_func(self):
#         return hasattr(self.request.user, 'teacher') # Checks if user has an associated Teacher profile


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



class SessionReportCardListView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """
    Allows teachers/admins to select a session and standard,
    then view a list of students to generate their annual report cards.
    """
    template_name = 'results/session_report_card_list.html'

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

        context = {
            'student': student,
            'session': session,
            'terms_in_session': terms_in_session, # Pass terms for dynamic table headers
            'report_data': report_data,
            'overall_session_average': f"{overall_session_average:.2f}" if overall_session_average is not None else 'N/A',
            'overall_remark': overall_remark,
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
    



# # Modify StudentDashboardView to include session report card links
# class StudentDashboardView(LoginRequiredMixin, View):
#     template_name = 'results/student_dashboard.html'

#     def get(self, request, *args, **kwargs):
#         if hasattr(request.user, 'student'):
#             student = request.user.student
            
#             # Get terms for which the student has scores (for termly reports)
#             terms_with_scores = Term.objects.filter(score__student=student).distinct().order_by('-start_date')

#             # Get sessions for which the student has scores (for annual reports)
#             sessions_with_filter = Q(terms__score__student=student)
            
#             # Optionally, filter for sessions where all expected terms have scores (e.g., 3 terms)
#             # This can be complex if not all students have scores for all subjects in all terms.
#             # For simplicity, we'll just check if student has *any* score in *any* term of a session.
#             sessions_with_scores = Session.objects.filter(sessions_with_filter).distinct().order_by('-start_date')

#             context = {
#                 'student': student,
#                 'terms': terms_with_scores,
#                 'sessions': sessions_with_scores, # Pass sessions to template
#             }
#             return render(request, self.template_name, context)
#         else:
#             messages.error(request, "Your user account is not linked to a student profile. Please contact administration.")
#             return redirect('home') # Redirect to a generic page if not linked
        

# schools/views.py

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