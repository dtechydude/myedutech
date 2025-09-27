# payments/helpers.py
from django.utils import timezone

def generate_receipt_number(payment_id):
    padded_id = str(payment_id).zfill(6) 
    date_prefix = timezone.now().strftime('%Y')
    return f"R-{date_prefix}-{padded_id}" 