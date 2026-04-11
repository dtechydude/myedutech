from curriculum.models import SchoolIdentity, StandardIdentity
from students.models import Student
# Import your Receipt model correctly
from payments.models import Receipt 

def school_identity(request):
    # 1. Default fallback
    school_info = SchoolIdentity.objects.filter(is_default=True).first() or SchoolIdentity.objects.first()

    resolver_match = request.resolver_match
    student_id = None

    if resolver_match:
        kwargs = resolver_match.kwargs
        
        # A. URLS WITH 'student_id' (ID Cards, Invoices)
        if 'student_id' in kwargs:
            student_id = kwargs.get('student_id')
        
        # B. URLS WITH 'receipt_id' or 'receipt_pk' (Receipts)
        elif 'receipt_id' in kwargs or 'receipt_pk' in kwargs:
            r_id = kwargs.get('receipt_id') or kwargs.get('receipt_pk')
            # Changed logic: Accessing student through the 'payment' relation
            receipt = Receipt.objects.filter(pk=r_id).select_related('payment').first()
            if receipt and receipt.payment:
                # Assuming the Payment model has the 'student' field
                student_id = receipt.payment.student.id

    # C. LOGGED-IN STUDENT
    if not student_id and request.user.is_authenticated:
        if hasattr(request.user, 'student') and request.user.student:
            student_id = request.user.student.id

    # 4. Final ID Lookup and Identity Swap
    if student_id:
        try:
            student = Student.objects.filter(pk=student_id).only('current_class').first()
            if student and student.current_class:
                # Use current_class.id directly
                standard_id = getattr(student.current_class, 'id', student.current_class)
                mapping = StandardIdentity.objects.filter(standard_id=standard_id).first()
                if mapping:
                    school_info = mapping.school_identity
        except Exception:
            pass 

    return {'school_info': school_info}