from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings



# Create your views here.

def cbt_home(request):
    return render(request, 'cbt/cbt_home.html')

def cbt_order(request):
    return render(request, 'cbt/cbt_order_form.html')

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