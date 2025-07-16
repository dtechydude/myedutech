# payments/admin.py

from django.contrib import admin
from django.contrib import messages
from decimal import Decimal
from .models import Payment, PaymentCategory, Term, Session, StudentAccountLedger, CategoryFee, Receipt
from students.models import Student # Assuming Student model is in 'students' app

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    # Fields to display in the list view of the admin
    list_display = (
        'student', 'payment_category', 'term', 'session',
        'original_amount', 'amount_received', 'balance_after_payment',
        'payment_date', 'status', 'recorded_by'
    )
    # Fields that can be filtered in the right sidebar of the admin list view
    list_filter = (
        'status', 'payment_category', 'term', 'session', 'payment_method', 'payment_date'
    )
    # Fields that can be searched using the search bar in the admin list view
    search_fields = (
        'student__first_name', 'student__last_name', 'student__student_id',
        'transaction_id', 'notes'
    )
    # Fields to make read-only in the add/change form.
    # original_amount is made read-only because its value will be derived automatically.
    readonly_fields = ('balance_before_payment', 'balance_after_payment', 'original_amount', 'payment_date')

    # Define the layout and fields shown in the add/change form
    fieldsets = (
        (None, {
            'fields': ('student', ('payment_category', 'term', 'session'), 'original_amount')
        }),
        ('Payment Details', {
            'fields': ('amount_received', 'payment_method', 'transaction_id', 'status', 'notes')
        }),
        ('Discount Information', {
            'fields': ('discount_amount', 'discount_percentage')
        }),
        ('Installment Details', {
            'fields': ('is_installment', ('installment_number', 'total_installments'))
        }),
        ('Balance Information (Auto-calculated)', {
            'description': 'These fields are automatically calculated and cannot be edited directly.',
            'fields': ('balance_before_payment', 'balance_after_payment')
        }),
        ('Audit Information', {
            'fields': ('recorded_by',) # payment_date is auto_now_add, so it's set on creation
        }),
    )

    # Override the save_model method to set original_amount and recorded_by automatically
    def save_model(self, request, obj, form, change):
        # Set 'recorded_by' to the current logged-in staff user if it's not already set
        if not obj.recorded_by and request.user.is_staff:
            obj.recorded_by = request.user

        # Fetch the CategoryFee based on the selected payment_category, term, and session
        payment_category = obj.payment_category
        term = obj.term
        session = obj.session

        if payment_category and term and session:
            # Try to find a matching CategoryFee
            category_fee = CategoryFee.objects.filter(
                payment_category=payment_category,
                term=term,
                session=session
            ).first()
            
            if category_fee:
                # If a matching CategoryFee is found, set original_amount from its amount_due
                obj.original_amount = category_fee.amount_due
            else:
                # If no matching CategoryFee, set original_amount to 0 and show a warning.
                # This ensures original_amount is always a Decimal for calculations.
                obj.original_amount = Decimal('0.00')
                messages.warning(request, "No matching Category Fee found for the selected Category, Term, and Session. Original Amount has been set to 0.00. Please define a Category Fee for this combination if it's an error.")
        else:
            # If essential related fields are missing, ensure original_amount is also 0
            obj.original_amount = Decimal('0.00')
            messages.warning(request, "Payment Category, Term, or Session not fully selected. Original Amount has been set to 0.00.")

        # Call the original save_model method to save the object with the updated original_amount
        super().save_model(request, obj, form, change)

@admin.register(PaymentCategory)
class PaymentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

# @admin.register(Term)
# class TermAdmin(admin.ModelAdmin):
#     list_display = ('name', 'start_date', 'end_date')
#     search_fields = ('name',)
#     list_filter = ('start_date', 'end_date')

# @admin.register(Session)
# class SessionAdmin(admin.ModelAdmin):
#     list_display = ('name', 'start_date', 'end_date')
#     search_fields = ('name',)
#     list_filter = ('start_date', 'end_date')

@admin.register(CategoryFee)
class CategoryFeeAdmin(admin.ModelAdmin):
    list_display = ('fee_name', 'payment_category', 'term', 'session', 'amount_due')
    list_filter = ('payment_category', 'term', 'session')
    search_fields = ('fee_name', 'payment_category__name', 'term__name', 'session__name')

@admin.register(StudentAccountLedger)
class StudentAccountLedgerAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'session', 'balance', 'last_updated')
    list_filter = ('term', 'session', 'last_updated')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')
    readonly_fields = ('balance', 'last_updated') # Balance is auto-calculated

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'payment', 'issue_date', 'generated_by')
    list_filter = ('issue_date', 'generated_by')
    search_fields = ('receipt_number', 'payment__student__first_name', 'payment__student__last_name')
    readonly_fields = ('receipt_number', 'issue_date', 'generated_by', 'payment') # Receipt details are generated, not manually edited
