from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.contrib import messages
from django.db import transaction
from django.views.generic import ListView
from django.urls import reverse
from django.db.models import Sum, F, Q, Case, Max, When, OuterRef, Subquery, DecimalField, Value, ExpressionWrapper 
from decimal import Decimal
from django.db.models.functions import Coalesce
from django.contrib.auth.decorators import login_required, user_passes_test
from datetime import datetime, timedelta # Import necessary for date handling

import datetime
from django.utils.decorators import method_decorator # <-- CORRECTED IMPORT
from django.utils import timezone
from django.db.models.functions import Coalesce
from .models import Payment, Receipt, PaymentCategory, StudentFeeAssignment, PaymentNotification, StudentAccountLedger, ClassFeeTemplate
from curriculum.models import Term, Session, SchoolIdentity, Standard
from .forms import StudentPaymentForm, ParentPaymentForm, FullPaymentForm, PaymentNotificationForm
from students.models import Student, Parent
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse, HttpResponse
import csv
from io import StringIO
from django.template.loader import render_to_string
from .utils import render_to_pdf, create_payment # Assuming this utility exists
import json



def is_staff(user):
    return user.is_authenticated and user.is_staff

# -----------------------------------------------------------------------
# API endpoint for getting total outstanding balance for a student.
# This replaces the need to select a specific fee.
# -----------------------------------------------------------------------
def get_student_balance_api(request, student_id):
    """
    API endpoint for getting a student's total outstanding invoice balance.
    Used by AJAX in the payment forms.
    """
    try:
        student = Student.objects.get(pk=student_id)
        current_session = Session.objects.get(is_current=True)
        current_term = Term.objects.get(is_current=True)
    except (Student.DoesNotExist, Session.DoesNotExist, Term.DoesNotExist):
        return JsonResponse({'total_balance': 0}, status=404)

    # Calculate total fees assigned to the student for the current session and term
    total_fees = StudentFeeAssignment.objects.filter(
        student=student,
        session=current_session,
        term=current_term
    ).aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')

    # Calculate total payments made by the student for the current session and term
    total_payments = Payment.objects.filter(
        student=student,
        session=current_session,
        term=current_term,
        status='completed'
    ).aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')
    
    total_balance = total_fees - total_payments

    data = {
        'total_balance': float(total_balance)
    }
    return JsonResponse(data)


# SEARCH STUDENT ON THE PAYMENT Form
def student_search_ajax(request):
    """
    Handles AJAX requests to search for students.
    Returns a JSON response with student data.
    """
    query = request.GET.get('q', '')
    students = []
    
    if query:
        # Search for students whose first name or last name contains the query
        # The __icontains lookup is case-insensitive.
        students = Student.objects.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query)
        ).values('id', 'first_name', 'last_name')[:20] # Limit to 20 results for performance

    results = []
    for student in students:
        results.append({
            'id': student['id'],
            'text': f"{student['first_name']} {student['last_name']}"
        })

    return JsonResponse({'results': results})

# MAKE PAYMENT 
@login_required
def make_payment(request):
    """
    Handles payments for staff.
    Enforces Post/Redirect/Get (PRG) pattern on create_payment failure to prevent double-submission.
    """
    if not request.user.is_staff:
        messages.error(request, "You do not have permission to access this page.")
        return redirect('pages:portal-home')

    # We only initialize the form for GET or to check if it's POST
    form = StudentPaymentForm(request.POST or None)

    if request.method == 'POST':
        # Re-initialize the form specifically for POST data validation
        form = StudentPaymentForm(request.POST) 
        
        if form.is_valid():
            student = form.cleaned_data.get('student')
            
            # Call the centralized utility function
            result = create_payment(request.user, student, form)
            
            if result['success']:
                # Success: Redirect to a new page (PRG pattern)
                messages.success(request, f"Payment recorded successfully. Receipt #{result['receipt_number']}.")
                return redirect(reverse('payments:payment_receipt', args=[result['receipt_id']]))
            else:
                # *** CRITICAL FIX: REDIRECT ON UTILITY FUNCTION FAILURE (IntegrityError) ***
                # This enforces PRG, wiping the POST data from the browser history.
                messages.error(request, result['message'])
                # Assuming 'payments:make_payment' is the name of this view's URL pattern
                return redirect('payments:make_payment') 
        else:
            # Form Validation Error: Re-render the form to show field errors (Standard Django practice)
            messages.error(request, "Please correct the errors in the form.")
            return render(request, 'payments/test1_make_payment.html', {'form': form})
    
    # This block handles the initial GET request (or redirect after a POST failure)
    context = {
        'form': form,
    }
    return render(request, 'payments/test1_make_payment.html', context)

# --------------------------------------------------------------------------------------------------

# PARENT MAKE PAYMENT
def make_parent_payment(request):
    """
    Parent-specific payment view.
    Enforces Post/Redirect/Get (PRG) pattern on create_payment failure to prevent double-submission.
    """
    user = request.user
    if not hasattr(user, 'parent'):
        messages.error(request, "You do not have permission to access this page.")
        return redirect('dashboard')

    parent_profile = user.parent
    form = ParentPaymentForm(request.POST or None, parent=parent_profile)

    if request.method == 'POST':
        # Re-initialize the form specifically for POST data validation
        form = ParentPaymentForm(request.POST, parent=parent_profile)
        
        if form.is_valid():
            student = form.cleaned_data['student']

            # Call the centralized utility function
            result = create_payment(request.user, student, form)
            
            if result['success']:
                # Success: Redirect to a new page (PRG pattern)
                messages.success(request, f"Payment recorded successfully. Receipt #{result['receipt_number']}.")
                return redirect(reverse('payments:payment_receipt', args=[result['receipt_id']]))
            else:
                # *** CRITICAL FIX: REDIRECT ON UTILITY FUNCTION FAILURE (IntegrityError) ***
                messages.error(request, result['message'])
                # Assuming 'payments:make_parent_payment' is the name of this view's URL pattern
                return redirect('payments:make_parent_payment')
        else:
            # Form Validation Error: Re-render the form to show field errors
            messages.error(request, "Please correct the errors in the form.")
            return render(request, 'payments/make_parent_payment.html', {'form': form})
    
    context = {
        'form': form,
    }
    return render(request, 'payments/make_parent_payment.html', context)

# Payment Detail Route
def payment_detail(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    # The `receipt` is accessed via the one-to-one relationship
    # This will not cause an error because a receipt for this payment now exists
    receipt = get_object_or_404(Receipt, payment=payment)
    
    context = {
        'payment': payment,
        'receipt': receipt
    }
    return render(request, 'payments/payment_detail.html', context)


# MAKE FULL PAYMENT
@login_required
def make_full_payment(request, student_id=None, session_id=None, term_id=None):
    if not request.user.is_staff:
        # A non-staff user can only pay for themselves
        student = get_object_or_404(Student, user=request.user)
    else:
        # Staff can pay for a specific student, but the student_id must be provided
        if not student_id:
            messages.error(request, "Student ID is required for a full payment.")
            return redirect(reverse('payments:payments_dashboard'))
        student = get_object_or_404(Student, id=student_id)

    session = get_object_or_404(Session, id=session_id)
    term = get_object_or_404(Term, id=term_id)

    # Calculate the total outstanding balance
    outstanding_assignments = StudentFeeAssignment.objects.filter(
        student=student, session=session, term=term
    ).select_related('payment_category')

    total_due = outstanding_assignments.aggregate(total_due=models.Sum('amount_due'))['total_due'] or Decimal('0.00')

    # Calculate the total paid previously for this session and term
    total_paid = Payment.objects.filter(
        student=student, session=session, term=term, status='completed'
    ).aggregate(total_paid=models.Sum('amount_received'))['total_paid'] or Decimal('0.00')
    
    total_outstanding_balance = total_due - total_paid

    if request.method == 'POST':
        form = FullPaymentForm(request.POST)
        if form.is_valid():
            amount_received = form.cleaned_data['amount_received']

            if amount_received > total_outstanding_balance:
                messages.error(request, "Payment amount cannot exceed the outstanding balance.")
                return render(request, 'payments/make_full_payment.html', {
                    'form': form,
                    'student': student,
                    'session': session,
                    'term': term,
                    'total_outstanding_balance': total_outstanding_balance
                })
            
            # Use a database transaction to ensure all payments are recorded correctly
            with transaction.atomic():
                remaining_amount_to_pay = amount_received
                for assignment in outstanding_assignments:
                    amount_paid_for_category = Payment.objects.filter(
                        student=student, session=session, term=term, 
                        payment_category=assignment.payment_category, status='completed'
                    ).aggregate(total=models.Sum('amount_received'))['total'] or Decimal('0.00')

                    category_balance = assignment.amount_due - amount_paid_for_category
                    
                    if category_balance > 0 and remaining_amount_to_pay > 0:
                        payment_amount = min(category_balance, remaining_amount_to_pay)
                        
                        Payment.objects.create(
                            student=student,
                            payment_category=assignment.payment_category,
                            session=session,
                            term=term,
                            amount_received=payment_amount,
                            payment_method=form.cleaned_data['payment_method'],
                            transaction_id=form.cleaned_data['transaction_id'],
                            status='completed',
                            recorded_by=request.user
                        )
                        remaining_amount_to_pay -= payment_amount
            
            messages.success(request, "Full payment recorded successfully!")
            return redirect('payments:payment_history')

    else:
        form = FullPaymentForm(initial={
            'student': student,
            'session': session,
            'term': term,
            'amount_received': total_outstanding_balance  # Pre-fill with the full amount
        })

    context = {
        'form': form,
        'student': student,
        'session': session,
        'term': term,
        'total_outstanding_balance': total_outstanding_balance,
        'title': 'Make Full Payment'
    }
    return render(request, 'payments/make_full_payment.html', context)

    
# DEBTORS LOGIC
@login_required
@permission_required('payments.view_studentfeeassignment', raise_exception=True)
def debtors_report(request):
    """
    Generates a report of students with outstanding balances (debtors).
    """
    student_class_id = request.GET.get('student_class')
    session_id = request.GET.get('session')
    term_id = request.GET.get('term')

    try:
        current_session = Session.objects.get(is_current=True)
        current_term = Term.objects.get(is_current=True)
    except (Session.DoesNotExist, Term.DoesNotExist):
        current_session = None
        current_term = None

    fees_queryset = StudentFeeAssignment.objects.all()
    payments_queryset = Payment.objects.all()

    if student_class_id:
        fees_queryset = fees_queryset.filter(student__current_class_id=student_class_id)
        payments_queryset = payments_queryset.filter(student__current_class_id=student_class_id)

    if session_id:
        fees_queryset = fees_queryset.filter(session_id=session_id)
        payments_queryset = payments_queryset.filter(session_id=session_id)
    elif current_session:
        fees_queryset = fees_queryset.filter(session=current_session)
        payments_queryset = payments_queryset.filter(session=current_session)

    if term_id:
        fees_queryset = fees_queryset.filter(term_id=term_id)
        payments_queryset = payments_queryset.filter(term_id=term_id)
    elif current_term:
        fees_queryset = fees_queryset.filter(term=current_term)
        payments_queryset = payments_queryset.filter(term=current_term)

    fees_by_student = fees_queryset.values('student').annotate(
        total_fees=Sum('amount_due')
    )
    
    payments_by_student = payments_queryset.values('student').annotate(
        total_payments=Sum('amount_received')
    )
    
    subquery_fees = fees_by_student.filter(student=OuterRef('pk')).values('total_fees')
    subquery_payments = payments_by_student.filter(student=OuterRef('pk')).values('total_payments')

    students = Student.objects.all().order_by('last_name', 'first_name')
    
    if student_class_id:
        students = students.filter(current_class_id=student_class_id)

    students = students.annotate(
        total_fees=Subquery(subquery_fees, output_field=DecimalField()),
        total_payments=Subquery(subquery_payments, output_field=DecimalField())
    ).annotate(
        total_fees_sum = Case(When(total_fees__isnull=True, then=0), default=F('total_fees'), output_field=DecimalField()),
        total_payments_sum = Case(When(total_payments__isnull=True, then=0), default=F('total_payments'), output_field=DecimalField())
    ).annotate(
        balance=F('total_fees_sum') - F('total_payments_sum')
    ).filter(
        balance__gt=0
    ).order_by('balance')

    total_debtor_balance = students.aggregate(total_balance=Sum('balance'))['total_balance'] or 0

    if request.GET.get('format') == 'csv':
        # --- NEW: Get selected Session and Term for the CSV ---
        selected_session_obj = Session.objects.get(id=session_id) if session_id else current_session
        selected_term_obj = Term.objects.get(id=term_id) if term_id else current_term

        session_name = selected_session_obj.name if selected_session_obj else 'N/A'
        term_name = selected_term_obj.name if selected_term_obj else 'N/A'
        # --- END NEW ---

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="debtors_report_{session_name}_{term_name}.csv"'

        writer = csv.writer(response)
        
        # --- UPDATED: Add 'Session' and 'Term' to the header row ---
        writer.writerow(['Student Name', 'Class', 'Session', 'Term', 'Total Due', 'Total Paid', 'Balance'])
        # --- END UPDATED ---

        for student in students:
            total_due = student.total_fees_sum if student.total_fees_sum is not None else 0
            total_paid = student.total_payments_sum if student.total_payments_sum is not None else 0
            balance = total_due - total_paid

            # --- UPDATED: Add the session and term to each row ---
            writer.writerow([
                f"{student.first_name} {student.last_name}",
                student.current_class.name if student.current_class else 'N/A',
                session_name,
                term_name,
                total_due,
                total_paid,
                balance,
            ])
        return response

    # --- New Pagination Logic ---
    paginator = Paginator(students, 20)  # Show 20 students per page
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)
    
    sessions = Session.objects.all()
    terms = Term.objects.all()
    student_classes = Standard.objects.all()
    
    context = {
        'sessions': sessions,
        'terms': terms,
        'student_classes': student_classes,
        'selected_session': session_id,
        'selected_term': term_id,
        'selected_class': student_class_id,
        'total_debt': total_debtor_balance,
        'page_obj': page_obj, # The paginated object
    }

    return render(request, 'payments/debtors_report.html', context)



# Payment History
@login_required
def payment_history(request):
    """Renders the payment history page with filtering and pagination."""
    
    # --- START: LOCAL IMPORTS (Added models needed for parent logic) ---
    from students.models import Parent, Student
    from django.db.models import Q, Sum, Max
    from django.db.models.functions import Coalesce
    from decimal import Decimal
    from django.db.models import DecimalField
    from django.core.paginator import Paginator
    from curriculum.models import Term, Session # Assuming these are imported
    from .models import PaymentCategory # Assuming this is imported
    # --- END: LOCAL IMPORTS ---

    is_staff_user = request.user.is_staff

    # Get filter parameters from the request
    student_search_query = request.GET.get('student_search', '').strip()
    selected_term_id = request.GET.get('term')
    selected_session_id = request.GET.get('session')
    selected_category_id = request.GET.get('category')
    page_number = request.GET.get('page')

    # --- CRITICAL FIX: Determine allowed student IDs ---
    student_filter_list = None 

    if not is_staff_user:
        if hasattr(request.user, 'student'):
            # Case 1: Individual Student User
            student_filter_list = [request.user.student.id]
        elif hasattr(request.user, 'parent'):
            # Case 2: Parent User (NEW LOGIC)
            try:
                parent = Parent.objects.get(user=request.user)
                # Get IDs of all children associated with this parent
                student_filter_list = list(Student.objects.filter(parent=parent).values_list('id', flat=True))
                
                # Check for student filtering from the dashboard URL (?student=ID)
                student_id_from_dashboard = request.GET.get('student')
                if student_id_from_dashboard and student_id_from_dashboard.isdigit():
                    student_id = int(student_id_from_dashboard)
                    # Ensure the requested student ID is actually one of the parent's children
                    if student_id in student_filter_list:
                        student_filter_list = [student_id]
                    else:
                        # If a parent tries to filter for a non-child, ignore the filter.
                        # We keep the original list of all children for safety.
                        pass
            except Parent.DoesNotExist:
                # If no Parent object is found, the user can see no payments.
                student_filter_list = []
        else:
            # Not staff, not student, not parent -> no access
            student_filter_list = []

    # ----------------------------------------------------
    # Base queryset for all individual payments
    payments_queryset = Payment.objects.filter(status='completed').select_related(
        'student__user', 'payment_category', 'term', 'session', 'recorded_by', 'receipt'
    ).order_by('-payment_date')
    
    # Base queryset for combined payments
    combined_payments_queryset = Payment.objects.filter(status='completed')

    # Apply access filtering based on the calculated student_filter_list
    if not is_staff_user:
        # Filter both querysets to ONLY include students in the list
        payments_queryset = payments_queryset.filter(student_id__in=student_filter_list)
        combined_payments_queryset = combined_payments_queryset.filter(student_id__in=student_filter_list)
        
        # Disable the search bar for non-staff users
        student_search_query = ''
    else:
        # Staff-specific search filters (Applied only if staff)
        if student_search_query:
            payments_queryset = payments_queryset.filter(
                Q(student__user__first_name__icontains=student_search_query) |
                Q(student__user__last_name__icontains=student_search_query) |
                Q(student__USN__icontains=student_search_query)
            )
            combined_payments_queryset = combined_payments_queryset.filter(
                Q(student__user__first_name__icontains=student_search_query) |
                Q(student__user__last_name__icontains=student_search_query) |
                Q(student__USN__icontains=student_search_query)
            )
    
    # --- Apply general filters for individual payments ---
    if selected_term_id:
        payments_queryset = payments_queryset.filter(term__id=selected_term_id)
    if selected_session_id:
        payments_queryset = payments_queryset.filter(session__id=selected_session_id)
    if selected_category_id:
        payments_queryset = payments_queryset.filter(payment_category__id=selected_category_id)

    # --- Apply general filters for combined payments ---
    if selected_term_id:
        combined_payments_queryset = combined_payments_queryset.filter(term__id=selected_term_id)
    if selected_session_id:
        combined_payments_queryset = combined_payments_queryset.filter(session__id=selected_session_id)
    if selected_category_id:
        combined_payments_queryset = combined_payments_queryset.filter(payment_category__id=selected_category_id)

    # Group and annotate payments for the combined summary table
    combined_payments = combined_payments_queryset.values(
        'student', 'student__user__first_name', 'student__user__last_name',
        'payment_category', 'payment_category__name',
        'term', 'term__name', 'session', 'session__name'
    ).annotate(
        total_amount_received=Coalesce(Sum('amount_received'), Decimal(0), output_field=DecimalField()),
        total_discount_amount=Coalesce(Sum('discount_amount'), Decimal(0), output_field=DecimalField()),
        latest_payment_date=Max('payment_date')
    ).order_by(
        'student__user__last_name', 'student__user__first_name',
        'session__name', 'term__name', 'payment_category__name'
    )
    
    # Attach original amount from StudentFeeAssignment for each combined entry
    from payments.models import StudentFeeAssignment # Needs to be imported for this section
    for combined in combined_payments:
        try:
            original_amount = StudentFeeAssignment.objects.get(
                student_id=combined['student'],
                term_id=combined['term'],
                session_id=combined['session'],
                payment_category_id=combined['payment_category']
            ).amount_due
        except StudentFeeAssignment.DoesNotExist:
            original_amount = Decimal(0)
        combined['total_original_amount'] = original_amount

    # Paginate the individual payments
    paginator = Paginator(payments_queryset, 20)
    page_obj = paginator.get_page(page_number)
    payments = page_obj

    # Preserve filter parameters for pagination links
    query_string = request.GET.copy()
    if 'page' in query_string:
        del query_string['page']
    
    context = {
        'payments': payments,
        'combined_payments': combined_payments,
        'page_obj': page_obj,
        'is_staff_user': is_staff_user,
        # Assuming Term, Session, and PaymentCategory are imported and available here
        'terms': Term.objects.all(),
        'sessions': Session.objects.all(),
        'categories': PaymentCategory.objects.all(),
        'selected_term_id': selected_term_id,
        'selected_session_id': selected_session_id,
        'selected_category_id': selected_category_id,
        'student_search_query': student_search_query,
        'query_string': query_string.urlencode(),
        'title': 'Payment History'
    }

    # Fetch students for the filter dropdown only if it's a staff user
    if is_staff_user:
        context['students'] = Student.objects.all()

    return render(request, 'payments/test_payment_history.html', context)


# PAYMENT RECEIPT
def payment_receipt(request, receipt_pk):
    """
    Renders a payment receipt with an accurate summary of the student's
    overall invoice.
    """
    receipt = get_object_or_404(Receipt, pk=receipt_pk)
    student = receipt.payment.student
    
    # Get the session and term from the payment itself
    current_session = receipt.payment.session
    current_term = receipt.payment.term
    
    # 1. Calculate the total amount due for the current session and term
    total_invoice_due_aggr = StudentFeeAssignment.objects.filter(
        student=student,
        session=current_session,
        term=current_term
    ).aggregate(total_due=Sum('amount_due'))
    total_invoice_due = total_invoice_due_aggr['total_due'] or Decimal('0.00')

    # 2. Calculate the total amount paid by the student for the current session and term
    total_paid_aggr = Payment.objects.filter(
        student=student,
        session=current_session,
        term=current_term,
        status='completed'
    ).aggregate(total_paid=Sum('amount_received'))
    total_invoice_paid = total_paid_aggr['total_paid'] or Decimal('0.00')

    # 3. Calculate the remaining balance
    total_invoice_balance = total_invoice_due - total_invoice_paid

    # 4. Fetch the individual assigned fees for the breakdown table
    assigned_fees = StudentFeeAssignment.objects.filter(
        student=student,
        session=current_session,
        term=current_term
    ).order_by('payment_category__name').select_related('payment_category')
    
    context = {
        'receipt': receipt,
        'student': student,
        'assigned_fees': assigned_fees,
        'total_invoice_due': total_invoice_due,
        'total_invoice_paid': total_invoice_paid,
        'total_invoice_balance': total_invoice_balance,
        'current_session': current_session,
        'current_term': current_term,
    }
    return render(request, 'payments/payment_receipt.html', context)

# Receipt PDF
@login_required
def receipt_pdf(request, receipt_id):
    """
    Generates a PDF of a payment receipt.
    """
    receipt = get_object_or_404(Receipt, pk=receipt_id)
    school_identity = SchoolIdentity.objects.first()
    
    # Render the HTML template with the receipt context
    context = {
        'receipt': receipt,
        'school_identity': school_identity,
    }
    html_string = render_to_string('payments/payment_receipt_pdf.html', context)
    
    # Convert the HTML to PDF using the utility function
    pdf = render_to_pdf(html_string)
    
    # Return the PDF as an HTTP response
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"Receipt-{receipt.receipt_number}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    
    return HttpResponse("PDF generation failed.", status=500)



# --- New/Refactored Views for Financial Management ---
# Custom JSON encoder to handle Decimal objects for charts
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# Custom JSON encoder to handle Decimal objects for charts
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

# Custom JSON encoder to handle Decimal objects for charts
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

@login_required
@user_passes_test(is_staff)
def finance_dashboard(request):
    """
    Renders the finance dashboard with key financial metrics and charts
    based on user-selected filters for session, term, and class.
    """
    # Get all available sessions, terms, and classes for filter dropdowns
    sessions = Session.objects.all().order_by('-start_date')
    terms = Term.objects.all().order_by('start_date')
    classes = Standard.objects.all().order_by('name')

    # Get selected filter IDs from the request or default to current
    selected_session_id = request.GET.get('session')
    selected_term_id = request.GET.get('term')
    selected_class_id = request.GET.get('class')
    
    current_session = Session.objects.filter(is_current=True).first()
    current_term = Term.objects.filter(is_current=True).first()

    selected_session_obj = sessions.filter(id=selected_session_id).first() if selected_session_id else current_session
    selected_term_obj = terms.filter(id=selected_term_id).first() if selected_term_id else current_term
    selected_class_obj = classes.filter(id=selected_class_id).first() if selected_class_id else None

    # Construct the filter arguments dynamically
    fee_filters = {}
    payment_filters = {'status': 'completed'}
    ledger_filters = {}
    
    if selected_session_obj:
        fee_filters['session'] = selected_session_obj
        payment_filters['session'] = selected_session_obj
        ledger_filters['session'] = selected_session_obj
    
    if selected_term_obj:
        fee_filters['term'] = selected_term_obj
        payment_filters['term'] = selected_term_obj
        ledger_filters['term'] = selected_term_obj

    # The student/class filter should be applied to the Student model
    student_filters = {}
    if selected_class_obj:
        student_filters['current_class'] = selected_class_obj

    # 1. Calculate global outstanding debt from the ledger
    # The Sum() query is run on the Ledger model
    total_outstanding_query = StudentAccountLedger.objects.filter(
        **ledger_filters
    )
    if selected_class_obj:
        total_outstanding_query = total_outstanding_query.filter(
            student__current_class=selected_class_obj
        )
    total_outstanding = total_outstanding_query.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

    # 2. Get the top 10 debtors based on the current filters from the ledger
    # The filter for balance > 0 and the session/term filters need to be on the ledger
    top_debtors = Student.objects.filter(
        account_ledgers__balance__gt=0,
        **student_filters # The class filter is applied here
    ).annotate(
        # The Subquery is what uses the session and term filters
        balance=Subquery(
            StudentAccountLedger.objects.filter(
                student=OuterRef('pk'),
                **ledger_filters
            ).values('balance')
        )
    ).order_by('-balance').select_related('current_class')[:10]

    # 3. Calculate global total fees and payments
    total_fees_due = StudentFeeAssignment.objects.filter(**fee_filters).aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')
    total_payments_received = Payment.objects.filter(**payment_filters).aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')

    # 4. Data for Charts (unchanged as it doesn't use the ledger)
    monthly_payments_data = list(
        Payment.objects.filter(**payment_filters).extra(
            {'month': "strftime('%%m', payment_date)", 'year': "strftime('%%Y', payment_date)"}
        ).values('year', 'month').annotate(total_amount=Sum('amount_received')).order_by('year', 'month')
    )

    payments_by_category_data = list(
        Payment.objects.filter(**payment_filters).values('payment_category__name').annotate(total_amount=Sum('amount_received')).order_by('-total_amount')
    )
    
    context = {
        'total_fees_due': total_fees_due,
        'total_payments_received': total_payments_received,
        'total_outstanding': total_outstanding,
        'top_debtors': top_debtors,
        'sessions': sessions,
        'terms': terms,
        'classes': classes,
        'selected_session_id': selected_session_obj.id if selected_session_obj else None,
        'selected_term_id': selected_term_obj.id if selected_term_obj else None,
        'selected_class_id': selected_class_obj.id if selected_class_obj else None,
        'monthly_payments_json': json.dumps(monthly_payments_data, cls=DecimalEncoder),
        'payments_by_category_json': json.dumps(payments_by_category_data, cls=DecimalEncoder),
    }
    
    return render(request, 'payments/finance_dashboard.html', context)

# PAYMENT SUMMARY
@login_required
@user_passes_test(is_staff)
def payment_summary(request):
    """
    Provides a detailed summary of payments by category, term, and session.
    """
    summary_data = Payment.objects.values(
        'payment_category__name', 'term__name', 'session__name'
    ).annotate(
        total_received=Sum('amount_received'),
        payment_category_id=F('payment_category__id'),
        term_id=F('term__id'),
        session_id=F('session__id')
    ).order_by('session__name', 'term__name', 'payment_category__name')

    context = {
        'title': 'Payment Summary Report',
        'summary_data': summary_data,
    }
    return render(request, 'payments/payment_summary.html', context)




# Placeholder for total payments report
# @login_required
# @user_passes_test(is_staff)
# def total_payments_report(request):
#     """Generates a detailed report of all payments received."""
#     payments = Payment.objects.all().select_related(
#         'student__user', 'payment_category', 'term', 'session'
#     ).order_by('-payment_date')
    
#     paginator = Paginator(payments, 50)
#     page_number = request.GET.get('page')
#     page_obj = paginator.get_page(page_number)
    
#     context = {
#         'title': 'Total Payments Report',
#         'payments': page_obj,
#     }
#     return render(request, 'payments/total_payments_report.html', context)

@login_required
@user_passes_test(is_staff)
# Assuming Payment, Student, Term, Session, etc., are imported correctly
# from .models import Student, Term, Session, Payment 


def total_payments_report(request):
    """
    Generates a detailed report by directly aggregating data from the Payment model,
    as confirmed by the provided utility function's structure.
    """
    
    # --- 1. FILTER & DATA SETUP ---
    all_terms = Term.objects.all().order_by('name')
    all_sessions = Session.objects.all().order_by('-start_date')
    all_students = Student.objects.all().select_related('user').order_by('last_name')
    
    selected_start_date = request.GET.get('start_date')
    selected_end_date = request.GET.get('end_date')
    selected_term_id = request.GET.get('term')
    selected_session_id = request.GET.get('session')
    selected_student_id = request.GET.get('student')
    
    # Start with all completed payments (CRITICAL FIX from API/Utility code)
    payments_query = Payment.objects.filter(status='completed')

    # Apply Filters (Matching the utility function's logic)
    if selected_start_date:
        try:
            start_date = datetime.strptime(selected_start_date, '%Y-%m-%d').date()
            payments_query = payments_query.filter(payment_date__gte=start_date)
        except ValueError:
            pass
    if selected_end_date:
        try:
            # The utility adds a day to include the end date
            end_date = datetime.strptime(selected_end_date, '%Y-%m-%d').date() + timedelta(days=1)
            payments_query = payments_query.filter(payment_date__lt=end_date)
        except ValueError:
            pass
    if selected_term_id:
        payments_query = payments_query.filter(term__id=selected_term_id)
    if selected_session_id:
        payments_query = payments_query.filter(session__id=selected_session_id)
    if selected_student_id:
        payments_query = payments_query.filter(student__id=selected_student_id)

    # --- 2. CALCULATE SUMMARY TOTALS (Matching utility logic) ---

    # Calculate total original amount: Sum of MAX original_amount for unique fee types
    unique_fees_agg = payments_query.values(
        'student', 'term', 'session', 'payment_category'
    ).annotate(
        unique_original_amount=Max('original_amount')
    ).aggregate(
        total_invoice_amount=Coalesce(Sum('unique_original_amount'), Value(0.0, output_field=DecimalField()))
    )
    
    # Calculate Total Paid
    total_paid_agg = payments_query.aggregate(
        total_amount_paid=Coalesce(Sum('amount_received'), Value(0.0, output_field=DecimalField()))
    )

    # Combine totals
    total_invoice_amount = unique_fees_agg['total_invoice_amount']
    total_amount_paid = total_paid_agg['total_amount_paid']
    total_balance_due = total_invoice_amount - total_amount_paid
    
    summary_totals = {
        'total_invoice_amount': total_invoice_amount,
        'total_amount_paid': total_amount_paid,
        'total_balance_due': total_balance_due,
    }
    
    # --- 3. PREPARE DETAILED BREAKDOWN (Matching utility logic) ---

    # Note: When grouping by (student, category, term, session), Max('original_amount') 
    # gives the correct *invoice* amount, and Sum('amount_received') gives the *total paid* # against that invoice/fee item.
    payment_breakdown = payments_query.values(
        'student__user__first_name', 
        'student__user__last_name', 
        'student__USN', 
        'payment_category__name', 
        'term__name', 
        'session__name'
    ).annotate(
        # These names match the template variables:
        sum_original=Max('original_amount'),
        sum_amount_received=Coalesce(Sum('amount_received'), Value(0.0, output_field=DecimalField())),
        
        # Calculate balance per row item: Max(original) - Sum(received)
        # Note: If discounts are involved, this balance calculation can be slightly off, 
        # but for simplicity, we use the original/received fields as provided.
        sum_balance=ExpressionWrapper(
            F('sum_original') - F('sum_amount_received'),
            output_field=DecimalField()
        )
    ).order_by('student__user__last_name', 'payment_category__name')
    
    
    # --- 4. FINAL CONTEXT DATA ---
    context = {
        'all_terms': all_terms,
        'all_sessions': all_sessions,
        'all_students': all_students,
        
        'selected_start_date': selected_start_date,
        'selected_end_date': selected_end_date,
        'selected_term_id': selected_term_id,
        'selected_session_id': selected_session_id,
        'selected_student_id': selected_student_id,
        
        'summary_totals': summary_totals, 
        'payment_breakdown': payment_breakdown,

        # Retain this for template compatibility, though calculated total_discount_given is not needed
        'total_discount_given': Value(0.0, output_field=DecimalField()), 
    }
    
    return render(request, 'payments/total_payments_report.html', context)

# Placeholder for PDF/CSV exports
@login_required
@user_passes_test(is_staff)
def debtors_report_pdf(request):
    term_id = request.GET.get('term')
    session_id = request.GET.get('session')
    category_id = request.GET.get('category')
    
    debtors_queryset = StudentFeeAssignment.objects.all().select_related(
        'student__user', 'payment_category', 'term', 'session'
    ).annotate(
        total_payments=Sum('payments__amount_received'),
        balance_due=F('amount_due') - F('total_payments')
    ).filter(balance_due__gt=Decimal('0.00')).order_by('student__user__last_name')
    
    if term_id:
        debtors_queryset = debtors_queryset.filter(term__id=term_id)
    if session_id:
        debtors_queryset = debtors_queryset.filter(session__id=session_id)
    if category_id:
        debtors_queryset = debtors_queryset.filter(payment_category__id=category_id)
    
    context = {
        'debtors': debtors_queryset,
        'selected_term': get_object_or_404(Term, id=term_id) if term_id else None,
        'selected_session': get_object_or_404(Session, id=session_id) if session_id else None,
        'selected_category': get_object_or_404(PaymentCategory, id=category_id) if category_id else None,
    }
    html_string = render_to_string('payments/debtors_report_pdf_template.html', context)
    pdf = render_to_pdf(html_string)
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="debtors_report.pdf"'
        return response
    return HttpResponse("PDF generation failed.", status=500)

@login_required
@user_passes_test(is_staff)
def debtors_report_csv(request):
    # This view would use similar logic as debtors_report_pdf to fetch data
    # and then write it to a CSV file.
    return HttpResponse("CSV export not yet implemented.", status=501)

@login_required
@user_passes_test(is_staff)
def total_payments_report_pdf(request):
    # This view would use similar logic as total_payments_report to fetch data
    # and then render a PDF.
    return HttpResponse("PDF export not yet implemented.", status=501)

@login_required
@user_passes_test(is_staff)
def total_payments_report_csv(request):
    # This view would use similar logic as total_payments_report to fetch data
    # and then write it to a CSV file.
    return HttpResponse("CSV export not yet implemented.", status=501)


# SHOW ALL PAYMENT FROM THE CLASS TEMPLATE
@login_required
def payment_chart_list(request):
    """
    Displays the complete payment chart for all classes to any logged-in user.
    """
    try:
        current_session = Session.objects.get(is_current=True)
        current_term = Term.objects.get(is_current=True)
    except (Session.DoesNotExist, Term.DoesNotExist):
        current_session = None
        current_term = None
    
    fee_data = {}
    
    # Get fees for all classes.
    standards_to_show = Standard.objects.all().order_by('name')

    if standards_to_show:
        for standard in standards_to_show:
            if current_session and current_term:
                fees = ClassFeeTemplate.objects.filter(
                    student_class=standard, 
                    session=current_session, 
                    term=current_term
                ).select_related('payment_category', 'student_class', 'session', 'term').order_by('payment_category__name')
                
                if fees.exists():
                    fee_data[standard] = fees
            
    context = {
        'fee_data': fee_data,
        'current_session': current_session,
        'current_term': current_term,
    }
    
    return render(request, 'payments/payment_chart_list.html', context)



# Add this new view function
def get_category_fee_details(request):
    category_fee_id = request.GET.get('category_fee_id')
    student_id = request.GET.get('student_id')

    # Ensure both IDs are provided
    if not category_fee_id or not student_id:
        return JsonResponse({'error': 'Missing category_fee_id or student_id'}, status=400)

    try:
        # Fetch the student fee assignment record
        assigned_fee = StudentFeeAssignment.objects.filter(
            payment_category__id=category_fee_id,
            student__id=student_id
        ).annotate(
            total_payments=Coalesce(Sum('payments__amount_received'), Decimal('0.00'))
        ).first()

        if assigned_fee:
            original_amount = assigned_fee.amount_due
            remaining_balance = assigned_fee.amount_due - assigned_fee.total_payments
            
            # Return details as JSON
            return JsonResponse({
                'original_amount': float(original_amount),
                'remaining_balance': float(remaining_balance)
            })
        else:
            return JsonResponse({'error': 'Fee assignment not found'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
  

# GET INVOICE DATA
def get_invoice_data(student):
    """
    Helper function to calculate and return all invoice data.
    """
    try:
        current_session = Session.objects.get(is_current=True)
        current_term = Term.objects.get(is_current=True)
    except (Session.DoesNotExist, Term.DoesNotExist):
        return {'error_message': 'Please set the current session and term in the curriculum module.'}

    # Fetch all fees assigned to the student for the current term and session
    assigned_fees = StudentFeeAssignment.objects.filter(
        student=student,
        session=current_session,
        term=current_term
    ).order_by('payment_category__name')

    # Calculate the total invoice due by summing ALL fees.
    total_due_aggr = assigned_fees.aggregate(total_due=Sum('amount_due'))
    total_due = total_due_aggr['total_due'] or Decimal('0.00')

    # Calculate the total amount paid by summing ALL payments.
    total_paid_aggr = Payment.objects.filter(
        student=student,
        session=current_session,
        term=current_term,
        status='completed'
    ).aggregate(total_paid=Sum('amount_received'))
    total_paid = total_paid_aggr['total_paid'] or Decimal('0.00')

    # Calculate the final balance.
    balance = total_due - total_paid

    # Get the list of fees for the breakdown table.
    fees_breakdown = assigned_fees.values(
        'payment_category__name', 'amount_due'
    ).order_by('payment_category__name')

    return {
        'student': student,
        'fees_breakdown': fees_breakdown,
        'total_due': total_due,
        'total_paid': total_paid,
        'balance': balance,
        'current_session': current_session,
        'current_term': current_term,
        'today': timezone.now().date(),
    }

# STUDENTS INVOICE
@login_required
def student_invoice(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    context = get_invoice_data(student)
    return render(request, 'payments/student_invoice.html', context)

@login_required
def student_invoice_view(request):
    try:
        student = Student.objects.get(user=request.user)
    except Student.DoesNotExist:
        return redirect('pages:portal-home')
    
    context = get_invoice_data(student)
    return render(request, 'payments/student_invoice.html', context)

# PAYMENT NOTIFICATION
@login_required
def notify_payment(request):
    user = request.user
    parent_obj = None
    student_for_display = None
    
    # --- 1. Determine the relevant Parent/Student objects ---
    try:
        if hasattr(user, 'student') and user.student:
            # Case 1: Direct Student
            student_for_display = user.student
            
        elif hasattr(user, 'parent') and user.parent:
            # Case 2: Parent
            parent_obj = user.parent
            children = Student.objects.filter(parent=parent_obj)
            
            # Set student_for_display to the single child or the first child 
            # for the template's display message.
            if children.exists():
                student_for_display = children.first()
                
    except (Student.DoesNotExist, Parent.DoesNotExist):
        pass
    
    # --- 2. Set initial data and handle POST request ---
    
    initial_data = {}
    initial_data['notified_by'] = user.pk
    
    # Pre-set the student field value if the form will be hiding it (i.e., non-staff)
    if student_for_display and not user.is_staff:
        initial_data['student'] = student_for_display.pk 
        
    # Prepare kwargs for the form initialization
    form_kwargs = {'user': user, 'parent': parent_obj}

    if request.method == 'POST':
        form = PaymentNotificationForm(request.POST, initial=initial_data, **form_kwargs)
        if form.is_valid():
            notification = form.save(commit=False)
            notification.notified_by = user 
            
            # If the student field was hidden, ensure it is set correctly on the model instance
            # This is a safety check, as the initial data should handle this if the form is valid.
            if not user.is_staff and student_for_display:
                 notification.student = student_for_display
            
            notification.save()
            messages.success(request, "Payment notification submitted successfully! It is now pending admin review.")
            return redirect('payments:payment-notification-success')
    else:
        form = PaymentNotificationForm(initial=initial_data, **form_kwargs)
        
    # --- 3. Context and Rendering ---
    context = {
        'form': form,
        'student_for_display': student_for_display, 
        'title': 'Submit Proof of Payment'
    }
    
    return render(request, 'payments/notify_payment.html', context)


# PAYMENT NOTIFICATION
def payment_notification_success(request):
    """Displays a simple success message after notification."""
    return render(request, 'payments/payment_notification_success.html', {})

# NOTE ON PARENT USERS:
# If you want parents to choose between their children, you should modify 
# PaymentNotificationForm's __init__ method to filter the 'student' queryset 
# to only include children related to the logged-in parent/user.


#New Staff View for Notifications
# Helper function to check for staff status
# Helper function to check for staff status
def is_staff_check(user):
    return user.is_authenticated and user.is_staff

@method_decorator(user_passes_test(is_staff_check), name='dispatch')
class PaymentNotificationListView(ListView):
    model = PaymentNotification
    template_name = 'payments/payment_notification_list.html'
    context_object_name = 'notifications'
    # Use the correct model field name for ordering
    ordering = ['-payment_date', '-submission_date'] 
    paginate_by = 10

    def get_queryset(self):
        # We can also add a default filter here to only show PENDING ones, 
        # as they are the ones requiring immediate action.
        # This is a good practice to reduce noise for the admin.
        return super().get_queryset().filter(status='PENDING')

# Optional: View to handle processing/deleting a notification
@user_passes_test(is_staff_check) # Applying is_staff check here too
def process_notification(request, pk):
    notification = get_object_or_404(PaymentNotification, pk=pk)
    
    # In a real system, you would:
    # 1. Verify the payment details.
    # 2. Create a formal Payment record based on the notification data.
    # 3. Mark the notification as 'PROCESSED' or 'REJECTED'.
    # For now, it redirects back to the list.
    
    return redirect('payments:notification-list')