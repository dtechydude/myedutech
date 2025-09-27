# payments/utils.py
from decimal import Decimal
from students.models import Student
from curriculum.models import Term, Session
import os
from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from django.conf import settings
from xhtml2pdf import pisa
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Prefetch, Q
from django.db import transaction, IntegrityError
from datetime import datetime
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
import logging
from .helpers import generate_receipt_number



def update_student_ledger(student, session, term):
    """
    Calculates the net balance for a student for a specific session/term
    and updates their corresponding StudentAccountLedger entry.
    """
    # Import models locally within the function to break the circular dependency
    from .models import StudentAccountLedger, StudentFeeAssignment, Payment

    # Calculate total fees assigned to the student for the given session and term
    total_fees = StudentFeeAssignment.objects.filter(
        student=student,
        session=session,
        term=term
    ).aggregate(total=Sum('amount_due'))['total'] or Decimal('0.00')

    # Calculate total payments received from the student for the given session and term
    total_payments = Payment.objects.filter(
        student=student,
        session=session,
        term=term,
        status='completed'
    ).aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')

    # Calculate the new balance (positive for debt, negative for credit)
    new_balance = total_fees - total_payments

    # Get or create the ledger entry and update its balance
    ledger_entry, created = StudentAccountLedger.objects.get_or_create(
        student=student,
        session=session,
        term=term,
        defaults={'balance': new_balance}
    )
    if not created and ledger_entry.balance != new_balance:
        ledger_entry.balance = new_balance
        ledger_entry.save()




def get_debtors_data(term_id=None, session_id=None, category_id=None):
    """
    Refactored to get debtors based on StudentFeeAssignment and StudentPayment models.
    """
    from payments.models import StudentFeeAssignment

    # 1. Get all assigned fees
    assigned_fees_qs = StudentFeeAssignment.objects.all()

    # 2. Filter by term, session, and category if provided
    if term_id:
        assigned_fees_qs = assigned_fees_qs.filter(term__id=term_id)
    if session_id:
        assigned_fees_qs = assigned_fees_qs.filter(session__id=session_id)
    if category_id:
        assigned_fees_qs = assigned_fees_qs.filter(payment_category__id=category_id)

    # 3. Annotate the assigned fees queryset with total payments.
    # We are using a Q object to filter payments correctly within the aggregation.
    assigned_fees_with_payments = assigned_fees_qs.annotate(
        total_paid=Sum(
            'student__payments__amount_received',  # <-- Correct field name here!
            filter=Q(
                student__payments__term=F('term'), 
                student__payments__session=F('session')
            )
        )
    ).annotate(
        balance=ExpressionWrapper(
            F('amount_due') - F('total_paid'), output_field=DecimalField()
        )
    )

    # 4. Filter for only those with a balance due
    debtors_qs = assigned_fees_with_payments.filter(balance__gt=0)
    
    # 5. Format data for the template
    debtors_list = []
    for debtor in debtors_qs:
        debtors_list.append({
            'student_name': debtor.student.get_full_name(),
            'student_class': debtor.student.current_class.name if debtor.student.current_class else 'N/A',
            'term_name': debtor.term.name,
            'session_name': debtor.session.name,
            'amount_due': debtor.amount_due,
            'amount_paid': debtor.total_paid if debtor.total_paid else 0,
            'balance': debtor.balance,
        })
    
    return debtors_list




def get_total_payments_data(start_date_str, end_date_str, term_id, session_id, student_id):
    """
    Retrieves total payments data with various filters.    
    """
    from payments.models import Payment

    payments_query = Payment.objects.filter(status='completed')

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            payments_query = payments_query.filter(payment_date__gte=start_date)
        except ValueError:
            pass # Handle error in view or silently ignore for helper
    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() + timedelta(days=1)
            payments_query = payments_query.filter(payment_date__lt=end_date)
        except ValueError:
            pass # Handle error in view or silently ignore
    if term_id:
        payments_query = payments_query.filter(term__id=term_id)
    if session_id:
        payments_query = payments_query.filter(session__id=session_id)
    if student_id:
        payments_query = payments_query.filter(student__id=student_id)

    # Calculate total original amount by summing the Max original_amount for unique fee types
    unique_fees_original_amounts = payments_query.values(
        'student', 'term', 'session', 'payment_category'
    ).annotate(
        unique_original_amount=Max('original_amount')
    ).aggregate(
        total_unique_original_amount=Sum('unique_original_amount')
    )['total_unique_original_amount'] or Decimal('0.00')

    total_original_amount = unique_fees_original_amounts
    total_amount_received = payments_query.aggregate(total=Sum('amount_received'))['total'] or Decimal('0.00')
    
    total_discount_given_agg = payments_query.aggregate(
        total_fixed_discount=Sum('discount_amount'),
        total_percentage_discount=Sum(F('original_amount') * (F('discount_percentage') / Decimal('100.00')))
    )
    total_discount_given = (total_discount_given_agg['total_fixed_discount'] or Decimal('0.00')) + \
                           (total_discount_given_agg['total_percentage_discount'] or Decimal('0.00'))

    payment_breakdown = payments_query.values(
        'student__first_name', 'student__last_name', 'student__USN',
        'payment_category__name', 'term__name', 'session__name'
    ).annotate(
        sum_amount_received=Sum('amount_received'),
        sum_original=Max('original_amount'), # Use Max for original amount per unique fee in breakdown
        sum_fixed_discount=Sum('discount_amount'),
        sum_percentage_discount=Sum(F('original_amount') * (F('discount_percentage') / Decimal('100.00')))
    ).order_by(
        'student__last_name', 'session__name', 'term__name', 'payment_category__name'
    )
    
    return {
        'total_amount_received': total_amount_received,
        'total_original_amount': total_original_amount,
        'total_discount_given': total_discount_given,
        'payment_breakdown': list(payment_breakdown), # Convert to list for easier passing
    }


def render_to_pdf(template_src, context_dict={}):
    """
    Renders an HTML template to a PDF file using xhtml2pdf.
    """
    template = get_template(template_src)
    html = template.render(context_dict)
    result = BytesIO()
    
    # Define a custom link callback to handle static files
    # This is crucial for images, CSS in PDF
    def link_callback(uri, rel):
        # use settings.STATIC_URL and settings.MEDIA_URL for resolving urls
        if uri.startswith(settings.STATIC_URL):
            path = os.path.join(settings.STATIC_ROOT, uri.replace(settings.STATIC_URL, ""))
        elif uri.startswith(settings.MEDIA_URL):
            path = os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ""))
        else:
            path = os.path.join(settings.BASE_DIR, uri) # For relative paths or absolute file paths
        return path

    pdf = pisa.CreatePDF(
        html,
        dest=result,
        link_callback=link_callback # Pass the link callback
    )
    if not pdf.err:
        return HttpResponse(result.getvalue(), content_type='application/pdf')
    return None # Return None on error


# CREATE PAYMENT HELPER FUNCTION
logger = logging.getLogger(__name__)

# This is the function that needs to be transactional
@transaction.atomic
def create_payment(user, student, form):
    """
    Centralized utility function to handle the creation of a Payment and its related Receipt.
    This function is wrapped in a database transaction to ensure data integrity and accurate calculations.
    """
    # Local imports to prevent circular dependency
    from .models import Payment, Receipt, StudentAccountLedger, StudentFeeAssignment
    
    # CRITICAL FIX: The local definition of generate_receipt_number has been permanently removed.

    try:
        # Get data from the form
        amount_received = form.cleaned_data['amount_received']
        payment_category = form.cleaned_data['payment_category']
        current_session = form.cleaned_data['session']
        current_term = form.cleaned_data['term']
        
        # --- Transaction ID Uniqueness Fix (CRITICAL) ---
        transaction_id_raw = form.cleaned_data.get('transaction_id')
        
        # If the user leaves the field blank (which causes IntegrityError if transaction_id is unique)
        if not transaction_id_raw or transaction_id_raw.strip() == '':
             # Generate a highly unique, non-conflicting placeholder for MANUAL entries
             # This ensures the database's UNIQUE constraint is satisfied.
             unique_placeholder = f"MANUAL-{user.pk}-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
             transaction_id_to_save = unique_placeholder
        else:
            # Use the ID the user provided
            transaction_id_to_save = transaction_id_raw.strip()
        # --- END Transaction ID Fix ---
        
        # --- Recalculating totals for accuracy ---
        # Total due for the current session/term
        total_due_aggr = StudentFeeAssignment.objects.filter(
            student=student,
            session=current_session,
            term=current_term
        ).aggregate(total_due=Sum('amount_due'))
        total_due = total_due_aggr['total_due'] or Decimal('0.00')

        # Total paid for the current session/term (excluding this new payment, as it's not saved yet)
        total_previously_paid_aggr = Payment.objects.filter(
            student=student,
            session=current_session,
            term=current_term,
            status='completed'
        ).aggregate(total_paid=Sum('amount_received'))
        total_previously_paid = total_previously_paid_aggr['total_paid'] or Decimal('0.00')

        # Calculate balances
        balance_before_payment = total_due - total_previously_paid
        balance_after_payment = balance_before_payment - amount_received

        # 1. Create the Payment record
        payment = Payment.objects.create(
            student=student,
            session=current_session,
            term=current_term,
            payment_category=payment_category,
            amount_received=amount_received,
            payment_method=form.cleaned_data['payment_method'],
            # USE THE CLEANED/UNIQUE ID HERE
            transaction_id=transaction_id_to_save,
            payment_date=form.cleaned_data['payment_date'],
            notes=form.cleaned_data.get('notes'),
            recorded_by=user,
            original_amount=total_due,
            balance_before_payment=balance_before_payment,
            balance_after_payment=balance_after_payment,
            status='completed' # Mark as completed to be included in future calculations
        )

        # 2. Update StudentAccountLedger
        ledger, created = StudentAccountLedger.objects.get_or_create(
            student=student,
            session=current_session,
            term=current_term,
            defaults={'balance': total_due} # Initialize balance with total due
        )
        ledger.balance -= amount_received
        ledger.save()
        
        # 3. Create the Receipt record
        # This now correctly calls the UNIQUE-GUARANTEED function from helpers.py
        receipt_number = generate_receipt_number(payment.pk) 
        receipt = Receipt.objects.create(
            payment=payment,
            receipt_number=receipt_number,
            generated_by=user,
            issue_date=timezone.now()
        )

        return {
            'success': True,
            'message': 'Payment and receipt created successfully.',
            'receipt_number': receipt.receipt_number,
            'receipt_id': receipt.pk
        }

    except IntegrityError as e:
        logger.error(f"Database IntegrityError: {e}")
        # The transaction is automatically rolled back due to @transaction.atomic
        return {
            'success': False,
            'message': "A database conflict occurred during payment processing. The transaction was rolled back. Please try again.",
            'receipt_id': None,
            'receipt_number': None
        }

    except Exception as e:
        logger.error(f"An unexpected error occurred in create_payment: {e}")
        return {
            'success': False,
            'message': "An unexpected error occurred. Please contact support.",
            'receipt_id': None,
            'receipt_number': None
        }
