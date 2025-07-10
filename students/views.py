from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db.models import Count
#converting html to pdf
from django.http import HttpResponse, HttpResponseRedirect
from django.template.loader import get_template
# from xhtml2pdf import pisa
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from students.models import Student, Hostel
from staff.models import Teacher
from students.forms import StudentUpdateForm
from users.forms import UserRegisterForm
from curriculum.models import SchoolIdentity
from curriculum.models import Standard
# from results.models import ResultSheet
import io
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from django.http import FileResponse
import csv
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.template.loader import get_template
from xhtml2pdf import pisa

from django.db import IntegrityError, transaction
from datetime import date


#Displays all students
def student_list(request):
    all_students = Student.objects.all().order_by('-date_admitted')
    my_students = Student.objects.filter(form_teacher__user=request.user).order_by('user')

    
    context ={
        'all_students':all_students,
        'my_students':my_students
    }
    if request.user.is_superuser or request.user.is_staff:
        return render(request, 'students/student_list.html', context) 
    elif my_students:
        return render(request, 'students/my_student_list.html', context) 
    else:
         return render(request, 'pages/portal_home.html')
    
    
 # for boarding students   
def student_boarder_list(request):
    boarder_student = Student.objects.filter(student_type='boarder').order_by('-date_admitted')
    # boarder_student = Student.objects.all().order_by('-date_admitted')

    context ={
        'boarder_student':boarder_student
    }
    if request.user.is_superuser or request.user.is_staff:
        return render(request, 'students/student_boarder_list.html', context)
    else:
         return render(request, 'pages/portal_home.html')
    

 # Hostel List
def hostel_list(request):
    hostel_list = Hostel.objects.all()
    # boarder_student = Student.objects.all().order_by('-date_admitted')

    context ={
        'hostel_list': hostel_list,
    }         
    
    return render(request, 'students/hostel_list.html', context)
    


# Student Search Query App
def student_search_list(request):
    student = Student.objects.all()
    
     # PAGINATOR METHOD
    page = request.GET.get('page', 1)
    paginator = Paginator(student, 30)
    try:
        student = paginator.page(page)
    except PageNotAnInteger:
        student = paginator.page(1)
    except EmptyPage:
        student = paginator.page(paginator.num_pages)

    return render(request, 'students/search_student_list.html', {'student': student })

# Define function to search student
def search(request):
    results = []

    if request.method == "GET":
        query = request.GET.get('search')

        if query == '':
            query = 'None'

        results = Student.objects.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(standard__name__icontains=query) | Q(guardian_name__icontains=query) | Q(user__username__icontains=query) | Q(USN__icontains=query))
        # results = Student.objects.filter(Q(full_name__icontains=query))
        
    return render(request, 'students/search.html', {'query': query, 'results': results})

#count students in each class
def student_in_class(request):
    students = Student.objects.all()
    student_no = Student.objects.filter().order_by('standard').values('standard__name').annotate(count=Count('standard__name'))

    try:
        num_inclass = Student.objects.filter(standard__name = request.user.student.standard).count()
    except Student.DoesNotExist:
        num_inclass = Student.objects.filter()

    return render(request, 'students/student_no_in_class.html', {'students': students, 'student_no':student_no, 'num_inclass':num_inclass})


class StudentDetailView(DetailView):
    template_name = 'students/student_detail.html'
    queryset = Student.objects.all()

    def get_object(self):
        id_ = self.kwargs.get("USN")
        return get_object_or_404(Student, USN=id_)
    
# Specific to the login detail
class StudentSelfDetailView(LoginRequiredMixin, DetailView):
    template_name = 'students/student_self_detail.html'
    model = Student

    def get_object(self, queryset=None):
           if queryset is None:
               queryset = self.get_queryset()
           return queryset.filter(user=self.request.user).first()


class StudentUpdateView(LoginRequiredMixin, UpdateView):
    form_class = StudentUpdateForm
    template_name = 'students/student_update_form.html'
    # queryset = StudentDetail.objects.all()


    def get_object(self):
        id_ = self.kwargs.get("USN")
        return get_object_or_404(Student, USN=id_)

    def form_valid(self, form):
        print(form.cleaned_data)
        return super().form_valid(form)

     

class StudentDeleteView(LoginRequiredMixin, DeleteView):
    template_name = 'students/student_delete.html'
    success_url = reverse_lazy('students:student-list')
    
    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Student, id=id_)
    

#generate IDCARD PDF
@login_required
def id_render_pdf_view(request, *args, **kwargs):    

    pk = kwargs.get('pk')
    
    student_detail = get_object_or_404(Student, pk=pk)
    school_identity = SchoolIdentity.objects.get()
    template_path = 'students/student_id_pdf.html'
    # template_path = 'results/result_sheet.html'
    context = {'student_detail': student_detail, 'school_identity':school_identity }
    # Create a Django response object, and specify content_type as pdf
    response = HttpResponse(content_type='application/pdf')
    # if you want to download
    # response['Content-Disposition'] = 'attachment; filename="report.pdf"'
    # if you just want to display
    response['Content-Disposition'] = 'filename="id_card.pdf"'

    # find the template and render it.
    template = get_template(template_path)
    html = template.render(context)

    # create a pdf
    pisa_status = pisa.CreatePDF(
    html, dest=response)
    # if error then show some funy view
    if pisa_status.err:
        return HttpResponse('We had some errors <pre>' + html + '</pre>')
    return response


class MyTeacherDetailView(DetailView):
    template_name = 'student/my_teacher_detail.html'
    context_object_name = 'teacher'
    queryset = Teacher.objects.all()

    def get_object(self):
        id_ = self.kwargs.get("id")
        return get_object_or_404(Teacher, id=id_)
    
# My Class Mates

@login_required
def my_classmates_view(request):
    try:
        # Get the logged-in user's student profile
        student = request.user.student
        
        # Get the classroom the student belongs to
        standard = student.standard

        if standard:
            # Get all other students in the same classroom, excluding the current student
            classmates = Student.objects.filter(standard=standard).exclude(user=request.user)
        else:
            classmates = [] # No classroom assigned
            
        context = {
            'student': student,
            'standard': standard,
            'classmates': classmates,
        }
        return render(request, 'students/my_classmates.html', context)
    except Student.DoesNotExist:
        # Handle cases where the logged-in user doesn't have a student profile
        return render(request, 'students/no_student_profile.html', {})
    except Exception as e:
        # Generic error handling
        return render(request, 'students/error.html', {'error_message': str(e)})

