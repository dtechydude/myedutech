# payments/utils.py
from decimal import Decimal
from django.db.models import Sum, Max, F
from students.models import Student
from curriculum.models import Term, Session
from payments.models import Payment, StudentAccountLedger, PaymentCategory, StudentFee# Assuming Fee is related to CategoryFee/StudentFee
from datetime import datetime, timedelta
import os
from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from django.conf import settings
from xhtml2pdf import pisa
from django.db.models import Prefetch, Q




def get_debtors_data(term_id=None, session_id=None, category_id=None):
    """
    Retrieves debtor data by querying the StudentAccountLedger model and aggregating.
    This function returns a list of dictionaries.
    """
    
    # Start by filtering StudentAccountLedger for debtors
    debtor_accounts = StudentAccountLedger.objects.filter(
        balance__gt=0
    )
    
    # Apply filters from the GET request
    if term_id:
        debtor_accounts = debtor_accounts.filter(term_id=term_id)
    if session_id:
        debtor_accounts = debtor_accounts.filter(session_id=session_id)
        
    # Use select_related for the direct foreign keys on the StudentAccountLedger model
    debtor_accounts = debtor_accounts.select_related(
        'student__user',
        'student__current_class',
        'term',
        'session'
    )
    
    # Prefetch the related payments from the Student model
    payments_prefetch_queryset = Payment.objects.filter(status='completed')
    if category_id:
        # If a category is filtered, we need to filter payments by that category
        payments_prefetch_queryset = payments_prefetch_queryset.filter(payment_category_id=category_id)
        
    # Now, prefetch the payments from the student object related to the ledger
    debtor_accounts = debtor_accounts.prefetch_related(
        Prefetch(
            'student__payments', 
            queryset=payments_prefetch_queryset.select_related('payment_category'),
            to_attr='relevant_payments_for_student'
        )
    )

    # Convert the QuerySet to a list of dictionaries for easier template rendering
    debtors_list = []
    
    for account in debtor_accounts:
        # It's better to calculate the balance for the specific category here if a category is filtered
        if category_id:
            # We need to get the specific student fee for this category, term, and session.
            try:
                # Use the 'student_fees' related_name you have on the model
                student_fee_record = account.student.student_fees.get(
                    category_fee__payment_category_id=category_id,
                    term=account.term,
                    session=account.session
                )
                total_charges_for_category = student_fee_record.amount_due
            # CORRECTED: Catch the specific exception from the model
            except StudentFee.DoesNotExist:
                total_charges_for_category = Decimal('0.00')

            # Now sum up payments for this category
            total_paid_for_category = sum(
                p.amount_received for p in account.student.relevant_payments_for_student
                if p.payment_category_id == int(category_id) and p.term_id == account.term_id and p.session_id == account.session_id
            )
            
            outstanding_balance = total_charges_for_category - total_paid_for_category
            
            # If the outstanding balance is zero or less, we don't want to show this record
            if outstanding_balance <= 0:
                continue
            
            # Get the category name for display
            category_name = PaymentCategory.objects.get(pk=category_id).name
        else:
            # No category filter, use the balance from the ledger
            outstanding_balance = account.balance
            category_name = "All Categories"
            
        debtors_list.append({
            'student_name': account.student.get_full_name(),
            'student_class': account.student.current_class.name if account.student.current_class else 'N/A',
            'term_name': account.term.name,
            'session_name': account.session.name,
            'balance': outstanding_balance,
            'payment_category_name': category_name,
        })
        
    # Sort the list of dictionaries
    debtors_list.sort(key=lambda x: (x['student_name'], x['session_name'], x['term_name']))
    
    return debtors_list





def get_total_payments_data(start_date_str, end_date_str, term_id, session_id, student_id):
    """
    Retrieves total payments data with various filters.
    """
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
