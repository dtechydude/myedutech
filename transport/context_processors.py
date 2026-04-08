# from curriculum.models import SchoolIdentity  # Replace 'your_app' with the app name where SchoolIdentity is located

# def school_identity(request):
#     try:
#         school_info = SchoolIdentity.objects.first()
#     except SchoolIdentity.DoesNotExist:
#         school_info = None

#     return {'school_info': school_info}
# import re
# from curriculum.models import SchoolIdentity, StandardIdentity
# from students.models import Student 

# def school_identity(request):
#     # 1. Start with Fallback
#     school_info = SchoolIdentity.objects.filter(is_default=True).first() or SchoolIdentity.objects.first()

#     # 2. Extract Student ID from Kwargs or the raw Path
#     student_id = None
#     resolver_match = request.resolver_match
    
#     if resolver_match and 'student_id' in resolver_match.kwargs:
#         student_id = resolver_match.kwargs.get('student_id')
#     else:
#         # If resolver_match fails, manually grab the ID from the URL path
#         # Pattern looks for /report-cards/NUMBER/
#         path_match = re.search(r'/report-cards/(\d+)/', request.path)
#         if path_match:
#             student_id = path_match.group(1)

#     # 3. If we have a student_id, find the mapped identity
#     if student_id:
#         try:
#             student = Student.objects.filter(pk=student_id).only('current_class').first()
#             if student and student.current_class:
#                 # We use .current_class_id to avoid an extra database hit
#                 standard_id = getattr(student.current_class, 'id', student.current_class)
                
#                 mapping = StandardIdentity.objects.filter(standard_id=standard_id).select_related('school_identity').first()
#                 if mapping:
#                     school_info = mapping.school_identity
#         except Exception:
#             pass # Keep default school_info if anything errors out

#         print(f"DEBUG: Current School Info Name: {school_info.name} | Label: {school_info.identity_label}")

#     return {'school_info': school_info}


# from curriculum.models import SchoolIdentity, StandardIdentity
# from students.models import Student
# from payments.models import Receipt  # Adjust the app name 'payments' to your actual app
# import re

# def school_identity(request):
#     # 1. SET THE GLOBAL FALLBACK (The 'Main' Identity)
#     school_info = SchoolIdentity.objects.filter(is_default=True).first() or SchoolIdentity.objects.first()

#     resolver_match = request.resolver_match
#     student_id = None

#     if resolver_match:
#         kwargs = resolver_match.kwargs
        
#         # A. URLS WITH 'student_id' (ID Cards, Student Invoice)
#         if 'student_id' in kwargs:
#             student_id = kwargs.get('student_id')
        
#         # B. URLS WITH 'receipt_id' or 'receipt_pk' (Receipts)
#         elif 'receipt_id' in kwargs or 'receipt_pk' in kwargs:
#             r_id = kwargs.get('receipt_id') or kwargs.get('receipt_pk')
#             receipt = Receipt.objects.filter(pk=r_id).select_related('student').first()
#             if receipt:
#                 student_id = receipt.student.id

#         # C. LOGGED-IN STUDENT (For 'my-invoice/')
#         elif request.user.is_authenticated and hasattr(request.user, 'is_student') and request.user.is_student:
#             # Assumes your User model has a relationship to Student
#             # Update 'student_profile' to the actual related_name on your User model
#             if hasattr(request.user, 'student_profile'):
#                 student_id = request.user.student.id

#     # 4. IF WE FOUND A STUDENT, SWAP THE IDENTITY
#     if student_id:
#         try:
#             student = Student.objects.filter(pk=student_id).only('current_class').first()
#             if student and student.current_class:
#                 # Identify the Standard ID
#                 standard_id = getattr(student.current_class, 'id', student.current_class)
                
#                 # Check for a specific mapping
#                 mapping = StandardIdentity.objects.filter(standard_id=standard_id).first()
#                 if mapping:
#                     school_info = mapping.school_identity
#         except Exception:
#             pass # Stay with fallback on any error

#     return {'school_info': school_info}


# from curriculum.models import SchoolIdentity, StandardIdentity
# from students.models import Student
# # Replace 'finance' with the actual app name where your Receipt model lives
# from payments.models import Receipt 

# def school_identity(request):
#     # 1. Start with the Fallback (The 'Main' Identity)
#     school_info = SchoolIdentity.objects.filter(is_default=True).first() or SchoolIdentity.objects.first()

#     resolver_match = request.resolver_match
#     student_id = None

#     if resolver_match:
#         kwargs = resolver_match.kwargs
        
#         # A. URLS WITH 'student_id' (ID Cards, Student Invoice)
#         if 'student_id' in kwargs:
#             student_id = kwargs.get('student_id')
        
#         # B. URLS WITH 'receipt_id' or 'receipt_pk' (Receipts)
#         elif 'receipt_id' in kwargs or 'receipt_pk' in kwargs:
#             r_id = kwargs.get('receipt_id') or kwargs.get('receipt_pk')
#             receipt = Receipt.objects.filter(pk=r_id).select_related('student').first()
#             if receipt:
#                 student_id = receipt.student.id

#     # C. LOGGED-IN STUDENT (For 'my-invoice/' or Dashboards)
#     # If no ID was in the URL, check if the current user is a student
#     if not student_id and request.user.is_authenticated:
#         if hasattr(request.user, 'student') and request.user.student:
#             student_id = request.user.student.id

#     # 4. IF WE HAVE A STUDENT ID, FIND THE MAPPED IDENTITY
#     if student_id:
#         try:
#             # We fetch the student to get their 'current_class'
#             student = Student.objects.filter(pk=student_id).only('current_class').first()
#             if student and student.current_class:
#                 # Get the ID of the Standard
#                 standard_id = getattr(student.current_class, 'id', student.current_class)
                
#                 # Look for the mapping to a specific logo/name
#                 mapping = StandardIdentity.objects.filter(standard_id=standard_id).first()
#                 if mapping:
#                     school_info = mapping.school_identity
#         except Exception:
#             pass # Stay with fallback on any error

#     return {'school_info': school_info}

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