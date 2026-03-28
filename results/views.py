from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse # Import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Sum, Avg, Q, Max, Min, Count # Import Q for complex queries if needed
from curriculum.models import Session, Term, Standard, Subject
from attendance.models import Attendance
from students.models import Student
from students.models import Parent
from django.contrib import messages # Import messages

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views import View
from django.db import transaction
from django.core.exceptions import ValidationError, ObjectDoesNotExist, PermissionDenied
from django.forms import formset_factory, modelformset_factory
from .models import Score, MotorAbilityScore, MidTermScore, ResultPublication, SessionResultStatus, ExamSetting, SchoolYearSettings
from .forms import ScoreEntryForm, ReportCardFilterForm, SessionReportCardFilterForm, MotorAbilityScoreForm, MidTermScoreForm # Import new form
from .utils import get_grade, get_subject_remark, get_overall_remark, mdterm_get_subject_remark, mdterm_get_grade, mdterm_get_overall_remark # Import helper functions
from django.template.loader import render_to_string # Import render_to_string
from curriculum.models import SchoolIdentity
from transport.context_processors import school_identity as school_identity_processor
from django.core.paginator import Paginator
import csv
from django.core.exceptions import PermissionDenied


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




# working well with new view to allow superuser and is_staff
class TeacherRequiredMixin(UserPassesTestMixin):
    """Mixin to allow only users linked to a Teacher profile, or staff/superuser."""
    def test_func(self):
        user = self.request.user
        return hasattr(user, 'teacher') or user.is_staff or user.is_superuser


# class ScoreEntryView(LoginRequiredMixin, TeacherRequiredMixin, View):
#     template_name = 'results/score_entry.html'

#     def get(self, request, *args, **kwargs):
#         # If superuser or staff, they are treated as having access to all classes and subjects
#         if request.user.is_superuser or request.user.is_staff:
#             teacher = None  # No need to filter by teacher
#             assigned_subjects = Subject.objects.all()
#             assigned_standards = Standard.objects.all()
#         else:
#             teacher = request.user.teacher
#             assigned_subjects = teacher.subjects_taught.all()
#             assigned_standards = teacher.standards_assigned.all()

#         current_term = Term.objects.filter(is_current=True).first()
#         if not current_term:
#             messages.error(request, 'No current term set. Please contact administration.')
#             return render(request, self.template_name, {})

#         selected_subject = None
#         selected_standard = None

#         selected_subject_id = request.GET.get('subject', assigned_subjects.first().id if assigned_subjects.exists() else None)
#         selected_standard_id = request.GET.get('standard', assigned_standards.first().id if assigned_standards.exists() else None)

#         students_in_standard = []
#         ScoreFormSet = formset_factory(ScoreEntryForm, extra=0)
#         formset = ScoreFormSet()

#         if selected_subject_id and selected_standard_id:
#             try:
#                 selected_subject = Subject.objects.get(id=selected_subject_id)
#                 selected_standard = Standard.objects.get(id=selected_standard_id)
#             except (Subject.DoesNotExist, Standard.DoesNotExist):
#                 messages.error(request, 'Invalid subject or standard selected.')

#             if selected_subject and selected_standard:
#                 students_in_standard = Student.objects.filter(current_class=selected_standard).order_by('last_name', 'first_name')

#                 initial_data = []
#                 for student in students_in_standard:
#                     score_instance = Score.objects.filter(
#                         student=student,
#                         subject=selected_subject,
#                         term=current_term
#                     ).first()

#                     initial_data.append({
#                         'student_id': student.id,
#                         'student_name': student.get_full_name(),
#                         'score_id': score_instance.id if score_instance else None,
#                         'ca1': score_instance.ca1 if score_instance else None,
#                         'ca2': score_instance.ca2 if score_instance else None,
#                         'ca3': score_instance.ca3 if score_instance else None,
#                         'exam_score': score_instance.exam_score if score_instance else None,
#                     })

#                 ScoreFormSet = formset_factory(ScoreEntryForm, extra=0)
#                 formset = ScoreFormSet(initial=initial_data)

#         try:
#             school_identity = SchoolIdentity.objects.first()
#         except SchoolIdentity.DoesNotExist:
#             school_identity = None

#         context = {
#             'current_term': current_term,
#             'assigned_subjects': assigned_subjects,
#             'assigned_standards': assigned_standards,
#             'selected_subject_id': int(selected_subject_id) if selected_subject_id else None,
#             'selected_standard_id': int(selected_standard_id) if selected_standard_id else None,
#             'selected_subject': selected_subject,
#             'selected_standard': selected_standard,
#             'formset': formset,
#             'students_in_standard': students_in_standard,
#             'school_identity': school_identity,
#         }
#         return render(request, self.template_name, context)

#     def post(self, request, *args, **kwargs):
#         # Same as get: bypass teacher filtering for superuser/staff
#         if request.user.is_superuser or request.user.is_staff:
#             teacher = None
#         else:
#             teacher = request.user.teacher

#         current_term = Term.objects.filter(is_current=True).first()
#         if not current_term:
#             messages.error(request, 'No current term set. Please contact administration.')
#             return render(request, self.template_name, {})

#         selected_subject_id = request.POST.get('selected_subject_id')
#         selected_standard_id = request.POST.get('selected_standard_id')

#         if not selected_subject_id or not selected_standard_id:
#             messages.error(request, 'Subject or standard not selected. Please try again.')
#             return redirect('score_entry')

#         try:
#             selected_subject = Subject.objects.get(id=selected_subject_id)
#             selected_standard = Standard.objects.get(id=selected_standard_id)
#         except (Subject.DoesNotExist, Standard.DoesNotExist):
#             messages.error(request, 'Invalid subject or standard selected.')
#             return redirect('score_entry')

#         # Authorization check only for non-superuser/staff
#         if teacher and (not teacher.subjects_taught.filter(id=selected_subject.id).exists() or
#                         not teacher.standards_assigned.filter(id=selected_standard.id).exists()):
#             messages.error(request, 'You are not authorized to enter scores for this subject or standard.')
#             return redirect('score_entry')

#         students_in_standard = Student.objects.filter(current_class=selected_standard).order_by('last_name', 'first_name')
#         ScoreFormSet = formset_factory(ScoreEntryForm, extra=0)
#         formset = ScoreFormSet(request.POST)

#         if formset.is_valid():
#             try:
#                 with transaction.atomic():
#                     for form in formset:
#                         if form.cleaned_data.get('student_id') is None:
#                             continue

#                         student_id = form.cleaned_data['student_id']
#                         score_id = form.cleaned_data['score_id']
#                         ca1 = form.cleaned_data.get('ca1')
#                         ca2 = form.cleaned_data.get('ca2')
#                         ca3 = form.cleaned_data.get('ca3')
#                         exam_score = form.cleaned_data.get('exam_score')
#                         student = get_object_or_404(Student, id=student_id)

#                         has_score_entry = any(s is not None for s in [ca1, ca2, ca3, exam_score])

#                         if has_score_entry:
#                             if score_id:
#                                 score_instance = get_object_or_404(Score, id=score_id)
#                                 score_instance.ca1 = ca1
#                                 score_instance.ca2 = ca2
#                                 score_instance.ca3 = ca3
#                                 score_instance.exam_score = exam_score
#                                 score_instance.save()
#                             else:
#                                 Score.objects.create(
#                                     student=student,
#                                     subject=selected_subject,
#                                     term=current_term,
#                                     ca1=ca1,
#                                     ca2=ca2,
#                                     ca3=ca3,
#                                     exam_score=exam_score
#                                 )
#                         elif score_id:
#                             score_instance = get_object_or_404(Score, id=score_id)
#                             score_instance.ca1, score_instance.ca2, score_instance.ca3, score_instance.exam_score = None, None, None, None
#                             score_instance.save()

#                 messages.success(request, 'Scores saved successfully!')
#                 return redirect('results:score_entry_success')
#             except ValidationError as e:
#                 for field, error_list in e.message_dict.items():
#                     for error_msg in error_list:
#                         messages.error(request, f"Validation Error: {error_msg}")

#         messages.error(request, 'Please correct the errors below.')
#         assigned_subjects = Subject.objects.all() if (request.user.is_superuser or request.user.is_staff) else teacher.subjects_taught.all()
#         assigned_standards = Standard.objects.all() if (request.user.is_superuser or request.user.is_staff) else teacher.standards_assigned.all()

#         try:
#             school_identity = SchoolIdentity.objects.first()
#         except SchoolIdentity.DoesNotExist:
#             school_identity = None

#         context = {
#             'current_term': current_term,
#             'assigned_subjects': assigned_subjects,
#             'assigned_standards': assigned_standards,
#             'selected_subject_id': int(selected_subject_id) if selected_subject_id else None,
#             'selected_standard_id': int(selected_standard_id) if selected_standard_id else None,
#             'selected_subject': selected_subject,
#             'selected_standard': selected_standard,
#             'formset': formset,
#             'students_in_standard': students_in_standard,
#             'school_identity': school_identity,
#         }
#         return render(request, self.template_name, context)

# New logic for twiking the CA total and Exam Total
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import formset_factory
from django.db import transaction
from django.core.exceptions import ValidationError

# Ensure these models and forms are imported correctly based on your app structure
# from .models import Score, Student, Subject, Standard, Term, SchoolIdentity, SchoolYearSettings
# from .forms import ScoreEntryForm

# class ScoreEntryView(LoginRequiredMixin, TeacherRequiredMixin, View):
#     template_name = 'results/score_entry.html'

#     def get_grading_config(self):
#         """Helper to fetch dynamic totals from settings or use 40/60 defaults."""
#         config = SchoolYearSettings.objects.filter(is_active=True).first()
#         if config:
#             return config.max_ca_total, config.max_exam_score
#         return 40, 60

#     def get(self, request, *args, **kwargs):
#         # Fetch dynamic configuration
#         max_ca, max_exam = self.get_grading_config()

#         # If superuser or staff, they are treated as having access to all classes and subjects
#         if request.user.is_superuser or request.user.is_staff:
#             teacher = None
#             assigned_subjects = Subject.objects.all()
#             assigned_standards = Standard.objects.all()
#         else:
#             teacher = request.user.teacher
#             assigned_subjects = teacher.subjects_taught.all()
#             assigned_standards = teacher.standards_assigned.all()

#         current_term = Term.objects.filter(is_current=True).first()
#         if not current_term:
#             messages.error(request, 'No current term set. Please contact administration.')
#             return render(request, self.template_name, {})

#         selected_subject = None
#         selected_standard = None

#         selected_subject_id = request.GET.get('subject', assigned_subjects.first().id if assigned_subjects.exists() else None)
#         selected_standard_id = request.GET.get('standard', assigned_standards.first().id if assigned_standards.exists() else None)

#         students_in_standard = []
#         ScoreFormSet = formset_factory(ScoreEntryForm, extra=0)
#         formset = ScoreFormSet()

#         if selected_subject_id and selected_standard_id:
#             try:
#                 selected_subject = Subject.objects.get(id=selected_subject_id)
#                 selected_standard = Standard.objects.get(id=selected_standard_id)
#             except (Subject.DoesNotExist, Standard.DoesNotExist):
#                 messages.error(request, 'Invalid subject or standard selected.')

#             if selected_subject and selected_standard:
#                 students_in_standard = Student.objects.filter(current_class=selected_standard).order_by('last_name', 'first_name')

#                 initial_data = []
#                 for student in students_in_standard:
#                     score_instance = Score.objects.filter(
#                         student=student,
#                         subject=selected_subject,
#                         term=current_term
#                     ).first()

#                     initial_data.append({
#                         'student_id': student.id,
#                         'student_name': student.get_full_name(),
#                         'score_id': score_instance.id if score_instance else None,
#                         'ca1': score_instance.ca1 if score_instance else None,
#                         'ca2': score_instance.ca2 if score_instance else None,
#                         'ca3': score_instance.ca3 if score_instance else None,
#                         'exam_score': score_instance.exam_score if score_instance else None,
#                     })

#                 formset = ScoreFormSet(initial=initial_data)

#         try:
#             school_identity = SchoolIdentity.objects.first()
#         except SchoolIdentity.DoesNotExist:
#             school_identity = None

#         context = {
#             'current_term': current_term,
#             'assigned_subjects': assigned_subjects,
#             'assigned_standards': assigned_standards,
#             'selected_subject_id': int(selected_subject_id) if selected_subject_id else None,
#             'selected_standard_id': int(selected_standard_id) if selected_standard_id else None,
#             'selected_subject': selected_subject,
#             'selected_standard': selected_standard,
#             'formset': formset,
#             'students_in_standard': students_in_standard,
#             'school_identity': school_identity,
#             'max_ca': max_ca,
#             'max_exam': max_exam,
#         }
#         return render(request, self.template_name, context)

#     def post(self, request, *args, **kwargs):
#         # Fetch dynamic configuration
#         max_ca, max_exam = self.get_grading_config()

#         if request.user.is_superuser or request.user.is_staff:
#             teacher = None
#         else:
#             teacher = request.user.teacher

#         current_term = Term.objects.filter(is_current=True).first()
#         if not current_term:
#             messages.error(request, 'No current term set. Please contact administration.')
#             return render(request, self.template_name, {})

#         selected_subject_id = request.POST.get('selected_subject_id')
#         selected_standard_id = request.POST.get('selected_standard_id')

#         if not selected_subject_id or not selected_standard_id:
#             messages.error(request, 'Subject or standard not selected. Please try again.')
#             return redirect('score_entry')

#         try:
#             selected_subject = Subject.objects.get(id=selected_subject_id)
#             selected_standard = Standard.objects.get(id=selected_standard_id)
#         except (Subject.DoesNotExist, Standard.DoesNotExist):
#             messages.error(request, 'Invalid subject or standard selected.')
#             return redirect('score_entry')

#         # Authorization check only for non-superuser/staff
#         if teacher and (not teacher.subjects_taught.filter(id=selected_subject.id).exists() or
#                         not teacher.standards_assigned.filter(id=selected_standard.id).exists()):
#             messages.error(request, 'You are not authorized to enter scores for this subject or standard.')
#             return redirect('score_entry')

#         students_in_standard = Student.objects.filter(current_class=selected_standard).order_by('last_name', 'first_name')
#         ScoreFormSet = formset_factory(ScoreEntryForm, extra=0)
#         formset = ScoreFormSet(request.POST)

#         if formset.is_valid():
#             try:
#                 with transaction.atomic():
#                     for form in formset:
#                         if form.cleaned_data.get('student_id') is None:
#                             continue

#                         student_id = form.cleaned_data['student_id']
#                         score_id = form.cleaned_data['score_id']
#                         ca1 = form.cleaned_data.get('ca1')
#                         ca2 = form.cleaned_data.get('ca2')
#                         ca3 = form.cleaned_data.get('ca3')
#                         exam_score = form.cleaned_data.get('exam_score')
#                         student = get_object_or_404(Student, id=student_id)

#                         has_score_entry = any(s is not None for s in [ca1, ca2, ca3, exam_score])

#                         if has_score_entry:
#                             if score_id:
#                                 score_instance = get_object_or_404(Score, id=score_id)
#                                 score_instance.ca1 = ca1
#                                 score_instance.ca2 = ca2
#                                 score_instance.ca3 = ca3
#                                 score_instance.exam_score = exam_score
#                                 # Model.save() handles the dynamic CA/Exam validation logic
#                                 score_instance.save()
#                             else:
#                                 Score.objects.create(
#                                     student=student,
#                                     subject=selected_subject,
#                                     term=current_term,
#                                     ca1=ca1,
#                                     ca2=ca2,
#                                     ca3=ca3,
#                                     exam_score=exam_score
#                                 )
#                         elif score_id:
#                             # If existing record is cleared, delete it
#                             score_instance = get_object_or_404(Score, id=score_id)
#                             score_instance.delete()

#                 messages.success(request, 'Scores saved successfully!')
#                 return redirect('results:score_entry_success')
                
#             except ValidationError as e:
#                 if hasattr(e, 'message_dict'):
#                     for field, error_list in e.message_dict.items():
#                         for msg in error_list:
#                             messages.error(request, f"Validation Error: {msg}")
#                 else:
#                     messages.error(request, f"Validation Error: {e.message}")

#         # If we reach here, there were errors
#         messages.error(request, 'Please correct the errors below.')
        
#         # Re-fetch assigned lists for context rebuild
#         if request.user.is_superuser or request.user.is_staff:
#             assigned_subjects = Subject.objects.all()
#             assigned_standards = Standard.objects.all()
#         else:
#             assigned_subjects = teacher.subjects_taught.all()
#             assigned_standards = teacher.standards_assigned.all()

#         try:
#             school_identity = SchoolIdentity.objects.first()
#         except SchoolIdentity.DoesNotExist:
#             school_identity = None

#         context = {
#             'current_term': current_term,
#             'assigned_subjects': assigned_subjects,
#             'assigned_standards': assigned_standards,
#             'selected_subject_id': int(selected_subject_id) if selected_subject_id else None,
#             'selected_standard_id': int(selected_standard_id) if selected_standard_id else None,
#             'selected_subject': selected_subject,
#             'selected_standard': selected_standard,
#             'formset': formset,
#             'students_in_standard': students_in_standard,
#             'school_identity': school_identity,
#             'max_ca': max_ca,
#             'max_exam': max_exam,
#         }
#         return render(request, self.template_name, context)

from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.forms import formset_factory
from django.db import transaction
from django.core.exceptions import ValidationError

class ScoreEntryView(LoginRequiredMixin, TeacherRequiredMixin, View):
    template_name = 'results/score_entry.html'

    def get_grading_config(self):
        """Helper to fetch dynamic totals from settings or use 40/60 defaults."""
        config = SchoolYearSettings.objects.filter(is_active=True).first()
        if config:
            return config.max_ca_total, config.max_exam_score
        return 40, 60

    def get(self, request, *args, **kwargs):
        # Fetch dynamic configuration
        max_ca, max_exam = self.get_grading_config()

        # If superuser or staff, they are treated as having access to all classes and subjects
        if request.user.is_superuser or request.user.is_staff:
            teacher = None
            assigned_subjects = Subject.objects.all()
            assigned_standards = Standard.objects.all()
        else:
            teacher = request.user.teacher
            assigned_subjects = teacher.subjects_taught.all()
            assigned_standards = teacher.standards_assigned.all()

        current_term = Term.objects.filter(is_current=True).first()
        if not current_term:
            messages.error(request, 'No current term set. Please contact administration.')
            return render(request, self.template_name, {})

        selected_subject = None
        selected_standard = None

        selected_subject_id = request.GET.get('subject', assigned_subjects.first().id if assigned_subjects.exists() else None)
        selected_standard_id = request.GET.get('standard', assigned_standards.first().id if assigned_standards.exists() else None)

        students_in_standard = []
        ScoreFormSet = formset_factory(ScoreEntryForm, extra=0)
        
        # Initialize formset with dynamic limits
        formset = ScoreFormSet(form_kwargs={'max_ca': max_ca, 'max_exam': max_exam})

        if selected_subject_id and selected_standard_id:
            try:
                selected_subject = Subject.objects.get(id=selected_subject_id)
                selected_standard = Standard.objects.get(id=selected_standard_id)
            except (Subject.DoesNotExist, Standard.DoesNotExist):
                messages.error(request, 'Invalid subject or standard selected.')

            if selected_subject and selected_standard:
                students_in_standard = Student.objects.filter(current_class=selected_standard).order_by('last_name', 'first_name')

                initial_data = []
                for student in students_in_standard:
                    score_instance = Score.objects.filter(
                        student=student,
                        subject=selected_subject,
                        term=current_term
                    ).first()

                    initial_data.append({
                        'student_id': student.id,
                        'student_name': student.get_full_name(),
                        'score_id': score_instance.id if score_instance else None,
                        'ca1': score_instance.ca1 if score_instance else None,
                        'ca2': score_instance.ca2 if score_instance else None,
                        'ca3': score_instance.ca3 if score_instance else None,
                        'exam_score': score_instance.exam_score if score_instance else None,
                    })

                # Re-initialize formset with initial data AND dynamic limits
                formset = ScoreFormSet(
                    initial=initial_data, 
                    form_kwargs={'max_ca': max_ca, 'max_exam': max_exam}
                )

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
            'max_ca': max_ca,
            'max_exam': max_exam,
        }
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        # Fetch dynamic configuration
        max_ca, max_exam = self.get_grading_config()

        if request.user.is_superuser or request.user.is_staff:
            teacher = None
        else:
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

        # Authorization check only for non-superuser/staff
        if teacher and (not teacher.subjects_taught.filter(id=selected_subject.id).exists() or
                        not teacher.standards_assigned.filter(id=selected_standard.id).exists()):
            messages.error(request, 'You are not authorized to enter scores for this subject or standard.')
            return redirect('score_entry')

        students_in_standard = Student.objects.filter(current_class=selected_standard).order_by('last_name', 'first_name')
        ScoreFormSet = formset_factory(ScoreEntryForm, extra=0)
        
        # Pass dynamic limits into the POST initialization so the form knows how to validate
        formset = ScoreFormSet(
            request.POST, 
            form_kwargs={'max_ca': max_ca, 'max_exam': max_exam}
        )

        if formset.is_valid():
            try:
                with transaction.atomic():
                    for form in formset:
                        if form.cleaned_data.get('student_id') is None:
                            continue

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
                                # Model.save() handles the dynamic CA/Exam validation logic
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
                            # If existing record is cleared, delete it
                            score_instance = get_object_or_404(Score, id=score_id)
                            score_instance.delete()

                messages.success(request, 'Scores saved successfully!')
                return redirect('results:score_entry_success')
                
            except ValidationError as e:
                if hasattr(e, 'message_dict'):
                    for field, error_list in e.message_dict.items():
                        for msg in error_list:
                            messages.error(request, f"Validation Error: {msg}")
                else:
                    messages.error(request, f"Validation Error: {e.message}")

        # If we reach here, there were errors
        messages.error(request, 'Please correct the errors below.')
        
        # Re-fetch assigned lists for context rebuild
        if request.user.is_superuser or request.user.is_staff:
            assigned_subjects = Subject.objects.all()
            assigned_standards = Standard.objects.all()
        else:
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
            'max_ca': max_ca,
            'max_exam': max_exam,
        }
        return render(request, self.template_name, context)


# Simple success view
class ScoreEntrySuccessView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return render(request, 'results/score_entry_success.html')


# For Report Card List
class TeacherRequiredMixin:
    def dispatch(self, request, *args, **kwargs):
        user = request.user

        # Allow admin & staff
        if user.is_superuser or user.is_staff:
            return super().dispatch(request, *args, **kwargs)

        # Allow users with teacher profile
        if hasattr(user, 'teacher'):
            return super().dispatch(request, *args, **kwargs)

        raise PermissionDenied

class ReportCardListView(LoginRequiredMixin, TeacherRequiredMixin, View):
    template_name = 'results/termly_report_card_list.html'

    def get(self, request, *args, **kwargs):
        # Pass request.user to the form so we can filter dropdowns in forms.py
        form = ReportCardFilterForm(request.GET, user=request.user)
        students = []
        selected_term = None
        selected_standard = None

        user = request.user
        is_admin = user.is_superuser or user.is_staff
        teacher_profile = getattr(user, 'teacher', None)

        if form.is_valid():
            selected_term = form.cleaned_data['term']
            selected_standard = form.cleaned_data['standard']

            if selected_term:
                # 1. Start with the base student queryset
                queryset = Student.objects.all()

                # 2. Apply Security: If teacher, they ONLY see their own class
                if not is_admin and teacher_profile:
                    queryset = queryset.filter(current_class__form_teacher=teacher_profile)
                    # Force standard to their own class if they try to bypass via URL
                    if selected_standard and selected_standard.form_teacher != teacher_profile:
                        selected_standard = None

                # 3. Apply the Filter
                if selected_standard:
                    students = queryset.filter(current_class=selected_standard)
                else:
                    # If no standard selected, show all students in their allowed scope who have scores
                    students = queryset.filter(scores__term=selected_term).distinct()
                
                students = students.order_by('last_name', 'first_name')
            else:
                messages.warning(request, "Please select a term to view students.")

        else:
            # Handle Initial Load (Pre-select current term)
            current_term = Term.objects.filter(is_current=True).first()
            if current_term:
                form = ReportCardFilterForm(initial={'term': current_term}, user=request.user)
                selected_term = current_term
                
                # Base queryset for current term
                queryset = Student.objects.filter(scores__term=current_term).distinct()
                
                if not is_admin and teacher_profile:
                    students = queryset.filter(current_class__form_teacher=teacher_profile)
                else:
                    students = queryset
                
                students = students.order_by('last_name', 'first_name')

        context = {
            'form': form,
            'students': students,
            'selected_term': selected_term,
            'selected_standard': selected_standard,
            'is_admin': is_admin,
        }
        return render(request, self.template_name, context)




class AdminTeacherOrOwnerMixin:
    """
    Allows:
    - Superuser
    - Staff
    - Teacher (optionally restrict to their class)
    - The student themselves
    """

    def has_permission(self, request, student):
        user = request.user

        # Admin access
        if user.is_superuser or user.is_staff:
            return True

        # Teacher access (OPTIONAL: restrict to their own class)
        if hasattr(user, 'teacher'):
            # If you want teachers to see ALL students, use:
            # return True

            # If you want teachers to see ONLY their class (recommended):
            return student.current_class.form_teacher == user.teacher

        # Student viewing own report
        if hasattr(user, 'student') and user.student == student:
            return True

        return False

    def handle_no_permission(self, request):
        messages.error(request, "You are not authorized to view this report card.")
        if hasattr(request.user, 'student'):
            return redirect('student_dashboard')
        return redirect('home')


# # used until 20/03/2026
# class StudentReportCardView(LoginRequiredMixin, AdminTeacherOrOwnerMixin, View):
#     """
#     Generates and displays a single student's report card for a specific term.
#     Accessible by teachers/admins (for any student) and by the student themselves.
#     """
#     # TEMPLATE OPTTION 1
#     template_name = 'results/test_student_report_card_detail.html'
#     # TEMPLATE OPTTION 2
#     # template_name = 'results/test_student_report_card_detail_VERTICAL.html'

#     pdf_template_name = 'results/test_student_report_card_pdf.html' # Dedicated template for PDF layout

#     def get(self, request, student_id, term_id, *args, **kwargs):
#         # Assumes Student, Term, etc. models are imported
#         student = get_object_or_404(Student, id=student_id)
#         term = get_object_or_404(Term, id=term_id)
#         standard = student.current_class # Get the standard for ranking

#         # Authorization Check (No change)
#         # if not hasattr(request.user, 'teacher'):
#         #     if not (hasattr(request.user, 'student') and request.user.student == student):
#         #         messages.error(request, "You are not authorized to view this report card.")
#         #         return redirect('student_dashboard' if hasattr(request.user, 'student') else 'home')

#         student = get_object_or_404(Student, id=student_id)
#         term = get_object_or_404(Term, id=term_id)
#         standard = student.current_class

#         # Authorization Check (Clean & Reusable)
#         if not self.has_permission(request, student):
#             return self.handle_no_permission(request)


#         # --- ATTENDANCE and NEXT TERM ---
#         student_attendance = Attendance.objects.filter(student=student, date__gte=term.start_date, date__lte=term.end_date)

#         days_present = student_attendance.filter(present=True).count()
#         days_absent = student_attendance.filter(present=False).count()

#         total_school_days = Attendance.objects.filter(
#             student__current_class=student.current_class,
#             date__gte=term.start_date,
#             date__lte=term.end_date
#         ).values('date').distinct().count()

#         next_term = Term.objects.filter(start_date__gt=term.end_date).order_by('start_date').first()
#         next_term_start_date = next_term.start_date if next_term else None

#         total_students_in_class = Student.objects.filter(current_class=student.current_class).count()

#         # Fetch scores for the student in the selected term
#         scores = Score.objects.filter(student=student, term=term).select_related('subject').order_by('subject__name')

#         report_data = []
#         total_scores_sum = 0
#         subjects_with_scores_count = 0

#         for score in scores:
#             current_total_score = score.total_score

#             if current_total_score is not None:
#                 # Assumes utility functions like get_grade, get_subject_remark are defined/imported
#                 total_ca = (score.ca1 or 0) + (score.ca2 or 0) + (score.ca3 or 0)

#                 report_data.append({
#                     'subject': score.subject.name,
#                     'ca1': score.ca1 if score.ca1 is not None else 'N/A',
#                     'ca2': score.ca2 if score.ca2 is not None else 'N/A',
#                     'ca3': score.ca3 if score.ca3 is not None else 'N/A',
#                     'total_ca': total_ca,
#                     'exam_score': score.exam_score if score.exam_score is not None else 'N/A',
#                     'total_score': current_total_score,
#                     'grade': get_grade(current_total_score),
#                     'remark': get_subject_remark(current_total_score),
#                 })

#                 total_scores_sum += current_total_score
#                 subjects_with_scores_count += 1

#         # --- Calculate Overall Average ---
#         overall_average = None
#         overall_remark = "No scores recorded for this term."
#         if subjects_with_scores_count > 0:
#             overall_average = total_scores_sum / subjects_with_scores_count
#             overall_remark = get_overall_remark(overall_average)

#         # --- RANKING LOGIC INTEGRATION ---
#         student_rank, total_students = get_student_class_rank(student, standard, term)

#         student_position_display = 'N/A (Unranked)'
#         if student_rank != 'N/A' and subjects_with_scores_count > 0:
#             student_position_display = f"{student_rank} out of {total_students}"
#         # --------------------------------

#         motor_ability_score = MotorAbilityScore.objects.filter(student=student, term=term).first()

#         try:
#             school_identity = SchoolIdentity.objects.first()
#         except SchoolIdentity.DoesNotExist:
#             school_identity = None

#         context = {
#             'student': student,
#             'term': term,
#             'report_data': report_data,
#             'overall_average': overall_average,
#             'overall_remark': overall_remark,
#             'student_position_display': student_position_display,
#             'motor_ability_score': motor_ability_score,
#             'school_identity': school_identity,
#             'total_school_days': total_school_days,
#             'days_present': days_present,
#             'days_absent': days_absent,
#             'next_term_start_date': next_term_start_date,
#             'total_students_in_class': total_students_in_class,
#         }

#         # --- PDF GENERATION LOGIC ---
#         if 'download' in request.GET and request.GET['download'] == 'pdf':
#             # Assumes render_to_pdf_xhtml2pdf function and HttpResponse are imported
#             filename = f"{student.first_name.replace(' ', '_')}_{term.name.replace(' ', '_')}_TermlyReportCard.pdf"
#             pdf_response = render_to_pdf_xhtml2pdf(self.pdf_template_name, context)

#             if pdf_response:
#                 # Set the response content type and disposition for download
#                 pdf_response['Content-Disposition'] = f'attachment; filename="{filename}"'
#                 pdf_response['Content-Type'] = 'application/pdf' # Ensure correct content type for download
#                 return pdf_response
#             else:
#                 return HttpResponse("Error generating PDF.", status=500)
#         # ----------------------------

#         return render(request, self.template_name, context)

# new logic to capture new entries
#Student Report Card View
# ======================================================================================================
# New logic to allow class position toggle
from results.models import ClassPositionSetting, ReportComments

class StudentReportCardView(LoginRequiredMixin, AdminTeacherOrOwnerMixin, View):

    template_name = 'results/test_student_report_card_detail_extended.html'
    pdf_template_name = 'results/test_student_report_card_pdf.html'

    def get(self, request, student_id, term_id, *args, **kwargs):
        student = get_object_or_404(Student, id=student_id)
        term = get_object_or_404(Term, id=term_id)
        standard = student.current_class

        if not self.has_permission(request, student):
            return self.handle_no_permission(request)

        # ---------------- ATTENDANCE ----------------
        student_attendance = Attendance.objects.filter(
            student=student,
            date__gte=term.start_date,
            date__lte=term.end_date
        )

        days_present = student_attendance.filter(present=True).count()
        days_absent = student_attendance.filter(present=False).count()

        total_school_days = Attendance.objects.filter(
            student__current_class=standard,
            date__gte=term.start_date,
            date__lte=term.end_date
        ).values('date').distinct().count()

        next_term = Term.objects.filter(start_date__gt=term.end_date).order_by('start_date').first()
        next_term_start_date = next_term.start_date if next_term else None
        total_students_in_class = Student.objects.filter(current_class=standard).count()

        # ---------------- SCORES ----------------
        scores = Score.objects.filter(
            student=student,
            term=term
        ).select_related('subject').order_by('subject__name')

        report_data = []
        total_scores_sum = 0
        subjects_with_scores_count = 0
        total_marks_obtained = 0  # 🔥

        for score in scores:
            current_total_score = score.total_score
            if current_total_score is not None:
                total_ca = (score.ca1 or 0) + (score.ca2 or 0) + (score.ca3 or 0)

                class_scores = Score.objects.filter(
                    subject=score.subject,
                    term=term,
                    student__current_class=standard,
                    total_score__isnull=False
                )

                subject_avg = class_scores.aggregate(avg=Avg('total_score'))['avg']
                subject_min = class_scores.aggregate(min=Min('total_score'))['min']
                subject_max = class_scores.aggregate(max=Max('total_score'))['max']

                higher_scores_count = class_scores.filter(total_score__gt=current_total_score).count()
                subject_position = higher_scores_count + 1

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
                    'subject_avg': subject_avg,
                    'subject_min': subject_min,
                    'subject_max': subject_max,
                    'subject_position': subject_position,
                })

                total_scores_sum += current_total_score
                total_marks_obtained += current_total_score
                subjects_with_scores_count += 1

        # ---------------- STUDENT AVERAGE ----------------
        overall_average = None
        overall_remark = "No scores recorded for this term."
        if subjects_with_scores_count > 0:
            overall_average = total_scores_sum / subjects_with_scores_count
            overall_remark = get_overall_remark(overall_average)

        # ---------------- CLASS AVERAGE STATS ----------------
        class_students = Student.objects.filter(current_class=standard)
        student_averages = []

        for stu in class_students:
            stu_scores = Score.objects.filter(student=stu, term=term)
            total = stu_scores.aggregate(total=Sum('total_score'))['total']
            count = stu_scores.filter(total_score__isnull=False).count()
            if total is not None and count > 0:
                avg = total / count
                student_averages.append(avg)

        class_avg = sum(student_averages) / len(student_averages) if student_averages else None
        class_max_avg = max(student_averages) if student_averages else None
        class_min_avg = min(student_averages) if student_averages else None

        # ---------------- RANKING ----------------
        student_rank, total_students = get_student_class_rank(student, standard, term)
        student_position_display = 'N/A (Unranked)'
        if student_rank != 'N/A' and subjects_with_scores_count > 0:
            student_position_display = f"{student_rank} out of {total_students}"

        motor_ability_score = MotorAbilityScore.objects.filter(student=student, term=term).first()
        school_identity = SchoolIdentity.objects.first()

        # ---------------- 🔥 NEW: CLASS POSITION SETTING ----------------
        try:
            position_setting = ClassPositionSetting.objects.get(
                standard=standard,
                term=term,
                session=term.session  # Make sure Term has session
            )
            show_class_position = position_setting.show_class_position
        except ClassPositionSetting.DoesNotExist:
            show_class_position = True  # Default to True if not configured

        # ---------------- 🔥 NEW: REPORT COMMENTS ----------------
        try:
            report_comments = ReportComments.objects.get(
                student=student,
                standard=standard,
                term=term,
                session=term.session
            )
            teacher_comment = report_comments.teacher_comment
            principal_comment = report_comments.principal_comment
        except ReportComments.DoesNotExist:
            teacher_comment = None
            principal_comment = None

        # ---------------- CONTEXT ----------------
        context = {
            'student': student,
            'term': term,
            'report_data': report_data,

            'overall_average': overall_average,
            'overall_remark': overall_remark,

            'student_position_display': student_position_display,
            'show_class_position': show_class_position,  # 🔥

            'teacher_comment': teacher_comment,          # 🔥
            'principal_comment': principal_comment,      # 🔥

            'total_marks_obtained': total_marks_obtained,
            'subjects_with_scores_count': subjects_with_scores_count,
            'class_avg': class_avg,
            'class_max_avg': class_max_avg,
            'class_min_avg': class_min_avg,

            'motor_ability_score': motor_ability_score,
            'school_identity': school_identity,

            'total_school_days': total_school_days,
            'days_present': days_present,
            'days_absent': days_absent,
            'next_term_start_date': next_term_start_date,
            'total_students_in_class': total_students_in_class,
        }

        # ---------------- PDF ----------------
        if request.GET.get('download') == 'pdf':
            filename = f"{student.first_name}_{term.name}_ReportCard.pdf"
            pdf_response = render_to_pdf_xhtml2pdf(self.pdf_template_name, context)

            if pdf_response:
                pdf_response['Content-Disposition'] = f'attachment; filename="{filename}"'
                pdf_response['Content-Type'] = 'application/pdf'
                return pdf_response

            return HttpResponse("Error generating PDF.", status=500)

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



class SessionReportCardListView(LoginRequiredMixin, TeacherRequiredMixin, View):
    """
    Allows teachers/admins to select a session and standard,
    then view a list of students to generate their annual report cards.
    """
    template_name = 'results/test_session_report_card_list.html'

    def get(self, request, *args, **kwargs):
        # Pass the user to the form
        form = SessionReportCardFilterForm(request.GET, user=request.user)
        students = []
        selected_session = None
        selected_standard = None

        if form.is_valid():
            selected_session = form.cleaned_data['session']
            selected_standard = form.cleaned_data['standard']

            if selected_session:
                student_filter = Q(scores__term__session=selected_session)
                
                # Apply standard filter if selected
                if selected_standard:
                    student_filter &= Q(current_class=selected_standard)
                # FORCE logic: If user is a teacher, ensure they only see their class even if standard isn't selected
                elif not (request.user.is_superuser or request.user.is_staff) and hasattr(request.user, 'teacher'):
                    student_filter &= Q(current_class__form_teacher=request.user.teacher)

                students = Student.objects.filter(student_filter).distinct().order_by('last_name', 'first_name')

                if not students and (selected_standard or selected_session):
                     messages.info(request, f"No students with recorded scores found for {selected_session.name}.")
            else:
                messages.warning(request, "Please select an academic session to view students.")
        
        else: 
            # Initial load logic
            current_session = Session.objects.filter(is_current=True).first()
            if current_session:
                form = SessionReportCardFilterForm(initial={'session': current_session.id}, user=request.user)
                
                student_filter = Q(scores__term__session=current_session)
                # Restrict initial student list if user is a teacher
                if not (request.user.is_superuser or request.user.is_staff) and hasattr(request.user, 'teacher'):
                    student_filter &= Q(current_class__form_teacher=request.user.teacher)
                
                students = Student.objects.filter(student_filter).distinct().order_by('last_name', 'first_name')
                selected_session = current_session

        context = {
            'form': form,
            'students': students,
            'selected_session': selected_session,
            'selected_standard': selected_standard,
        }
        return render(request, self.template_name, context)



# NEW SESSION OVERALL AVERAGE
# Assuming these helper functions and models are imported correctly
# from .models import Student, Session, Score, MotorAbilityScore, Attendance, SchoolIdentity
# from .utils import get_grade, get_subject_remark, get_overall_remark, render_to_pdf_xhtml2pdf

class StudentSessionReportCardView(LoginRequiredMixin, View):
    """
    Generates a cumulative report card where averages are based ONLY on 
    terms and subjects where data actually exists.
    """
    template_name = 'results/session_report_card_detail.html'
    pdf_template_name = 'results/session_report_card_pdf.html'

    def get(self, request, student_id, session_id, *args, **kwargs):
        student = get_object_or_404(Student, id=student_id)
        session = get_object_or_404(Session, id=session_id)

        # 1. Authorization Check
        if not hasattr(request.user, 'teacher') and not request.user.is_staff:
            if not (hasattr(request.user, 'student') and request.user.student == student):
                messages.error(request, "You are not authorized to view this report card.")
                return redirect('student_dashboard' if hasattr(request.user, 'student') else 'home')

        # 2. Term Setup
        terms_in_session = session.terms.all().order_by('start_date')
        if not terms_in_session.exists():
            messages.warning(request, f"No terms defined for {session.name}.")
            return redirect(request.META.get('HTTP_REFERER', 'session_report_card_list'))

        # 3. Aggregate scores per subject, counting ONLY terms where a score exists
        subject_cumulative_data = Score.objects.filter(
            student=student,
            term__in=terms_in_session
        ).values('subject__name', 'subject__id').annotate(
            cumulative_total_score=Sum('total_score'),
            active_term_count=Count('term', filter=Q(total_score__isnull=False))
        ).order_by('subject__name')

        report_data = []
        overall_effective_average_sum = 0
        subjects_counted_for_overall_average = 0

        for item in subject_cumulative_data:
            subject_id = item['subject__id']
            subject_name = item['subject__name']
            cumulative_score_raw = item['cumulative_total_score']
            active_term_count = item['active_term_count']

            # Get individual term scores for table display
            term_scores_for_subject = {}
            for term in terms_in_session:
                try:
                    score_inst = Score.objects.get(student=student, subject__id=subject_id, term=term)
                    term_scores_for_subject[term.name] = score_inst.total_score if score_inst.total_score is not None else 'N/A'
                except Score.DoesNotExist:
                    term_scores_for_subject[term.name] = 'N/A'

            # Calculate subject average based ONLY on active terms
            effective_subject_average = None
            if cumulative_score_raw is not None and active_term_count > 0:
                effective_subject_average = cumulative_score_raw / active_term_count
                overall_effective_average_sum += effective_subject_average
                subjects_counted_for_overall_average += 1

            report_data.append({
                'subject': subject_name,
                'term_scores': term_scores_for_subject,
                'cumulative_total_score': f"{cumulative_score_raw:.2f}" if cumulative_score_raw is not None else 'N/A',
                'effective_subject_average': f"{effective_subject_average:.2f}" if effective_subject_average is not None else 'N/A',
                'grade': get_grade(effective_subject_average),
                'remark': get_subject_remark(effective_subject_average),
            })

        # 4. Calculate Overall Session Average
        overall_session_average = None
        overall_remark = "No scores recorded for this session."

        if subjects_counted_for_overall_average > 0:
            overall_session_average = overall_effective_average_sum / subjects_counted_for_overall_average
            overall_remark = get_overall_remark(overall_session_average)

        # 5. Aggregate Motor Ability Scores (Behavioral)
        motor_ability_scores = MotorAbilityScore.objects.filter(student=student, term__session=session)
        agg_motor = motor_ability_scores.aggregate(
            avg_honesty=Avg('honesty'), avg_politeness=Avg('politeness'),
            avg_neatness=Avg('neatness'), avg_cooperation=Avg('cooperation'),
            avg_obedience=Avg('obedience'), avg_attentiveness=Avg('attentiveness'),
            avg_punctuality=Avg('punctuality'), avg_perseverance=Avg('perseverance'),
            avg_emotional_stability=Avg('emotional_stability'), avg_attitude=Avg('attitude'),
            avg_leadership=Avg('leadership'), avg_physical_education=Avg('physical_education'),
            avg_games=Avg('games'), avg_musical=Avg('musical'),
            avg_handwriting=Avg('handwriting'), avg_reading=Avg('reading'),
            avg_verbal_fluency=Avg('verbal_fluency'), avg_handling_tools=Avg('handling_tools'),

        )

        processed_motor = {k: (round(min(v, 5)) if v is not None else 0) for k, v in agg_motor.items()}

        # 6. Attendance Logic
        attendance_records = Attendance.objects.filter(
            student=student,
            date__gte=session.start_date,
            date__lte=session.end_date
        )
        total_school_days = attendance_records.count()
        days_present = attendance_records.filter(present=True).count()
        days_absent = attendance_records.filter(present=False).count()

        # 7. Next Session / School Info
        next_session = Session.objects.filter(start_date__gt=session.end_date).order_by('start_date').first()
        
        try:
            school_identity = SchoolIdentity.objects.first()
        except:
            school_identity = None

        context = {
            'student': student,
            'session': session,
            'terms_in_session': terms_in_session,
            'report_data': report_data,
            'overall_session_average': f"{overall_session_average:.2f}" if overall_session_average is not None else 'N/A',
            'overall_remark': overall_remark,
            'aggregated_motor_abilities': processed_motor,
            'school_identity': school_identity,
            'total_school_days': total_school_days,
            'days_present': days_present,
            'days_absent': days_absent,
            'next_session_start_date': next_session.start_date if next_session else None,
        }

        # 8. PDF Logic
        if request.GET.get('download') == 'pdf':
            filename = f"{student.first_name}_{session.name}_AnnualReport.pdf"
            pdf_response = render_to_pdf_xhtml2pdf(self.pdf_template_name, context)
            if pdf_response:
                pdf_response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return pdf_response
            return HttpResponse("Error generating PDF.", status=500)

        return render(request, self.template_name, context)



# Student Session Report Publication

class SessionPublicationControlView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'results/session_publication_control.html'

    def test_func(self):
        # Only Staff/Superusers can manage publication
        return self.request.user.is_staff

    def get(self, request):
        class_id = request.GET.get('class_id')
        session_id = request.GET.get('session_id')
        
        students_data = []
        if class_id and session_id:
            class_obj = get_object_or_404(Standard, id=class_id)
            # Fetch all students in the selected class
            student_list = Student.objects.filter(current_class=class_obj).order_by('last_name')
            
            for student in student_list:
                # get_or_create ensures a record exists for every student in the session
                status_obj, created = SessionResultStatus.objects.get_or_create(
                    student=student, 
                    session_id=session_id
                )
                students_data.append({
                    'id': student.id,
                    'name': student.get_full_name(),
                    'is_published': status_obj.is_published
                })

        context = {
            'classes': Standard.objects.all().order_by('name'),
            'sessions': Session.objects.all().order_by('-id'),
            'students': students_data,
            'selected_class': class_id,
            'selected_session': session_id,
        }
        return render(request, self.template_name, context)

    def post(self, request):
        session_id = request.POST.get('session_id')
        class_id = request.POST.get('class_id')
        
        # 'published_students' only contains IDs of CHECKED boxes
        published_ids = request.POST.getlist('published_students')
        
        # 'all_student_ids' contains EVERY student ID currently visible on the page
        all_shown_ids = request.POST.getlist('all_student_ids')

        if not session_id or not all_shown_ids:
            messages.error(request, "Selection error: No data found to update.")
            return redirect(f"{request.path}?class_id={class_id}&session_id={session_id}")

        # STEP 1: RESET everything in the current view to False
        # This handles the "Unchecking" logic
        SessionResultStatus.objects.filter(
            student_id__in=all_shown_ids, 
            session_id=session_id
        ).update(is_published=False)

        # STEP 2: SET only the checked ones to True
        if published_ids:
            SessionResultStatus.objects.filter(
                student_id__in=published_ids, 
                session_id=session_id
            ).update(is_published=True)

        messages.success(request, f"Successfully updated results publication for the selected class.")
        return redirect(f"{request.path}?class_id={class_id}&session_id={session_id}")



class StudentDashboardView(LoginRequiredMixin, View):
    template_name = 'results/student_dashboard.html'

    def get(self, request, *args, **kwargs):
        if hasattr(request.user, 'student'):
            student = request.user.student

            # 1. RESTORE ORIGINAL TERMLY LOGIC
            # This allows your existing termly publication logic to handle things.
            # (If your previous termly logic was just "if they have scores", this brings it back)
            terms_with_scores = Term.objects.filter(
                score__student=student
            ).distinct().order_by('-start_date')

            # 2. APPLY NEW SESSION (ANNUAL) LOGIC SEPARATELY
            # We only filter the sessions based on the new SessionResultStatus table.
            published_session_ids = SessionResultStatus.objects.filter(
                student=student, 
                is_published=True
            ).values_list('session_id', flat=True)

            sessions_with_scores = Session.objects.filter(
                id__in=published_session_ids, # Only published ones
                terms__score__student=student # That have scores
            ).distinct().order_by('-start_date')

            # --- Debugging ---
            print(f"\n--- Dashboard Logic Sync ---")
            print(f"Terms Visible: {terms_with_scores.count()}")
            print(f"Sessions (Annual) Published: {sessions_with_scores.count()}")
            print("-----------------------------\n")

            context = {
                'student': student,
                'terms': terms_with_scores,    # Termly links (Restored)
                'sessions': sessions_with_scores, # Annual links (Controlled)
            }
            return render(request, self.template_name, context)
        else:
            messages.error(request, "Your account is not linked to a student profile.")
            return redirect('portal-home')

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

        overall_ranking_data.sort(key=lambda x: x['overall_average'], reverse=True)
        current_rank = 0
        last_average = -1
        for i, data in enumerate(overall_ranking_data):
            if data['overall_average'] != last_average:
                current_rank = i + 1
            data['rank'] = current_rank
            last_average = data['overall_average']

        # --- EXPORT LOGIC: OVERALL ---
        if request.GET.get('export') == 'csv' and not request.GET.get('subject_id'):
            response = HttpResponse(content_type='text/csv')
            filename = f"Overall_Ranking_{standard.name}_{term.name}.csv".replace(" ", "_")
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            writer = csv.writer(response)
            writer.writerow(['Position', 'Student Name', 'USN', 'Overall Average (%)'])
            for row in overall_ranking_data:
                writer.writerow([row['rank'], row['student'].user.get_full_name(), row['student'].USN, f"{row['overall_average']:.2f}"])
            return response

        # --- Subject-Specific Ranking Logic ---
        subject_ranking_data = {}
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
                    subject_scores.append({'student': student, 'total_score': score.total_score})

            subject_scores.sort(key=lambda x: x['total_score'], reverse=True)
            current_rank_subject = 0
            last_score_subject = -1
            for i, data in enumerate(subject_scores):
                if data['total_score'] != last_score_subject:
                    current_rank_subject = i + 1
                data['rank'] = current_rank_subject
                last_score_subject = data['total_score']
            
            # --- EXPORT LOGIC: SPECIFIC SUBJECT ---
            # This triggers if the button for a specific subject is clicked
            if request.GET.get('export') == 'csv' and request.GET.get('subject_id') == str(subject_info['subject_id']):
                response = HttpResponse(content_type='text/csv')
                filename = f"{subject_info['subject__name']}_Ranking_{standard.name}_{term}.csv".replace(" ", "_")
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                writer = csv.writer(response)
                writer.writerow(['Position', 'Student Name', 'USN', 'Score (%)'])
                for item in subject_scores:
                    writer.writerow([item['rank'], item['student'].user.get_full_name(), item['student'].USN, item['total_score']])
                return response

            subject_ranking_data[subject_info['subject__name']] = {
                'id': subject_info['subject_id'], # Added ID to help the template
                'scores': subject_scores
            }

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
    template_name = 'results/ranking_standard_and_terms_list.html'

    def get(self, request, *args, **kwargs):
        # Fetch all standards and terms
        all_standards = Standard.objects.all().order_by('name')
        all_terms = Term.objects.all().order_by('-start_date')

        context = {
            'all_standards': all_standards,
            'all_terms': all_terms,
        }

        return render(request, self.template_name, context)



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



# Mid term score entry for new logic
class MidTermScoreEntryView(LoginRequiredMixin, View):
    template_name = 'results/midterm_score_entry.html'

    def dispatch(self, request, *args, **kwargs):
        # Only teachers and staff can access
        if not (hasattr(request.user, 'teacher') or request.user.is_staff):
            messages.error(request, "You do not have permission to enter scores.")
            return redirect('pages:portal-home')
        return super().dispatch(request, *args, **kwargs)

    def get_formset(self, max_score, queryset, data=None):
        """
        Create a ModelFormSet passing max_score to each form for validation.
        """
        MidTermScoreFormSet = modelformset_factory(
            MidTermScore,
            form=MidTermScoreForm,
            extra=0,
            fields=('exam_total_score',)
        )

        return MidTermScoreFormSet(
            data=data,
            queryset=queryset,
            form_kwargs={'max_score': max_score}
        )

    def get(self, request, class_id, subject_id, term_id):
        assigned_class = get_object_or_404(Standard, id=class_id)
        subject = get_object_or_404(Subject, id=subject_id)
        term = get_object_or_404(Term, id=term_id)

        # --- Authorization for teachers ---
        if hasattr(request.user, 'teacher') and not request.user.is_staff:
            teacher = request.user.teacher
            is_assigned_to_class = assigned_class in teacher.standards_assigned.all()
            teaches_subject = subject in teacher.subjects_taught.all()
            if not (is_assigned_to_class and teaches_subject):
                messages.error(
                    request,
                    f"You are not authorized to enter scores for {subject.name} in {assigned_class.name}."
                )
                return redirect('results:teacher_dashboard')

        
        exam_setting = get_object_or_404(
            ExamSetting,
            term=term,
            exam_type="Midterm"
        )

        central_max = exam_setting.max_score  # used for form validation

        # --- Ensure all students have a MidTermScore instance ---
        students = Student.objects.filter(current_class=assigned_class).order_by('last_name')
        existing_student_ids = MidTermScore.objects.filter(
            student__in=students, subject=subject, term=term
        ).values_list('student_id', flat=True)

        for student in students:
            if student.id not in existing_student_ids:
                MidTermScore.objects.create(student=student, subject=subject, term=term)

        queryset = MidTermScore.objects.filter(
            student__in=students,
            subject=subject,
            term=term
        ).select_related('student').order_by('student__last_name')

        formset = self.get_formset(central_max, queryset)

        context = {
            'formset': formset,
            'assigned_class': assigned_class,
            'subject': subject,
            'term': term,
            'students': students,
            'central_max': central_max,
            'exam_setting': exam_setting,  # <-- pass the object

        }
        return render(request, self.template_name, context)

    def post(self, request, class_id, subject_id, term_id):
        assigned_class = get_object_or_404(Standard, id=class_id)
        subject = get_object_or_404(Subject, id=subject_id)
        term = get_object_or_404(Term, id=term_id)

        # --- Authorization check ---
        if hasattr(request.user, 'teacher') and not request.user.is_staff:
            teacher = request.user.teacher
            if not (assigned_class in teacher.standards_assigned.all() and subject in teacher.subjects_taught.all()):
                messages.error(request, "Unauthorized action.")
                return redirect('results:teacher_dashboard')

        # --- Get central max score ---
        exam_setting = get_object_or_404(
            ExamSetting,
            term=term,
            exam_type="Midterm"
        )
        central_max = exam_setting.max_score

        # --- Prepare queryset ---
        students = Student.objects.filter(current_class=assigned_class)
        queryset = MidTermScore.objects.filter(
            student__in=students,
            subject=subject,
            term=term
        ).select_related('student').order_by('student__last_name')

        formset = self.get_formset(central_max, queryset, data=request.POST)

        if formset.is_valid():
            instances_to_save = []
            instances_to_delete = []

            for form in formset:
                if form.has_changed():
                    instance = form.save(commit=False)
                    score_value = form.cleaned_data.get('exam_total_score')

                    # Skip saving empty or blank inputs
                    if score_value in (None, ''):
                        if instance.pk:
                            instances_to_delete.append(instance)
                        continue

                    # Enforce central max score
                    if score_value > central_max:
                        form.add_error(
                            'exam_total_score',
                            f"Score cannot exceed {central_max}."
                        )
                        continue

                    # Assign max_score before saving
                    instance.max_score = central_max
                    instances_to_save.append(instance)

            # Save valid scores
            for instance in instances_to_save:
                instance.save()

            # Delete empty/removed scores
            for instance in instances_to_delete:
                instance.delete()

            return redirect(
                'results:midterm_score_success',
                class_id=class_id,
                subject_id=subject_id,
                term_id=term_id
            )

        context = {
            'formset': formset,
            'assigned_class': assigned_class,
            'subject': subject,
            'term': term,
            'students': students.order_by('last_name'),
            'central_max': central_max,
            'exam_setting': exam_setting,  # <-- pass the object

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
        # AUTHORIZATION LOGIC
        # -----------------------------------------------------------
        is_admin = request.user.is_superuser or request.user.is_staff
        is_current_student = hasattr(request.user, 'student') and request.user.student.id == student_id
        is_assigned_form_teacher = False

        if hasattr(request.user, 'teacher') and student.form_teacher == request.user.teacher:
            is_assigned_form_teacher = True

        if not (is_admin or is_current_student or is_assigned_form_teacher):
            return redirect('results:student_midterm_list')
        # -----------------------------------------------------------

        # -----------------------------------------------------------
        # Get central max score for Midterm from ExamSetting
        # -----------------------------------------------------------
        exam_setting = get_object_or_404(
            ExamSetting,
            term=term,
            exam_type="Midterm"
        )
        central_max = exam_setting.max_score
        # -----------------------------------------------------------

        # Fetch student's midterm scores
        midterm_scores = MidTermScore.objects.filter(
            student=student,
            term=term,
            exam_total_score__isnull=False
        ).select_related('subject').order_by('subject__name')

        report_data = []
        total_scores_sum = 0

        for score in midterm_scores:
            # Class statistics for the subject
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
                'grade': mdterm_get_grade(score.exam_total_score, max_score=central_max),
                'remark': mdterm_get_subject_remark(score.exam_total_score, max_score=central_max),
                'class_high': stats['class_max'],
                'class_low': stats['class_min'],
                'class_avg': stats['class_avg'],
            })

            total_scores_sum += score.exam_total_score

        subjects_with_scores_count = len(report_data)
        overall_average = total_scores_sum / subjects_with_scores_count if subjects_with_scores_count > 0 else None
        overall_remark = mdterm_get_overall_remark(overall_average, max_score=central_max) if overall_average else "No scores recorded."

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
            'exam_setting': exam_setting,  # Pass exam_setting for template display
        }

        # PDF download option
        if 'download' in request.GET and request.GET['download'] == 'pdf':
            filename = f"{student.first_name}_{term.name}_MidTerm.pdf"
            pdf_response = render_to_pdf_xhtml2pdf(self.pdf_template_name, context)
            if pdf_response:
                pdf_response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return pdf_response

        return render(request, self.template_name, context)



# Mid Term List with filtering
class StudentMidTermListView(LoginRequiredMixin, View):
    template_name = 'results/student_midterm_list.html'

    def get(self, request):
        is_student = hasattr(request.user, 'student')
        is_teacher = hasattr(request.user, 'teacher')
        is_admin = request.user.is_staff or request.user.is_superuser

        if not (is_student or is_teacher or is_admin):
            messages.error(request, "Access denied.")
            return redirect('pages:portal-home')

        context = {}
        report_data = []

        # Get filter parameters from GET request
        selected_class_id = request.GET.get('class')
        selected_term_id = request.GET.get('term')

        # --- STUDENT VIEW ---
        if is_student:
            student = request.user.student
            context['current_user_type'] = 'student'
            context['student'] = student

            queryset = Term.objects.filter(midtermscore__student=student).distinct()
            if selected_term_id:
                queryset = queryset.filter(id=selected_term_id)

            for report in queryset:
                report_data.append({
                    'term_id': report.id,
                    'term_name': report.name,
                    'session_name': report.session.name,
                    'student_id': student.id,
                })

        # --- TEACHER & ADMIN VIEW ---
        elif is_admin or is_teacher:
            context['current_user_type'] = 'admin' if is_admin else 'teacher'

            # Teacher assigned class
            assigned_class = None
            if not is_admin:
                try:
                    assigned_class = request.user.teacher.form_class.get()
                except:
                    assigned_class = request.user.teacher.form_class.first()
                if not assigned_class:
                    messages.warning(request, "No assigned class found.")
                    context['available_reports'] = []
                    return render(request, self.template_name, context)
                context['assigned_class'] = assigned_class

            # Base Queryset
            scores_qs = MidTermScore.objects.all()

            # Filter by teacher's class
            if assigned_class:
                scores_qs = scores_qs.filter(student__current_class=assigned_class)

            # Filter by selected class (admin only)
            if is_admin and selected_class_id:
                scores_qs = scores_qs.filter(student__current_class__id=selected_class_id)

            # Filter by term
            if selected_term_id:
                scores_qs = scores_qs.filter(term__id=selected_term_id)

            # Unique student + term combinations
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

            # For filter dropdowns
            context['all_classes'] = Standard.objects.all()
            context['all_terms'] = Term.objects.all()

        context['available_reports'] = report_data
        context['selected_class_id'] = selected_class_id
        context['selected_term_id'] = selected_term_id

        return render(request, self.template_name, context)




class MidTermScoreSelectionView(LoginRequiredMixin, View):
    """
    Allows teachers to select from their assigned classes and subjects
    to enter mid-term scores.
    """
    template_name = 'results/midterm_score_selection.html'

    def get(self, request):
        user = request.user

        # 1. Authorization Check
        if not (hasattr(user, 'teacher') or user.is_staff):
            messages.error(request, "Access denied. You must be a teacher or administrator.")
            return redirect('pages:portal-home')

        # Staff/Admins see everything; Teachers see only their assignments
        if user.is_staff:
            available_classes = Standard.objects.all().order_by('name')
            available_subjects = Subject.objects.all().order_by('name')
        else:
            teacher = user.teacher
            # Get all classes assigned to this teacher
            available_classes = teacher.standards_assigned.all().order_by('name')
            # Get all subjects assigned to this teacher
            available_subjects = teacher.subjects_taught.all().order_by('name')

        # 2. Safety Check: Ensure they have assignments
        if not available_classes.exists() or not available_subjects.exists():
            messages.warning(request, "You do not have any classes or subjects assigned to you for score entry.")
            return redirect('pages:portal-home')

        # 3. Get the Current Term
        try:
            available_terms = [Term.objects.get(is_current=True)]
        except Term.DoesNotExist:
            messages.error(request, "No active academic term found. Please contact the administrator.")
            available_terms = []

        context = {
            'available_classes': available_classes,
            'available_subjects': available_subjects,
            'available_terms': available_terms,
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



# PARENT LOGIC FOR RESULTS
#parent midterm results access

class ParentMidTermReportView(LoginRequiredMixin, View):
    template_name = 'results/mid_term_report_card_detail.html'

    def get(self, request, student_id, term_id):
        student = get_object_or_404(Student, id=student_id)

        # Security check
        if not hasattr(request.user, 'parent') or student not in request.user.parent.children.all():
            raise PermissionDenied("Access denied.")

        term = get_object_or_404(Term, id=term_id)

        # Fetch all midterm scores for this student and term
        scores = MidTermScore.objects.select_related('subject').filter(
            student=student,
            term=term
        )

        school_identity = SchoolIdentity.objects.first()

        # Prepare report data with grading & class stats
        report_data = []
        total_sum = 0
        subject_count = 0

        for score in scores:
            exam_score = float(score.exam_total_score or 0)
            total_sum += exam_score
            subject_count += 1

            # Compute grade (simple example, adjust grading scale)
            if exam_score >= 70:
                grade = 'A'
            elif exam_score >= 60:
                grade = 'B'
            elif exam_score >= 50:
                grade = 'C'
            elif exam_score >= 40:
                grade = 'D'
            else:
                grade = 'F'

            # Compute class stats for this subject
            subject_scores = MidTermScore.objects.filter(
                term=term,
                subject=score.subject
            )

            class_high = subject_scores.aggregate(Max('exam_total_score'))['exam_total_score__max'] or 0
            class_low = subject_scores.aggregate(Min('exam_total_score'))['exam_total_score__min'] or 0
            class_avg = subject_scores.aggregate(Avg('exam_total_score'))['exam_total_score__avg'] or 0

            # Remarks based on score
            if exam_score >= 70:
                remark = 'Excellent'
            elif exam_score >= 60:
                remark = 'Very Good'
            elif exam_score >= 50:
                remark = 'Good'
            elif exam_score >= 40:
                remark = 'Fair'
            else:
                remark = 'Needs Improvement'

            report_data.append({
                'subject': score.subject.name,
                'total_score': exam_score,
                'grade': grade,
                'class_high': class_high,
                'class_low': class_low,
                'class_avg': class_avg,
                'remark': remark,
            })

        overall_average = (total_sum / subject_count) if subject_count else 0

        context = {
            'student': student,
            'term': term,
            'report_data': report_data,
            'overall_average': overall_average,
            'overall_remark': 'Satisfactory performance. Keep it up.',
            'school_identity': school_identity,
        }

        return render(request, self.template_name, context)


class ParentSessionReportView(LoginRequiredMixin, View):
    template_name = 'results/session_report_card_detail.html'

    def get(self, request, student_id, session_id, *args, **kwargs):
        # Fetch student
        student = get_object_or_404(Student, id=student_id)

        # Parent authorization check
        if not hasattr(request.user, 'parent') or student not in request.user.parent.children.all():
            raise PermissionDenied("Access denied: This student is not linked to your account.")

        # Fetch session
        session = get_object_or_404(Session, id=session_id)
        terms_in_session = session.terms.all().order_by('start_date')

        if not terms_in_session.exists():
            messages.warning(request, f"No terms defined for {session.name}.")
            return redirect(request.META.get('HTTP_REFERER', 'session_report_card_list'))

        # Aggregate scores per subject, counting only terms with data
        subject_cumulative_data = Score.objects.filter(
            student=student,
            term__in=terms_in_session
        ).values('subject__name', 'subject__id').annotate(
            cumulative_total_score=Sum('total_score'),
            active_term_count=Count('term', filter=Q(total_score__isnull=False))
        ).order_by('subject__name')

        report_data = []
        overall_effective_average_sum = 0
        subjects_counted_for_overall_average = 0

        for item in subject_cumulative_data:
            subject_id = item['subject__id']
            subject_name = item['subject__name']
            cumulative_score_raw = item['cumulative_total_score']
            active_term_count = item['active_term_count']

            # Individual term scores for table display
            term_scores_for_subject = {}
            for term in terms_in_session:
                try:
                    score_inst = Score.objects.get(student=student, subject__id=subject_id, term=term)
                    term_scores_for_subject[term.name] = score_inst.total_score if score_inst.total_score is not None else 'N/A'
                except Score.DoesNotExist:
                    term_scores_for_subject[term.name] = 'N/A'

            # Subject average based on active terms only
            effective_subject_average = None
            if cumulative_score_raw is not None and active_term_count > 0:
                effective_subject_average = cumulative_score_raw / active_term_count
                overall_effective_average_sum += effective_subject_average
                subjects_counted_for_overall_average += 1

            report_data.append({
                'subject': subject_name,
                'term_scores': term_scores_for_subject,
                'cumulative_total_score': f"{cumulative_score_raw:.2f}" if cumulative_score_raw is not None else 'N/A',
                'effective_subject_average': f"{effective_subject_average:.2f}" if effective_subject_average is not None else 'N/A',
                'grade': get_grade(effective_subject_average),
                'remark': get_subject_remark(effective_subject_average),
            })

        # Overall session average
        overall_session_average = None
        overall_remark = "No scores recorded for this session."
        if subjects_counted_for_overall_average > 0:
            overall_session_average = overall_effective_average_sum / subjects_counted_for_overall_average
            overall_remark = get_overall_remark(overall_session_average)

        # Motor/Behavioral aggregation
        motor_ability_scores = MotorAbilityScore.objects.filter(student=student, term__session=session)
        agg_motor = motor_ability_scores.aggregate(
            avg_honesty=Avg('honesty'), avg_politeness=Avg('politeness'),
            avg_neatness=Avg('neatness'), avg_cooperation=Avg('cooperation'),
            avg_obedience=Avg('obedience'), avg_attentiveness=Avg('attentiveness'),
            avg_punctuality=Avg('punctuality'), avg_perseverance=Avg('perseverance'),
            avg_emotional_stability=Avg('emotional_stability'), avg_attitude=Avg('attitude'),
            avg_leadership=Avg('leadership'), avg_physical_education=Avg('physical_education'),
            avg_games=Avg('games'), avg_musical=Avg('musical'),
            avg_handwriting=Avg('handwriting'), avg_reading=Avg('reading'),
            avg_verbal_fluency=Avg('verbal_fluency'), avg_handling_tools=Avg('handling_tools'),
        )
        processed_motor = {k: (round(min(v, 5)) if v is not None else 0) for k, v in agg_motor.items()}

        # Attendance
        attendance_records = Attendance.objects.filter(
            student=student,
            date__gte=session.start_date,
            date__lte=session.end_date
        )
        total_school_days = attendance_records.count()
        days_present = attendance_records.filter(present=True).count()
        days_absent = attendance_records.filter(present=False).count()

        # School info
        school_identity = SchoolIdentity.objects.first()
        next_session = Session.objects.filter(start_date__gt=session.end_date).order_by('start_date').first()

        context = {
            'student': student,
            'session': session,
            'terms_in_session': terms_in_session,
            'report_data': report_data,
            'overall_session_average': f"{overall_session_average:.2f}" if overall_session_average is not None else 'N/A',
            'overall_remark': overall_remark,
            'aggregated_motor_abilities': processed_motor,
            'school_identity': school_identity,
            'total_school_days': total_school_days,
            'days_present': days_present,
            'days_absent': days_absent,
            'next_session_start_date': next_session.start_date if next_session else None,
        }

        return render(request, self.template_name, context)


# Parent Termly Report Access    
class ParentTermlyReportView(LoginRequiredMixin, View):
    """Independent view for parents to view full termly report cards."""
    template_name = 'results/test_student_report_card_detail.html'

    def get(self, request, student_id, term_id):
        # 1. Get objects
        student = get_object_or_404(Student, id=student_id)
        term = get_object_or_404(Term, id=term_id)
        
        # 2. STRICT PARENT SECURITY CHECK
        if not hasattr(request.user, 'parent'):
            raise PermissionDenied("You do not have a parent profile.")
        
        if student not in request.user.parent.children.all():
            raise PermissionDenied("This student is not linked to your account.")

        # 3. DATA FETCHING (Same logic as student view but isolated)
        standard = student.current_class
        scores = Score.objects.filter(student=student, term=term).select_related('subject').order_by('subject__name')

        report_data = []
        total_scores_sum = 0
        subjects_with_scores_count = 0

        for score in scores:
            if score.total_score is not None:
                total_ca = (score.ca1 or 0) + (score.ca2 or 0) + (score.ca3 or 0)
                report_data.append({
                    'subject': score.subject.name,
                    'ca1': score.ca1 if score.ca1 is not None else 'N/A',
                    'ca2': score.ca2 if score.ca2 is not None else 'N/A',
                    'ca3': score.ca3 if score.ca3 is not None else 'N/A',
                    'total_ca': total_ca,
                    'exam_score': score.exam_score if score.exam_score is not None else 'N/A',
                    'total_score': score.total_score,
                    'grade': get_grade(score.total_score),
                    'remark': get_subject_remark(score.total_score),
                })
                total_scores_sum += score.total_score
                subjects_with_scores_count += 1

        # 4. AVERAGES & RANKING
        overall_average = total_scores_sum / subjects_with_scores_count if subjects_with_scores_count > 0 else None
        overall_remark = get_overall_remark(overall_average) if overall_average else "No scores recorded."
        
        student_rank, total_students = get_student_class_rank(student, standard, term)
        student_position_display = f"{student_rank} out of {total_students}" if student_rank != 'N/A' else 'N/A'

        # 5. ATTENDANCE
        student_attendance = Attendance.objects.filter(student=student, date__gte=term.start_date, date__lte=term.end_date)
        days_present = student_attendance.filter(present=True).count()
        
        school_identity = SchoolIdentity.objects.first()

        context = {
            'student': student,
            'term': term,
            'report_data': report_data,
            'overall_average': overall_average,
            'overall_remark': overall_remark,
            'student_position_display': student_position_display,
            'school_identity': school_identity,
            'days_present': days_present,
            'report_type': 'Full Termly Report',
        }
        
        return render(request, self.template_name, context)



# Result Broadsheet View

# 1. PAGE TO SELECT CLASS AND TERM
class BroadsheetSelectionView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'results/broadsheet_selection.html'

    def test_func(self):
        return self.request.user.is_staff

    def get(self, request):
        context = {
            'classes': Standard.objects.all().order_by('name'),
            'terms': Term.objects.all().order_by('-id'),
        }
        return render(request, self.template_name, context)

# 2. THE ACTUAL BROADSHEET GENERATOR
class ClassBroadsheetView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'results/class_broadsheet.html'

    def test_func(self):
        return self.request.user.is_staff

    def get(self, request, class_id, term_id):
        standard = get_object_or_404(Standard, id=class_id)
        term = get_object_or_404(Term, id=term_id)
        
        students = Student.objects.filter(current_class=standard).order_by('last_name')
        subject_ids = Score.objects.filter(student__current_class=standard, term=term).values_list('subject_id', flat=True).distinct()
        subjects = Subject.objects.filter(id__in=subject_ids).order_by('name')

        broadsheet_data = []
        for student in students:
            student_scores = {}
            row_total = 0
            count = 0
            scores = Score.objects.filter(student=student, term=term)
            
            for sub in subjects:
                score_obj = scores.filter(subject=sub).first()
                if score_obj:
                    total = score_obj.total_score or 0
                    student_scores[sub.id] = {
                        'ca': (score_obj.ca1 or 0) + (score_obj.ca2 or 0) + (score_obj.ca3 or 0),
                        'exam': score_obj.exam_score or 0,
                        'total': total
                    }
                    row_total += total
                    count += 1
                else:
                    student_scores[sub.id] = {'ca': 0, 'exam': 0, 'total': 0}

            broadsheet_data.append({
                'student': student,
                'scores': student_scores,
                'total_sum': row_total,
                'average': row_total / count if count > 0 else 0
            })

        broadsheet_data = sorted(broadsheet_data, key=lambda x: x['average'], reverse=True)

        if 'export' in request.GET:
            return self.export_csv(standard, term, subjects, broadsheet_data)

        return render(request, self.template_name, {
            'standard': standard, 'term': term, 'subjects': subjects, 'broadsheet_data': broadsheet_data
        })

    def export_csv(self, standard, term, subjects, broadsheet_data):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="Broadsheet_{standard.name}.csv"'
        writer = csv.writer(response)
        writer.writerow(['S/N', 'Name'] + [f"{s.name} (TOT)" for s in subjects] + ['Total', 'Avg', 'Rank'])
        for i, row in enumerate(broadsheet_data, 1):
            scores = [row['scores'][s.id]['total'] for s in subjects]
            writer.writerow([i, row['student'].get_full_name()] + scores + [row['total_sum'], round(row['average'], 2), i])
        return response
    


# Bulk Report Card View
class BulkReportCardPrintView(LoginRequiredMixin, AdminTeacherOrOwnerMixin, View):
    template_name = 'results/bulk_report_cards_print.html'

    def get(self, request, standard_id, term_id, *args, **kwargs):
        standard = get_object_or_404(Standard, id=standard_id)
        term = get_object_or_404(Term, id=term_id)
        students = Student.objects.filter(current_class=standard).order_by('last_name')
        
        school_identity = SchoolIdentity.objects.first()
        next_term = Term.objects.filter(start_date__gt=term.end_date).order_by('start_date').first()
        next_term_start_date = next_term.start_date if next_term else None
        total_students_in_class = students.count()

        # Class-wide Average Stats
        student_averages = []
        for stu in students:
            stu_scores = Score.objects.filter(student=stu, term=term)
            agg = stu_scores.aggregate(total=Sum('total_score'))
            total = agg.get('total')
            count = stu_scores.filter(total_score__isnull=False).count()
            if total is not None and count > 0:
                student_averages.append(total / count)

        class_avg = sum(student_averages) / len(student_averages) if student_averages else 0
        class_max_avg = max(student_averages) if student_averages else 0
        class_min_avg = min(student_averages) if student_averages else 0

        # Global Position Setting for the Class
        try:
            position_setting = ClassPositionSetting.objects.get(
                standard=standard, term=term, session=term.session
            )
            show_class_position = position_setting.show_class_position
        except:
            show_class_position = True

        all_reports = []

        for student in students:
            # Attendance
            student_attendance = Attendance.objects.filter(
                student=student, date__gte=term.start_date, date__lte=term.end_date
            )
            days_present = student_attendance.filter(present=True).count()
            days_absent = student_attendance.filter(present=False).count()
            total_school_days = Attendance.objects.filter(
                student__current_class=standard, date__gte=term.start_date, date__lte=term.end_date
            ).values('date').distinct().count()

            # Scores
            scores = Score.objects.filter(student=student, term=term).select_related('subject').order_by('subject__name')
            report_data = []
            total_scores_sum = 0
            subjects_count = 0
            
            for score in scores:
                if score.total_score is not None:
                    total_ca = (score.ca1 or 0) + (score.ca2 or 0) + (score.ca3 or 0)
                    class_scores = Score.objects.filter(subject=score.subject, term=term, student__current_class=standard, total_score__isnull=False)
                    stats = class_scores.aggregate(avg=Avg('total_score'), min=Min('total_score'), max=Max('total_score'))
                    
                    higher_scores = class_scores.filter(total_score__gt=score.total_score).count()
                    
                    report_data.append({
                        'subject': score.subject.name,
                        'ca1': score.ca1, 'ca2': score.ca2, 'ca3': score.ca3,
                        'total_ca': total_ca, 'exam_score': score.exam_score,
                        'total_score': score.total_score,
                        'grade': get_grade(score.total_score),
                        'remark': get_subject_remark(score.total_score),
                        'subject_avg': stats.get('avg') or 0,
                        'subject_min': stats.get('min') or 0,
                        'subject_max': stats.get('max') or 0,
                        'subject_position': higher_scores + 1,
                    })
                    total_scores_sum += score.total_score
                    subjects_count += 1

            overall_avg = total_scores_sum / subjects_count if subjects_count > 0 else 0
            rank, total_rank_count = get_student_class_rank(student, standard, term)
            
            # Comments & Psychomotor
            comments = ReportComments.objects.filter(student=student, standard=standard, term=term, session=term.session).first()
            motor = MotorAbilityScore.objects.filter(student=student, term=term).first()

            all_reports.append({
                'student': student,
                'report_data': report_data,
                'overall_average': overall_avg,
                'student_position_display': f"{rank} out of {total_rank_count}" if rank != 'N/A' else 'N/A',
                'days_present': days_present,
                'days_absent': days_absent,
                'teacher_comment': comments.teacher_comment if comments else None,
                'principal_comment': comments.principal_comment if comments else None,
                'motor_ability_score': motor,
                'total_marks_obtained': total_scores_sum,
                'subjects_with_scores_count': subjects_count,
            })

        context = {
            'standard': standard,
            'term': term,
            'all_reports': all_reports,
            'school_identity': school_identity,
            'class_avg': class_avg,
            'class_max_avg': class_max_avg,
            'class_min_avg': class_min_avg,
            'total_school_days': total_school_days,
            'next_term_start_date': next_term_start_date,
            'total_students_in_class': total_students_in_class,
            'show_class_position': show_class_position,
        }
        return render(request, self.template_name, context)
    
    

# Bulk Print Selection Page View    
class BulkReportCardSelectorView(LoginRequiredMixin, AdminTeacherOrOwnerMixin, View):
    template_name = 'results/bulk_report_card_selector.html'

    def get(self, request, *args, **kwargs):
        standards = Standard.objects.all().order_by('name')
        terms = Term.objects.all().order_by('-start_date')
        
        context = {
            'standards': standards,
            'terms': terms,
        }
        return render(request, self.template_name, context)