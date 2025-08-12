# payments/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test, permission_required
from django.contrib import messages
from django.db import transaction
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.db.models import Sum, F,  ExpressionWrapper, DecimalField, Q, Max, Min
from .models import Payment, Receipt, PaymentCategory, StudentAccountLedger, CategoryFee
from curriculum.models import Term, Session
from .forms import PaymentForm
from students.models import Student
from datetime import datetime, timedelta
from decimal import Decimal
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
    is_student_user = False
    student_instance = None
    if hasattr(request.user, 'student'):
        is_student_user = True
        student_instance = request.user.student

    if request.method == 'POST':
        form = PaymentForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    payment = form.save(commit=False)

                    current_student = payment.student

                    if is_student_user:
                        selected_category_fee = form.cleaned_data['category_fee']
                        payment.original_amount = selected_category_fee.amount_due
                        payment.term = selected_category_fee.term
                        payment.session = selected_category_fee.session
                        payment.payment_category = selected_category_fee.payment_category
                        payment.discount_amount = Decimal('0.00')
                        payment.discount_percentage = Decimal('0.00')
                    else: # Staff user
                        selected_category_fee = CategoryFee.objects.filter(
                            payment_category=payment.payment_category,
                            term=payment.term,
                            session=payment.session
                        ).first()
                        if payment.original_amount is None:
                            payment.original_amount = selected_category_fee.amount_due if selected_category_fee else Decimal('0.00')


                    total_paid_for_this_fee_before = Payment.objects.filter(
                        student=current_student,
                        payment_category=payment.payment_category,
                        term=payment.term,
                        session=payment.session,
                        status='completed'
                    ).exclude(pk=payment.pk).aggregate(Sum('amount_received'))['amount_received__sum'] or Decimal('0.00')

                    payment.balance_before_payment = payment.original_amount - total_paid_for_this_fee_before
                    payment.balance_before_payment = max(Decimal('0.00'), payment.balance_before_payment)

                    payment.recorded_by = request.user if request.user.is_staff else None
                    payment.status = 'completed'
                    
                    payment.save()

                    payment.balance_after_payment = payment.balance_before_payment - payment.amount_received
                    payment.balance_after_payment = max(Decimal('0.00'), payment.balance_after_payment)
                    payment.save(update_fields=['balance_after_payment'])

                    receipt = Receipt.objects.create(
                        payment=payment,
                        generated_by=request.user if request.user.is_staff else None
                    )
                    messages.success(request, f"Payment of N{payment.amount_received} recorded successfully for {payment.student.first_name}. Receipt #{receipt.receipt_number} generated.")

                    if is_student_user:
                        return redirect('payments:view_receipt', receipt_id=receipt.id)
                    else:
                        return redirect('payments:payment_history')
            except Exception as e:
                messages.error(request, f"An error occurred while recording payment: {e}")
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
    View to display a list of all payments with filtering and aggregation options.
    Students can only see their own payments. Staff can see all payments.
    """
    payments = Payment.objects.all().select_related(
        'student', 'recorded_by', 'term', 'session', 'payment_category'
    ).order_by('-payment_date')

    # Initialize filter variables to None at the start of the function
    student_id = None
    term_id = None
    session_id = None
    category_id = None

    if hasattr(request.user, 'student'):
        payments = payments.filter(student=request.user.student)
        students = []
        terms = []
        sessions = []
        categories = []
        selected_student_id = None
        selected_term_id = None
        selected_session_id = None
        selected_category_id = None
    else:
        student_id = request.GET.get('student')
        term_id = request.GET.get('term')
        session_id = request.GET.get('session')
        category_id = request.GET.get('category')

        if student_id:
            payments = payments.filter(student__id=student_id)
        if term_id:
            payments = payments.filter(term__id=term_id)
        if session_id:
            payments = payments.filter(session__id=session_id)
        if category_id:
            payments = payments.filter(payment_category__id=category_id)

        students = Student.objects.all().order_by('first_name', 'last_name')
        terms = Term.objects.all().order_by('-start_date')
        sessions = Session.objects.all().order_by('-start_date')
        categories = PaymentCategory.objects.all().order_by('name')
        selected_student_id = student_id
        selected_term_id = term_id
        selected_session_id = session_id
        selected_category_id = category_id

    is_installment_filter = request.GET.get('is_installment')
    if is_installment_filter:
        payments = payments.filter(is_installment=(is_installment_filter == 'true'))

    combined_payments = {}
    for payment in payments:
        key = (
            payment.student.id,
            payment.term.id if payment.term else None,
            payment.session.id if payment.session else None,
            payment.payment_category.id if payment.payment_category else None,
        )
        if key not in combined_payments:
            combined_payments[key] = {
                'student': payment.student,
                'term': payment.term,
                'session': payment.session,
                'payment_category': payment.payment_category,
                'total_original_amount': payment.original_amount if payment.original_amount is not None else Decimal('0.00'),
                'total_amount_received': Decimal('0.00'),
                'total_discount_amount': Decimal('0.00'),
                'payments_list': []
            }
        combined_payments[key]['total_amount_received'] += payment.amount_received
        combined_payments[key]['total_discount_amount'] += payment.discount_amount + \
                                                             ((payment.original_amount or Decimal('0.00')) * (payment.discount_percentage / Decimal('100.00')))
        combined_payments[key]['payments_list'].append(payment)

    combined_payments_list = sorted(list(combined_payments.values()), key=lambda x: x['student'].last_name)

    context = {
        'payments': payments,
        'combined_payments': combined_payments_list,
        'students': students,
        'terms': terms,
        'sessions': sessions,
        'categories': categories,
        'selected_student_id': selected_student_id,
        'selected_term_id': selected_term_id,
        'selected_session_id': selected_session_id,
        'selected_category_id': selected_category_id,
        'selected_is_installment': is_installment_filter,
        'title': 'Payment History',
        'is_staff_user': request.user.is_staff
    }
    return render(request, 'payments/test1_payment_history.html', context)


@login_required
def view_receipt(request, receipt_id):
    """
    View to display a specific receipt.
    """
    receipt = get_object_or_404(
        Receipt.objects.select_related(
            'payment__student', 'payment__term', 'payment__session',
            'payment__payment_category', 'generated_by'
        ),
        id=receipt_id
    )

    if not request.user.is_staff and (not hasattr(receipt.payment.student, 'user') or request.user != receipt.payment.student.user):
        messages.warning(request, "You are not authorized to view this receipt.")
        return redirect('payments:payment_history') # Ensure correct redirect name
      # ADDITION START
    try:
        school_identity = SchoolIdentity.objects.first()
    except SchoolIdentity.DoesNotExist:
        school_identity = None
        # ADDITION END
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



@login_required
@user_passes_test(is_staff)
def debtors_report(request):
    """
    Generates a report of students who currently owe money (have a positive balance in the ledger).
    Allows filtering by term and session.
    """
    term_id = request.GET.get('term')
    session_id = request.GET.get('session')

    # Use the refactored helper function
    debtors = get_debtors_data(term_id, session_id)

    terms = Term.objects.all().order_by('-start_date')
    sessions = Session.objects.all().order_by('-start_date')

    context = {
        'debtors': debtors,
        'terms': terms,
        'sessions': sessions,
        'selected_term_id': term_id,
        'selected_session_id': session_id,
        'title': 'Debtors Report'
    }
    return render(request, 'payments/test_debtors_report.html', context)

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
    Generates a CSV report of debtors based on current outstanding balances.
    """
    term_id = request.GET.get('term')
    session_id = request.GET.get('session')

    # Get the debtor data from your utility function
    # This data now contains 'balance' directly, not 'total_amount_due' or 'amount_paid'
    debtors = get_debtors_data(term_id, session_id)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="debtors_report.csv"'

    writer = csv.writer(response)

    # Define the CSV header based on the keys available in 'debtors' list
    # The header should now use 'Balance' instead of 'Total Amount Due' and 'Amount Paid'
    writer.writerow(['Student Name', 'Class', 'Term', 'Session', 'Balance'])

    # Write the data rows
    for debtor in debtors:
        writer.writerow([
            debtor['student_name'],
            debtor['student_class'],
            debtor['term_name'],
            debtor['session_name'],
            debtor['balance'], # Use 'balance' directly
        ])

    return response



@login_required
def payment_chart_list(request):
    payment_chart_list = CategoryFee.objects.all()   

    context = {
        'payment_chart_list': payment_chart_list,
        
    }
    return render (request, 'payments/fees_table.html', context )


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
    return render(request, 'payments/test_total_payments_report.html', context)


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
