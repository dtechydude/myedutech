# payments/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.contrib import messages
from django.db import transaction
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.db.models import Sum, F,  ExpressionWrapper, DecimalField, Q, Max, Min, OuterRef, Subquery
from .models import Payment, Receipt, PaymentCategory, StudentAccountLedger, CategoryFee, StudentFee
from curriculum.models import Term, Session
from .forms import PaymentForm, ParentPaymentForm
from students.models import Student, Parent
from datetime import datetime, timedelta
from decimal import Decimal
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse, HttpResponse
from django.template.loader import get_template
from curriculum.models import SchoolIdentity
import csv # For CSV export
from io import StringIO # For CSV export
# from .utils import get_debtors_data, get_total_payments_data, render_to_pdf # Import render_to_pdf

# Import the refactored utility functions
from .utils import get_debtors_data, get_total_payments_data, render_to_pdf

# For PDF generation (using django-weasyprint which wraps xhtml2pdf/wkhtmltopdf)
from django.conf import settings # To access STATIC_URL for PDF images
# Add:
from xhtml2pdf import pisa # Import the pisa library
# You'll also need these for the PDF generation utility
from django.template.context_processors import static # for accessing STATIC_URL in render_to_pdf



# Helper function to check if user is staff (adjust as per your User model setup)
def is_staff(user):
    return user.is_authenticated and user.is_staff

@login_required
def make_payment(request):
    """
    View for staff or students to record a new payment.
    Students can only make payments for themselves.
    """
    is_student_user = hasattr(request.user, 'student')
    student_instance = request.user.student if is_student_user else None

    if request.method == 'POST':
        form = PaymentForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    payment = form.save(commit=False)
                    current_student = payment.student

                    if is_student_user:
                        # CRITICAL FIX: The form has cleaned_data['category_fee']
                        # which is an object. Use its attributes.
                        selected_category_fee = form.cleaned_data['category_fee']
                        payment.original_amount = selected_category_fee.amount_due
                        payment.term = selected_category_fee.term
                        payment.session = selected_category_fee.session
                        payment.payment_category = selected_category_fee.payment_category
                        payment.discount_amount = Decimal('0.00')
                        payment.discount_percentage = Decimal('0.00')
                    else:  # Staff user
                        # Logic to find a matching CategoryFee is robust. Keep it.
                        selected_category_fee = CategoryFee.objects.filter(
                            payment_category=payment.payment_category,
                            term=payment.term,
                            session=payment.session
                        ).first()
                        if payment.original_amount is None:
                            payment.original_amount = selected_category_fee.amount_due if selected_category_fee else Decimal('0.00')

                    # Calculate balance before payment
                    total_paid_for_this_fee_before = Payment.objects.filter(
                        student=current_student,
                        payment_category=payment.payment_category,
                        term=payment.term,
                        session=payment.session,
                        status='completed'
                    ).exclude(pk=payment.pk).aggregate(Sum('amount_received'))['amount_received__sum'] or Decimal('0.00')

                    payment.balance_before_payment = payment.original_amount - total_paid_for_this_fee_before
                    payment.balance_before_payment = max(Decimal('0.00'), payment.balance_before_payment)

                    # Set the recorded_by field correctly
                    payment.recorded_by = request.user if request.user.is_staff else None
                    payment.status = 'completed'
                    
                    payment.save()

                    # Calculate balance after payment and update
                    payment.balance_after_payment = payment.balance_before_payment - payment.amount_received
                    payment.balance_after_payment = max(Decimal('0.00'), payment.balance_after_payment)
                    payment.save(update_fields=['balance_after_payment'])

                    receipt = Receipt.objects.create(
                        payment=payment,
                        # The `generated_by` user for a student payment should be the student's user.
                        # This ensures receipts are linked to the user who made the payment.
                        generated_by=request.user 
                    )
                    messages.success(request, f"Payment of N{payment.amount_received} recorded successfully for {payment.student.first_name}. Receipt #{receipt.receipt_number} generated.")

                    # Use the correct URL name based on your urls.py file
                    return redirect('payments:receipt', receipt_id=receipt.id)
            
            except Exception as e:
                messages.error(request, f"An unexpected error occurred while recording payment. Please try again or contact support.")
                # You should log the full traceback for debugging
                import logging
                logger = logging.getLogger(__name__)
                logger.exception("Error recording payment:")
                context = {'form': form, 'title': 'Record New Payment'}
                return render(request, 'payments/test1_make_payment.html', context)
        else:
            messages.error(request, "Please correct the errors in the form.")
            context = {'form': form, 'title': 'Record New Payment'}
            return render(request, 'payments/test1_make_payment.html', context)
    else:
        form = PaymentForm(user=request.user)

    context = {
        'form': form,
        'title': 'Record New Payment'
    }
    return render(request, 'payments/test1_make_payment.html', context)



@login_required
def payment_history(request):
    """
    Renders the payment history page with filtering and pagination.
    """
    is_staff_user = request.user.is_staff

    # Get filter and pagination parameters
    student_search_query = request.GET.get('student_search', '').strip()
    selected_term_id = request.GET.get('term')
    selected_session_id = request.GET.get('session')
    selected_category_id = request.GET.get('category')
    selected_is_installment = request.GET.get('is_installment')
    page_number = request.GET.get('page') # Get the page number from the URL

    # Start with a base queryset for payments, filtering by 'completed' status
    payments_queryset = Payment.objects.filter(status='completed').select_related(
        'student__user',
        'payment_category',
        'term',
        'session',
        'recorded_by'
    ).order_by('-payment_date')
    
    # Apply filters based on request parameters
    if not is_staff_user:
        payments_queryset = payments_queryset.filter(student=request.user.student)
    else:
        if student_search_query:
            payments_queryset = payments_queryset.filter(
                Q(student__user__first_name__icontains=student_search_query) |
                Q(student__user__last_name__icontains=student_search_query) |
                Q(student__USN__icontains=student_search_query)
            )

    if selected_term_id:
        payments_queryset = payments_queryset.filter(term__id=selected_term_id)
    if selected_session_id:
        payments_queryset = payments_queryset.filter(session__id=selected_session_id)
    if selected_category_id:
        payments_queryset = payments_queryset.filter(payment_category__id=selected_category_id)
    if selected_is_installment:
        is_installment_bool = selected_is_installment.lower() == 'true'
        payments_queryset = payments_queryset.filter(is_installment=is_installment_bool)

    # Paginate the payments queryset
    paginator = Paginator(payments_queryset, 20) # Show 20 payments per page
    page_obj = paginator.get_page(page_number)
    payments = page_obj # Use the paginated object in the context

    # Aggregate data for the combined summary
    combined_payments_data = payments_queryset.values(
        'student', 
        'payment_category', 
        'term', 
        'session'
    ).annotate(
        total_amount_received=Sum('amount_received'),
        total_discount_amount=Sum('discount_amount')
    )

    # Retrieve related objects for combined payments
    student_ids = [item['student'] for item in combined_payments_data if item['student']]
    category_ids = [item['payment_category'] for item in combined_payments_data if item['payment_category']]
    term_ids = [item['term'] for item in combined_payments_data if item['term']]
    session_ids = [item['session'] for item in combined_payments_data if item['session']]

    students = {s.pk: s for s in Student.objects.filter(pk__in=student_ids).select_related('user')}
    payment_categories = {c.pk: c for c in PaymentCategory.objects.filter(pk__in=category_ids)}
    terms = {t.pk: t for t in Term.objects.filter(pk__in=term_ids)}
    sessions = {s.pk: s for s in Session.objects.filter(pk__in=session_ids)}

    # Attach the full objects and calculate balances
    for item in combined_payments_data:
        item['student_obj'] = students.get(item['student'])
        item['payment_category_obj'] = payment_categories.get(item['payment_category'])
        item['term_obj'] = terms.get(item['term'])
        item['session_obj'] = sessions.get(item['session'])
        
        try:
            student_fee = StudentFee.objects.get(
                student=item['student_obj'],
                term=item['term_obj'],
                session=item['session_obj'],
                category_fee__payment_category=item['payment_category_obj']
            )
            item['total_original_amount'] = student_fee.amount_due
        except StudentFee.DoesNotExist:
            item['total_original_amount'] = Decimal('0.00')

        item['balance'] = max(item['total_original_amount'] - item['total_amount_received'], Decimal('0.00'))

    # Build query string for pagination links to preserve filters
    query_string = request.GET.copy()
    if 'page' in query_string:
        del query_string['page']
    
    context = {
        'payments': payments, # Use the paginated object here
        'page_obj': page_obj, # Pass the paginator object
        'combined_payments': combined_payments_data,
        'is_staff_user': is_staff_user,
        'terms': Term.objects.all(),
        'sessions': Session.objects.all(),
        'categories': PaymentCategory.objects.all(),
        'selected_term_id': selected_term_id,
        'selected_session_id': selected_session_id,
        'selected_category_id': selected_category_id,
        'selected_is_installment': selected_is_installment,
        'student_search_query': student_search_query,
        'query_string': query_string.urlencode(), # URL-encoded query string
        'title': 'Payment History'
    }

    return render(request, 'payments/test1_payment_history.html', context)

# Olde receipt logic without parent permission
# @login_required
# def view_receipt(request, receipt_id):
#     """
#     View to display a specific receipt.
#     """
#     receipt = get_object_or_404(
#         Receipt.objects.select_related(
#             'payment__student', 'payment__term', 'payment__session',
#             'payment__payment_category', 'generated_by'
#         ),
#         id=receipt_id
#     )

#     if not request.user.is_staff and (not hasattr(receipt.payment.student, 'user') or request.user != receipt.payment.student.user):
#         messages.warning(request, "You are not authorized to view this receipt.")
#         return redirect('payments:payment_history') # Ensure correct redirect name
#       # ADDITION START
#     try:
#         school_identity = SchoolIdentity.objects.first()
#     except SchoolIdentity.DoesNotExist:
#         school_identity = None
#         # ADDITION END
#     context = {
#         'receipt': receipt,
#         'title': f'Receipt #{receipt.receipt_number}',
#         'school_identity': school_identity
#     }
#     return render(request, 'payments/receipt_detail.html', context)

# new receipt logic with parent, student and staff permission
@login_required
def view_receipt(request, receipt_id):
    """
    View to display a specific receipt, with proper authorization for staff, parents, and students.
    """
    receipt = get_object_or_404(
        Receipt.objects.select_related(
            'payment__student', 'payment__term', 'payment__session',
            'payment__payment_category', 'generated_by'
        ),
        id=receipt_id
    )

    # Authorization logic
    authorized = False
    if request.user.is_staff:
        # Staff can view any receipt.
        authorized = True
    elif hasattr(receipt.payment.student, 'parent'):
        try:
            parent = Parent.objects.get(user=request.user)
            # Check if the payment's student is a child of the logged-in parent.
            if receipt.payment.student.parent == parent:
                authorized = True
        except Parent.DoesNotExist:
            pass
    
    # Check if the user is the student associated with the receipt.
    # This assumes your Student model has a ForeignKey or OneToOneField to a User model.
    if hasattr(receipt.payment.student, 'user') and request.user == receipt.payment.student.user:
        authorized = True

    if not authorized:
        messages.warning(request, "You are not authorized to view this receipt.")
        return redirect('payments:payment_history')

    # Fetch school identity for the receipt.
    try:
        school_identity = SchoolIdentity.objects.first()
    except SchoolIdentity.DoesNotExist:
        school_identity = None

    context = {
        'receipt': receipt,
        'title': f'Receipt #{receipt.receipt_number}',
        'school_identity': school_identity
    }
    return render(request, 'payments/receipt_detail.html', context)





# --- Modified View: PDF for Receipt ---
@login_required
def receipt_pdf(request, receipt_id):
    receipt = get_object_or_404(
        Receipt.objects.select_related(
            'payment__student', 'payment__term', 'payment__session',
            'payment__payment_category', 'generated_by'
        ),
        id=receipt_id
    )

    if not request.user.is_staff and (not hasattr(receipt.payment.student, 'user') or request.user != receipt.payment.student.user):
        messages.warning(request, "You are not authorized to view this receipt.")
        return redirect('payments:payment_history')

    context = {
        'receipt': receipt,
        'title': f'Receipt #{receipt.receipt_number}',
        # 'STATIC_URL': settings.STATIC_URL, # No longer needed to pass explicitly if link_callback handles it
        'logo_path': os.path.join(settings.STATIC_URL, 'path/to/your/school_logo.png') # Use os.path.join for clarity
    }

    template_path = 'payments/receipt_pdf_template.html'
    pdf = render_to_pdf(template_path, context)
    if pdf:
        response = pdf
        response['Content-Disposition'] = f'attachment; filename="receipt_{receipt.receipt_number}.pdf"'
        return response
    
    messages.error(request, "Could not generate PDF for the receipt.")
    return redirect('payments:view_receipt', receipt_id=receipt.id) # Redirect back if PDF generation fails


# # CURRENT WORKING BUT INCREASING THE TOTAL BALANCE INSTEAD OF REDUCING IT
# @login_required
# @user_passes_test(is_staff)
# def debtors_report(request):
#     """
#     Generates a report of students who currently owe money (have a positive balance in the ledger).
#     Allows filtering by term and session.
#     """
#     term_id = request.GET.get('term')
#     session_id = request.GET.get('session')

#     # Use the refactored helper function
#     debtors = get_debtors_data(term_id, session_id)

#     terms = Term.objects.all().order_by('-start_date')
#     sessions = Session.objects.all().order_by('-start_date')

#     context = {
#         'debtors': debtors,
#         'terms': terms,
#         'sessions': sessions,
#         'selected_term_id': term_id,
#         'selected_session_id': session_id,
#         'title': 'Debtors Report'
#     }
#     return render(request, 'payments/test_debtors_report.html', context)


# A simple helper function to check if the user is a staff member.
# def is_staff(user):
#     return user.is_staff

# def get_debtors_data(term_id, session_id, category_id):
#     """
#     Calculates and returns a list of debtors with outstanding balances
#     broken down by payment category, with filtering for category.
#     """
#     debtors_list = []
    
#     student_fees = StudentFee.objects.all()
#     if term_id:
#         student_fees = student_fees.filter(term__id=term_id)
#     if session_id:
#         student_fees = student_fees.filter(session__id=session_id)
#     if category_id:
#         student_fees = student_fees.filter(category_fee__payment_category__id=category_id)  # Filter by category

#     payments = Payment.objects.all()
#     if term_id:
#         payments = payments.filter(term__id=term_id)
#     if session_id:
#         payments = payments.filter(session__id=session_id)
#     if category_id:
#         payments = payments.filter(payment_category__id=category_id)  # Filter payments by category
        
#     student_payments_by_category = payments.values(
#         'student',
#         'payment_category'
#     ).annotate(
#         total_paid=Sum('amount_received')
#     )
    
#     payments_dict = {
#         (p['student'], p['payment_category']): p['total_paid']
#         for p in student_payments_by_category
#     }

#     for student_fee in student_fees:
#         student = student_fee.student
#         term = student_fee.term
#         session = student_fee.session
#         category = student_fee.category_fee.payment_category
        
#         total_fees = student_fee.amount_due
        
#         total_payments = payments_dict.get((student.id, category.id), 0)
        
#         outstanding_balance = total_fees - total_payments
        
#         if outstanding_balance > 0:
#             debtors_list.append({
#                 'student': student,
#                 'term': term,
#                 'session': session,
#                 'category_name': category.name,
#                 'total_fees': total_fees,
#                 'total_payments': total_payments,
#                 'outstanding_balance': outstanding_balance
#             })

#     return debtors_list


# payments/views.py
@login_required
@permission_required('payments.view_studentaccountledger', raise_exception=True)
def debtors_report(request):
    """
    Renders the debtors report page and handles filtering.
    """
    
    term_id = request.GET.get('term', '')
    session_id = request.GET.get('session', '')
    category_id = request.GET.get('category', '')

    # Call the utility function to get the data
    debtors_list = get_debtors_data(term_id, session_id, category_id)

    # --- Paginator logic is now for a list, which is less efficient but necessary ---
    paginator = Paginator(debtors_list, 25) 
    page_number = request.GET.get('page', 1)
    try:
        debtors = paginator.page(page_number)
    except PageNotAnInteger:
        debtors = paginator.page(1)
    except EmptyPage:
        debtors = paginator.page(paginator.num_pages)
        
    query_string = request.GET.copy()
    if 'page' in query_string:
        del query_string['page']
    query_string = query_string.urlencode()
    # --- Paginator Logic Ends Here ---
    
    sessions = Session.objects.all().order_by('-start_date')
    terms = Term.objects.all().order_by('name')
    categories = PaymentCategory.objects.all().order_by('name')

    context = {
        'title': 'Debtors Report',
        'debtors': debtors,
        'sessions': sessions,
        'terms': terms,
        'categories': categories,
        'selected_session': int(session_id) if session_id else None,
        'selected_term': int(term_id) if term_id else None,
        'selected_category': int(category_id) if category_id else None,
        'query_string': query_string,
    }

    return render(request, 'payments/test_debtors_report.html', context)


# A new view function to generate student fees (you can make this a management command)
def generate_student_fees(request):
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        term_id = request.POST.get('term_id')

        try:
            term = Term.objects.get(id=term_id)
            session = Session.objects.get(id=session_id)
        except (Term.DoesNotExist, Session.DoesNotExist):
            messages.error(request, "Invalid term or session selected.")
            return redirect('payments:generate_student_fees')

        fees_generated_count = 0
        classes_without_fees = set() # Use a set to store unique class names
        
        all_students = Student.objects.all().select_related('current_class') 

        for student in all_students:
            relevant_category_fees = CategoryFee.objects.filter(
                student_class=student.current_class,
                term=term,
                session=session
            )

            if not relevant_category_fees.exists():
                classes_without_fees.add(student.current_class.name) # Add class name to the set
                continue 

            for cat_fee in relevant_category_fees:
                student_fee, created = StudentFee.objects.update_or_create(
                    student=student,
                    category_fee=cat_fee,
                    term=term,
                    session=session,
                    defaults={'amount_due': cat_fee.amount_due}
                )
                if created:
                    fees_generated_count += 1
        
        # Display a single, consolidated message for each class that had no fees
        for class_name in classes_without_fees:
            messages.warning(request, f"No Category Fees defined for class '{class_name}' in {term.name}, {session.name}.")

        # Display the success message for fees generated
        messages.success(request, f"{fees_generated_count} student fee records have been successfully generated or updated!")

        return redirect('payments:debtors_report')

    else: # GET request
        sessions = Session.objects.all().order_by('-start_date')
        terms = Term.objects.all().order_by('-start_date')
        context = {
            'sessions': sessions,
            'terms': terms,
        }
        return render(request, 'payments/generate_fees.html', context)

# --- New View: PDF for Debtors Report ---
@login_required
@user_passes_test(is_staff)
def debtors_report_pdf(request):
    term_id = request.GET.get('term')
    session_id = request.GET.get('session')

    debtors = get_debtors_data(term_id, session_id)

    context = {
        'debtors': debtors,
        'selected_term': Term.objects.get(id=term_id) if term_id else 'All',
        'selected_session': Session.objects.get(id=session_id) if session_id else 'All',
        'report_date': datetime.now(),
        'STATIC_URL': settings.STATIC_URL, # Pass STATIC_URL
        'logo_path': 'path/to/your/school_logo.png' # Update this for your logo
    }

    template_path = 'payments/debtors_report_pdf_template.html'
    html_string = get_template(template_path).render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="debtors_report.pdf"'
    
    HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf(response, stylesheets=[
        CSS(string='@page { size: A4 landscape; margin: 2cm; }') # Landscape for more columns
    ])
    return response

# # --- New View: CSV for Debtors Report ---
# @login_required
# @user_passes_test(is_staff)
# def debtors_report_csv(request):
#     # --- ADD THESE TWO LINES ---
#     term_id = request.GET.get('term')
#     session_id = request.GET.get('session')
#     # ---------------------------

#     debtors = get_debtors_data(term_id, session_id)

#     response = HttpResponse(content_type='text/csv')
#     response['Content-Disposition'] = 'attachment; filename="debtors_report.csv"'

#     writer = csv.writer(response)
#     writer.writerow(['Student Name', 'Class', 'Total Amount Due', 'Amount Paid', 'Balance'])

#     for debtor in debtors:
#         writer.writerow([
#             debtor['student_name'],
#             debtor['student_class'],
#             debtor['total_amount_due'],
#             debtor['amount_paid'],
#             debtor['balance']
#         ])
#     return response

@login_required
@permission_required('payments.view_studentaccountledger', raise_exception=True)
def debtors_report_csv(request):
    """
    Generates a CSV report of debtors based on outstanding balances.
    """
    term_id = request.GET.get('term')
    session_id = request.GET.get('session')
    category_id = request.GET.get('category')
    
    # The get_debtors_data function returns a list of dictionaries
    debtors = get_debtors_data(term_id, session_id, category_id)

    # ❗ This is the critical line to prevent the error
    if not debtors:
        return HttpResponse("No debtors found for the selected criteria.", content_type="text/plain", status=200)

    # The rest of the code only executes if debtors is not empty
    response = HttpResponse(content_type='text/csv')
    
    filename = "debtors_report"
    if term_id:
        filename += f"_term_{term_id}"
    if session_id:
        filename += f"_session_{session_id}"
    if category_id:
        filename += f"_category_{category_id}"
    filename += ".csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    writer.writerow(['Student Name', 'Class', 'Term', 'Session', 'Balance'])

    for debtor in debtors:
        writer.writerow([
            debtor['student_name'],
            debtor['student_class'],
            debtor['term_name'],
            debtor['session_name'],
            debtor['balance'],
        ])

    return response


@login_required
def payment_chart_list(request):
    # Retrieve the current active session
    try:
        current_session = Session.objects.get(is_current=True)
    except Session.DoesNotExist:
        current_session = None

    payment_chart_list = []
    
    if current_session:
        # Check if the user is a staff member or has a Teacher profile
        if request.user.is_staff or hasattr(request.user, 'teacher'):
            # Staff and teachers can see all payment fees for the current session
            payment_chart_list = CategoryFee.objects.filter(session=current_session)
        else:
            # Students can only see fees for their current class
            # Get the student instance linked to the user
            try:
                student = request.user.student
                student_class = student.current_class 
                
                if student_class:
                    # Filter fees based on the student's class and the current session
                    # Using the correct field name: 'student_class'
                    payment_chart_list = CategoryFee.objects.filter(
                        session=current_session,
                        student_class=student_class
                    )
                
            except AttributeError:
                # Handles cases where the user is not a student
                payment_chart_list = []

    context = {
        'payment_chart_list': payment_chart_list,
        'title': 'Fee Structure',
    }
    return render(request, 'payments/fees_table.html', context)

# Old Payment Chart List
@login_required
def archive_payment_chart_list(request):
    """
    Displays payment charts for all sessions that are not currently active.
    """
    # Use a direct lookup across the ForeignKey to filter by the session's 'is_current' status
    archive_payment_chart_list = CategoryFee.objects.filter(session__is_current=False).order_by('session__name', 'term__name')

    context = {
        'archive_payment_chart_list': archive_payment_chart_list,
        'title': 'Archived Fees Chart'
    }
    return render(request, 'payments/archived_fees_table.html', context)

@login_required
def get_category_fee_details(request):
    category_fee_id = request.GET.get('category_fee_id')
    if category_fee_id:
        try:
            category_fee = CategoryFee.objects.get(id=category_fee_id)
            
            # Get the logged-in student
            student = None
            if hasattr(request.user, 'student'):
                student = request.user.student
            
            total_paid_for_this_fee = Decimal('0.00')
            if student:
                # Sum all payments made by this student for this specific category, term, and session
                payments_for_fee = Payment.objects.filter(
                    student=student,
                    payment_category=category_fee.payment_category,
                    term=category_fee.term,
                    session=category_fee.session,
                    status='completed' # Only count completed payments
                ).aggregate(Sum('amount_received'))['amount_received__sum']
                
                if payments_for_fee:
                    total_paid_for_this_fee = payments_for_fee

            # Calculate remaining balance
            balance_remaining = category_fee.amount_due - total_paid_for_this_fee
            # Ensure balance_remaining doesn't go below zero if overpaid
            balance_remaining = max(Decimal('0.00'), balance_remaining)

            data = {
                'amount_due': str(category_fee.amount_due),
                'fee_name': category_fee.fee_name,
                'term_name': category_fee.term.name,
                'session_name': category_fee.session.name,
                'payment_category_name': category_fee.payment_category.name,
                'balance_remaining': str(balance_remaining), # New field
                'total_paid_for_this_fee': str(total_paid_for_this_fee), # New field
            }
            return JsonResponse(data)
        except CategoryFee.DoesNotExist:
            return JsonResponse({'error': 'Category Fee not found'}, status=404)
    return JsonResponse({'error': 'Invalid request'}, status=400)


# --- NEW: Total Payments Report Views ---
@login_required
@user_passes_test(is_staff)
def total_payments_report(request):
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    term_id = request.GET.get('term')
    session_id = request.GET.get('session')
    student_id = request.GET.get('student')

    report_data = get_total_payments_data(start_date_str, end_date_str, term_id, session_id, student_id)

    terms = Term.objects.all()
    sessions = Session.objects.all()
    students = Student.objects.select_related('user').all().order_by('user__first_name', 'user__last_name')

    context = {
        'total_amount_received': report_data['total_amount_received'],
        'total_original_amount': report_data['total_original_amount'],
        'total_discount_given': report_data['total_discount_given'],
        'payment_breakdown': report_data['payment_breakdown'],
        'selected_start_date': start_date_str,
        'selected_end_date': end_date_str,
        'selected_term': Term.objects.get(id=term_id) if term_id else None,
        'selected_session': Session.objects.get(id=session_id) if session_id else None,
        'selected_student': Student.objects.get(id=student_id) if student_id else None,
        'report_date': datetime.now(),
        'terms': terms,
        'sessions': sessions,
        'students': students,
    }
    return render(request, 'payments/total_payments_report.html', context)


@login_required
@user_passes_test(is_staff)
def total_payments_report_pdf(request):
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    term_id = request.GET.get('term')
    session_id = request.GET.get('session')
    student_id = request.GET.get('student')

    report_data = get_total_payments_data(start_date_str, end_date_str, term_id, session_id, student_id)

    context = {
        'total_amount_received': report_data['total_amount_received'],
        'total_original_amount': report_data['total_original_amount'],
        'total_discount_given': report_data['total_discount_given'],
        'payment_breakdown': report_data['payment_breakdown'],
        'selected_start_date': start_date_str,
        'selected_end_date': end_date_str,
        'selected_term': Term.objects.get(id=term_id) if term_id else 'All',
        'selected_session': Session.objects.get(id=session_id) if session_id else 'All',
        'selected_student': Student.objects.get(id=student_id) if student_id else 'All',
        'report_date': datetime.now(),
        'logo_path': os.path.join(settings.STATIC_URL, 'img/school_logo.png') # Adjust path as needed
    }

    template_path = 'payments/total_payments_report_pdf_template.html'
    pdf = render_to_pdf(template_path, context)
    if pdf:
        response = pdf
        response['Content-Disposition'] = 'attachment; filename="total_payments_report.pdf"'
        return response

    messages.error(request, "Could not generate PDF for the total payments report.")
    # Use request.GET.urlencode() to preserve filters on redirect
    return redirect('payments:total_payments_report', f'?{request.GET.urlencode()}') if request.GET else redirect('payments:total_payments_report')




@login_required
@user_passes_test(is_staff)
def total_payments_report_csv(request):
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    term_id = request.GET.get('term')
    session_id = request.GET.get('session')
    student_id = request.GET.get('student')

    report_data = get_total_payments_data(start_date_str, end_date_str, term_id, session_id, student_id)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="total_payments_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Category', 'Total Amount']) # Headers for breakdown

    # Write summary data
    writer.writerow([]) # Empty row for spacing
    writer.writerow(['Total Amount Received', report_data['total_amount_received']])
    writer.writerow(['Total Original Amount', report_data['total_original_amount']])
    writer.writerow(['Total Discount Given', report_data['total_discount_given']])
    writer.writerow([]) # Empty row for spacing

    # Write breakdown
    writer.writerow(['Payment Breakdown by Category'])
    for category, amount in report_data['payment_breakdown'].items():
        writer.writerow([category, amount])

    return response



# Calculating Total Income Per term and outstanding

def is_staff_user(user):
    return user.is_staff

@method_decorator(user_passes_test(is_staff_user), name='dispatch')
class FinanceDashboardView(LoginRequiredMixin, View):
    """
    Dashboard view for staff to see an overview of school finances.
    Calculates total income and debt per term and session.
    """
    template_name = 'payments/finance_dashboard.html'

    def get(self, request, *args, **kwargs):
        session_id = request.GET.get('session')
        
        payments = Payment.objects.filter(status='completed')

        if session_id:
            payments = payments.filter(session__id=session_id)

        # Calculate Total Income Per Term and Session
        income_by_term_qs = payments.values(
            'session__name', 'term__name'
        ).annotate(
            total_income=Sum('amount_received')
        ).order_by('session__start_date', 'term__start_date')
        
        # Calculate Total Debt Per Term and Session
        debt_by_term_qs = payments.annotate(
            net_amount_due=ExpressionWrapper(
                F('original_amount') - F('discount_amount'), 
                output_field=DecimalField()
            )
        ).values(
            'session__name', 'term__name'
        ).annotate(
            total_due=Sum('net_amount_due')
        ).order_by('session__start_date', 'term__start_date')

        # Combine income and debt data
        income_and_debt_by_term = {}
        for item in income_by_term_qs:
            key = (item['session__name'], item['term__name'])
            if key not in income_and_debt_by_term:
                income_and_debt_by_term[key] = {
                    'session__name': item['session__name'],
                    'term__name': item['term__name'],
                    'total_income': Decimal('0.00'),
                    'total_due': Decimal('0.00'),
                    'total_debt': Decimal('0.00'),
                }
            income_and_debt_by_term[key]['total_income'] = item['total_income'] or Decimal('0.00')

        for item in debt_by_term_qs:
            key = (item['session__name'], item['term__name'])
            if key not in income_and_debt_by_term:
                income_and_debt_by_term[key] = {
                    'session__name': item['session__name'],
                    'term__name': item['term__name'],
                    'total_income': Decimal('0.00'),
                    'total_due': Decimal('0.00'),
                    'total_debt': Decimal('0.00'),
                }
            
            income_and_debt_by_term[key]['total_due'] = item['total_due'] or Decimal('0.00')
            # Calculate total debt for this term/session
            income_and_debt_by_term[key]['total_debt'] = (
                income_and_debt_by_term[key]['total_due'] - income_and_debt_by_term[key]['total_income']
            )

        # Sort the final list of dictionaries
        income_and_debt_list = sorted(
            income_and_debt_by_term.values(), 
            key=lambda x: (x['session__name'], x['term__name'])
        )

        # Calculate dashboard metrics
        total_income_all_terms = payments.aggregate(Sum('amount_received'))['amount_received__sum'] or Decimal('0.00')
        
        total_due_all_terms_qs = payments.annotate(
            net_amount_due=ExpressionWrapper(
                F('original_amount') - F('discount_amount'), 
                output_field=DecimalField()
            )
        ).aggregate(
            total_due=Sum('net_amount_due')
        )
        total_due_all_terms = total_due_all_terms_qs['total_due'] or Decimal('0.00')
        
        total_outstanding_debt = total_due_all_terms - total_income_all_terms

        # Get all sessions for the filter dropdown
        sessions = Session.objects.all().order_by('-start_date')

        context = {
            'title': 'Finance Dashboard',
            'income_and_debt_list': income_and_debt_list,
            'total_outstanding_debt': total_outstanding_debt,
            'total_income_all_terms': total_income_all_terms,
            'sessions': sessions,
            'selected_session_id': session_id,
        }
        return render(request, self.template_name, context)

 # Function Based View For the Finance Dashboard   
def finance_dashboard(request):
    selected_session_id = request.GET.get('session')
    
    # Base queryset for filtering all payment and fee data
    payment_queryset = Payment.objects.all()
    if selected_session_id:
        payment_queryset = payment_queryset.filter(session_id=selected_session_id)

    # 1. Calculate total income
    total_income_all_terms = payment_queryset.aggregate(
        total_income=Sum('amount_received')
    )['total_income'] or 0

    # 2. Calculate total outstanding debt
    # This is a bit more complex. We need to find the latest payment for each student
    # and sum up the 'balance_after_payment' from those latest payments.
    latest_payments_subquery = payment_queryset.values('student_id').annotate(
        max_id=Max('id')
    ).values('max_id')

    total_outstanding_debt = payment_queryset.filter(
        id__in=Subquery(latest_payments_subquery)
    ).aggregate(
        total_debt=Sum('balance_after_payment')
    )['total_debt'] or 0
    
    # 3. Aggregate income per term/session for the chart
    income_and_debt_list = payment_queryset.values(
        'session__name', 'term__name'
    ).annotate(
        total_income=Sum('amount_received'),
        total_debt=Sum('balance_after_payment')
    ).order_by('session__name', 'term__name')

    # --- Chart Data Preparation ---
    chart_labels = []
    chart_income_data = []
    chart_debt_data = []

    for item in income_and_debt_list:
        chart_labels.append(f"{item['session__name']} - {item['term__name']}")
        chart_income_data.append(float(item['total_income'] or 0))
        chart_debt_data.append(float(item['total_debt'] or 0))
    # --- End of Chart Data Preparation ---

    context = {
        'total_income_all_terms': total_income_all_terms,
        'total_outstanding_debt': total_outstanding_debt,
        'income_and_debt_list': income_and_debt_list,
        'sessions': Session.objects.all().order_by('-start_date'),
        'selected_session_id': selected_session_id,
        'title': 'Finance Dashboard',
        'chart_labels': chart_labels,
        'chart_income_data': chart_income_data,
        'chart_debt_data': chart_debt_data,
    }
    return render(request, 'payments/test_finance_dashboard.html', context)


# parent making payment for student
@login_required
def make_individual_payment(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        # Logic to process payment for a single student
        # e.g., integrate with a payment gateway using student_id
        # and redirect to a payment confirmation page.
    return redirect('pages:parent-dashboard')

@login_required
def make_group_payment(request):
    if request.method == 'POST':
        # Logic to get all children for the current parent
        parent = Parent.objects.get(user=request.user)
        children = parent.children.all()
        # Logic to process a single payment and distribute it equally among the children
        # e.g., divide the total payment amount by the number of children
        # and update each student's fee_balance.
    return redirect('pages:parent-dashboard')



# Parent Make Payment For Child View
@login_required
def make_payment_for_child(request, student_id):
    """
    Allows a parent to make a payment for a specific child.
    """
    try:
        parent = Parent.objects.get(user=request.user)
        student = get_object_or_404(Student, id=student_id, parent=parent)
    except Parent.DoesNotExist:
        messages.error(request, "You are not authorized to make payments for this student.")
        return redirect('students:parent-dashboard')
    
    if request.method == 'POST':
        form = ParentPaymentForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    payment = form.save(commit=False)
                    payment.student = student

                    selected_category_fee = form.cleaned_data['category_fee']
                    payment.original_amount = selected_category_fee.amount_due
                    payment.term = selected_category_fee.term
                    payment.session = selected_category_fee.session
                    payment.payment_category = selected_category_fee.payment_category
                    payment.discount_amount = Decimal('0.00')
                    payment.discount_percentage = Decimal('0.00')
                    payment.recorded_by = None
                    payment.status = 'completed'

                    total_paid_before = Payment.objects.filter(
                        student=student,
                        payment_category=payment.payment_category,
                        term=payment.term,
                        session=payment.session,
                        status='completed'
                    ).exclude(pk=payment.pk).aggregate(Sum('amount_received'))['amount_received__sum'] or Decimal('0.00')

                    payment.balance_before_payment = payment.original_amount - total_paid_before
                    payment.balance_before_payment = max(Decimal('0.00'), payment.balance_before_payment)

                    payment.save()
                    payment.balance_after_payment = payment.balance_before_payment - payment.amount_received
                    payment.balance_after_payment = max(Decimal('0.00'), payment.balance_after_payment)
                    payment.save(update_fields=['balance_after_payment'])

                    receipt = Receipt.objects.create(
                        payment=payment,
                        generated_by=None
                    )
                    messages.success(request, f"Payment of N{payment.amount_received} recorded successfully for {payment.student.first_name}. Receipt #{receipt.receipt_number} generated.")
                    return redirect('payments:view_receipt', receipt_id=receipt.id)

            except Exception as e:
                messages.error(request, f"An error occurred while recording payment: {e}")
                return render(request, 'payments/parent_make_payment.html', {'form': form, 'student': student})
    else:
        form = ParentPaymentForm()

    return render(request, 'payments/parent_make_payment.html', {'form': form, 'student': student})


def payment_details(request, pk, category_pk, term_pk, session_pk):
    """
    View to display details for a specific combined payment record.
    """
    # Retrieve the model instances using the passed primary keys
    student = get_object_or_404(Student, pk=pk)
    payment_category = get_object_or_404(PaymentCategory, pk=category_pk)
    term = get_object_or_404(Term, pk=term_pk)
    session = get_object_or_404(Session, pk=session_pk)

    # Filter payments based on the retrieved details
    payments_for_details = Payment.objects.filter(
        student=student,
        payment_category=payment_category,
        term=term,
        session=session
    ).order_by('payment_date')

    total_amount_received = payments_for_details.aggregate(Sum('amount_received'))['amount_received__sum'] or Decimal('0.00')

    # You might want to get the original fee amount from the StudentFee model
    try:
        student_fee = StudentFee.objects.get(
            student=student,
            category_fee__payment_category=payment_category,
            term=term,
            session=session
        )
        total_due = student_fee.amount_due
    except StudentFee.DoesNotExist:
        total_due = Decimal('0.00')

    # Calculate total discount and balance
    total_discount_amount = sum(
        (p.discount_amount or Decimal('0.00')) + 
        ((p.original_amount or Decimal('0.00')) * (p.discount_percentage / Decimal('100.00')))
        for p in payments_for_details
    )
    balance = total_due - total_amount_received - total_discount_amount

    context = {
        'student': student,
        'payment_category': payment_category,
        'term': term,
        'session': session,
        'payments': payments_for_details,
        'total_due': total_due,
        'total_amount_received': total_amount_received,
        'total_discount_amount': total_discount_amount,
        'balance': balance,
        'title': 'Payment Details'
    }
    return render(request, 'payments/payment_details.html', context)