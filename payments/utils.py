# payments/utils.py
from decimal import Decimal
from django.db.models import Sum, Max, F
from students.models import Student
from curriculum.models import Term, Session
from payments.models import Payment, StudentAccountLedger # Assuming Fee is related to CategoryFee/StudentFee
from datetime import datetime, timedelta
import os
from io import BytesIO
from django.http import HttpResponse
from django.template.loader import get_template
from django.conf import settings
from xhtml2pdf import pisa

# def get_debtors_data(term_id, session_id):
#     """
#     Retrieves debtor data based on StudentAccountLedger.
#     """
#     debtors_query = StudentAccountLedger.objects.filter(balance__gt=0).select_related('student', 'term', 'session')

#     if term_id:
#         debtors_query = debtors_query.filter(term__id=term_id)
#     if session_id:
#         debtors_query = debtors_query.filter(session__id=session_id)

#     debtors = list(debtors_query.order_by('student__last_name', 'session__name', 'term__name'))

#     return debtors

# def get_debtors_data(term_id=None, session_id=None):
#     """
#     Retrieves debtor data, calculating total amount due, paid, and balance.
#     Returns a list of dictionaries, where each dictionary represents a debtor.
#     """
#     students_with_accounts = StudentAccountLedger.objects.select_related(
#         'student__user', 'student__student_class', 'term', 'session'
#     ).annotate(
#         total_due=Sum(F('fee__amount'), filter=F('transaction_type') == 'debit'),
#         total_paid=Sum(F('amount'), filter=F('transaction_type') == 'credit')
#     ).order_by('student__user__last_name', 'student__user__first_name')

#     if term_id:
#         students_with_accounts = students_with_accounts.filter(term_id=term_id)
#     if session_id:
#         students_with_accounts = students_with_accounts.filter(session_id=session_id)

#     debtors_list = []
#     for account_entry in students_with_accounts:
#         # Calculate balance for this specific account entry
#         balance = (account_entry.total_due or 0) - (account_entry.total_paid or 0)

#         # Only include if there's an actual balance or if it's explicitly a "debtor" report
#         # (you might want to adjust this logic based on how you define a "debtor")
#         if balance > 0: # Only show actual debtors with positive balance
#             debtors_list.append({
#                 'student_name': account_entry.student.user.get_full_name(),
#                 'student_class': account_entry.student.student_class.name if account_entry.student.student_class else 'N/A',
#                 'total_amount_due': account_entry.total_due or 0,
#                 'amount_paid': account_entry.total_paid or 0,
#                 'balance': balance,
#                 # You might add other relevant fields here
#             })
#     return debtors_list


# Assuming your StudentAccountLedger model has fields like:
# - student (ForeignKey to Student)
# - term (ForeignKey to Term)
# - session (ForeignKey to Session)
# - amount (DecimalField)
# - transaction_type (CharField, e.g., 'debit' for fees/charges, 'credit' for payments)
# - description (CharField, e.g., 'School Fees', 'Tuition', 'Payment Received')

# def get_debtors_data(term_id=None, session_id=None):
#     """
#     Retrieves debtor data, calculating total amount due, paid, and balance
#     based on the transaction_type in StudentAccountLedger.
#     Returns a list of dictionaries, where each dictionary represents a debtor.
#     """
#     # Start with all distinct students that have ledger entries for the given term/session
#     # We group by student, term, and session to get totals per student per academic period.
#     # We also select related student, user, and class for efficient access later.
#     ledger_entries = StudentAccountLedger.objects.select_related(
#         'student__user',
#         'student__current_class', # Assuming student_class is a ForeignKey on Student
#         'term',
#         'session'
#     )

#     if term_id:
#         ledger_entries = ledger_entries.filter(term_id=term_id)
#     if session_id:
#         ledger_entries = ledger_entries.filter(session_id=session_id)

#     # Annotate total debits (fees/charges) and total credits (payments) for each student/term/session combination
#     students_data = ledger_entries.values(
#         'student__id',
#         'student__user__first_name',
#         'student__user__last_name',
#         'student__current_class__name', # Access class name through student relationship
#         'term__name',
#         'session__name'
#     ).annotate(
#         total_fees_due=Sum('amount', filter=F('transaction_type') == 'debit'),
#         total_payments_made=Sum('amount', filter=F('transaction_type') == 'credit')
#     ).order_by(
#         'student__user__last_name',
#         'student__user__first_name',
#         'session__name',
#         'term__name'
#     )

#     debtors_list = []
#     for entry_data in students_data:
#         total_due = entry_data['total_fees_due'] or 0
#         amount_paid = entry_data['total_payments_made'] or 0
#         balance = total_due - amount_paid

#         # Only include if there's an actual balance due (or you can include all for a full ledger report)
#         if balance > 0: # This filters for actual debtors
#             debtors_list.append({
#                 'student_name': f"{entry_data['student__user__first_name']} {entry_data['student__user__last_name']}",
#                 'student_class': entry_data['student__current_class__name'] if entry_data['student__current_class__name'] else 'N/A',
#                 'term_name': entry_data['term__name'],
#                 'session_name': entry_data['session__name'],
#                 'total_amount_due': total_due,
#                 'amount_paid': amount_paid,
#                 'balance': balance,
#             })
#     return debtors_list


def get_debtors_data(term_id=None, session_id=None):
    """
    Retrieves debtor data based on the 'balance' field in StudentAccountLedger.
    Returns a list of dictionaries, where each dictionary represents a debtor
    with an outstanding balance.
    """
    # Start with all StudentAccountLedger entries
    # Filter for entries where the balance is greater than 0 (i.e., they owe money)
    debtor_accounts = StudentAccountLedger.objects.filter(balance__gt=0).select_related(
        'student__user',
        'student__current_class', # Assuming student_class is a ForeignKey on Student
        'term',
        'session'
    )

    if term_id:
        debtor_accounts = debtor_accounts.filter(term_id=term_id)
    if session_id:
        debtor_accounts = debtor_accounts.filter(session_id=session_id)

    # Order the results
    debtor_accounts = debtor_accounts.order_by(
        'student__user__last_name',
        'student__user__first_name',
        'session__name',
        'term__name'
    )

    debtors_list = []
    for account_entry in debtor_accounts:
        debtors_list.append({
            'student_name': account_entry.student.get_full_name(),
            'student_class': account_entry.student.current_class.name if account_entry.student.current_class else 'N/A',
            'term_name': account_entry.term.name if account_entry.term else 'N/A',
            'session_name': account_entry.session.name if account_entry.session else 'N/A',
            'balance': account_entry.balance,
            # If your StudentAccountLedger model only stores balance,
            # you might not have 'total_amount_due' or 'amount_paid' readily available here.
            # These would need to be calculated from a different model (e.g., individual Fee and Payment models)
            # or pre-calculated and stored if your ledger is a summary.
            # For now, we'll omit them if they aren't direct fields.
        })
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
