# student_management_app/views.py (or payments/views.py)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, F, Q
from .models import Payment, Receipt, PaymentCategory, StudentAccountLedger, CategoryFee
from curriculum.models import Term, Session
from .forms import PaymentForm
from students.models import Student
from datetime import datetime, timedelta
from decimal import Decimal
from django.http import JsonResponse

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

                    if is_student_user:
                        selected_category_fee = form.cleaned_data['category_fee']
                        payment.original_amount = selected_category_fee.amount_due
                        payment.term = selected_category_fee.term
                        payment.session = selected_category_fee.session
                        payment.payment_category = selected_category_fee.payment_category
                        payment.discount_amount = Decimal('0.00')
                        payment.discount_percentage = Decimal('0.00')
                    else:
                        pass # Staff fields handled by form.save(commit=False)

                    payment.recorded_by = request.user if request.user.is_staff else None
                    payment.status = 'completed'
                    payment.save()

                    receipt = Receipt.objects.create(
                        payment=payment,
                        generated_by=request.user if request.user.is_staff else None
                    )
                    messages.success(request, f"Payment of ${payment.amount_received} recorded successfully for {payment.student.first_name}. Receipt #{receipt.receipt_number} generated.")

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
                return render(request, 'payments/make_payment.html', context)
        else:
            messages.error(request, "Please correct the errors in the form.")
            context = {'form': form, 'title': 'Record New Payment'}
            return render(request, 'payments/make_payment.html', context)
    else:
        form = PaymentForm(user=request.user)

    context = {
        'form': form,
        'title': 'Record New Payment'
    }
    return render(request, 'payments/make_payment.html', context)

@login_required
def payment_history(request):
    """
    View to display a list of all payments with filtering and aggregation options.
    Students can only see their own payments. Staff can see all payments.
    """
    payments = Payment.objects.all().select_related(
        'student', 'recorded_by', 'term', 'session', 'payment_category'
    ).order_by('-payment_date')

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
            payment.is_installment,
            payment.installment_number,
            payment.total_installments
        )
        if key not in combined_payments:
            combined_payments[key] = {
                'student': payment.student,
                'term': payment.term,
                'session': payment.session,
                'payment_category': payment.payment_category,
                'is_installment': payment.is_installment,
                'installment_number': payment.installment_number,
                'total_installments': payment.total_installments,
                'total_original_amount': Decimal('0.00'),
                'total_amount_received': Decimal('0.00'),
                'total_discount_amount': Decimal('0.00'),
                'payments_list': []
            }
        combined_payments[key]['total_original_amount'] += payment.original_amount if payment.original_amount is not None else Decimal('0.00')
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
    return render(request, 'payments/payment_history.html', context)

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
        return redirect('payment_history')

    context = {
        'receipt': receipt,
        'title': f'Receipt #{receipt.receipt_number}'
    }
    return render(request, 'payments/receipt_detail.html', context)


@login_required
@user_passes_test(is_staff)
def debtors_report(request):
    """
    Generates a report of students who currently owe money (have a positive balance in the ledger).
    Allows filtering by term and session.
    """
    term_id = request.GET.get('term')
    session_id = request.GET.get('session')

    debtors_query = StudentAccountLedger.objects.filter(balance__gt=0).select_related('student', 'term', 'session')

    if term_id:
        debtors_query = debtors_query.filter(term__id=term_id)
    if session_id:
        debtors_query = debtors_query.filter(session__id=session_id)

    debtors = debtors_query.order_by('student__last_name', 'session__name', 'term__name')

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
    return render(request, 'payments/debtors_report.html', context)


@login_required
@user_passes_test(is_staff)
def total_payments_report(request):
    """
    Generates a report showing total payments made by students,
    with options to filter by period, term, or session.
    """
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    term_id = request.GET.get('term')
    session_id = request.GET.get('session')
    student_id = request.GET.get('student')

    payments_query = Payment.objects.filter(status='completed')

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(payment_date__gte=start_date)
        except ValueError:
            messages.error(request, "Invalid start date format. Please use YYYY-MM-DD.")
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)
            payments_query = payments_query.filter(payment_date__lt=end_date)
        except ValueError:
            messages.error(request, "Invalid end date format. Please use YYYY-MM-DD.")
    if term_id:
        payments_query = payments_query.filter(term__id=term_id)
    if session_id:
        payments_query = payments_query.filter(session__id=session_id)
    if student_id:
        payments_query = payments_query.filter(student__id=student_id)


    total_amount_received = payments_query.aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')
    total_original_amount = payments_query.aggregate(total=Sum('original_amount'))['total'] or Decimal('0.00')
    total_discount_given = payments_query.aggregate(
        total_fixed_discount=Sum('discount_amount'),
        total_percentage_discount=Sum(F('original_amount') * (F('discount_percentage') / Decimal('100.00')))
    )
    total_discount_given = (total_discount_given['total_fixed_discount'] or Decimal('0.00')) + \
                           (total_discount_given['total_percentage_discount'] or Decimal('0.00'))


    payment_breakdown = payments_query.values(
        'student__first_name', 'student__last_name', 'student__student_id',
        'payment_category__name', 'term__name', 'session__name'
    ).annotate(
        sum_amount_received=Sum('amount_received'),
        sum_original=Sum('original_amount'),
        sum_fixed_discount=Sum('discount_amount'),
        sum_percentage_discount=Sum(F('original_amount') * (F('discount_percentage') / Decimal('100.00')))
    ).order_by(
        'student__last_name', 'session__name', 'term__name', 'payment_category__name'
    )

    terms = Term.objects.all().order_by('-start_date')
    sessions = Session.objects.all().order_by('-start_date')
    students = Student.objects.all().order_by('first_name', 'last_name')

    context = {
        'total_amount_received': total_amount_received,
        'total_original_amount': total_original_amount,
        'total_discount_given': total_discount_given,
        'payment_breakdown': payment_breakdown,
        'terms': terms,
        'sessions': sessions,
        'students': students,
        'selected_start_date': start_date_str,
        'selected_end_date': end_date_str,
        'selected_term_id': term_id,
        'selected_session_id': session_id,
        'selected_student_id': student_id,
        'title': 'Total Payments Report'
    }
    return render(request, 'payments/total_payments_report.html', context)

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

