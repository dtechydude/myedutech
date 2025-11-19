# your_app/admin.py
from django.contrib import admin, messages
from decimal import Decimal
from django.db.models import Sum
from .models import Payment, PaymentNotification, StudentFeeAssignment, PaymentCategory, Receipt, BankDetail, StudentAccountLedger


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'payment_category', 'term', 'session',
        'original_amount', 'amount_received', 'balance_after_payment',
        'status', 'payment_date', 'recorded_by'
    )
    list_filter = (
        'status', 'payment_date', 'payment_category', 'term', 'session', 'payment_method', 'student__current_class',
    )
    search_fields = (
        'student__user__first_name', 'student__user__last_name', 'transaction_id', 'student__USN'
    )
    raw_id_fields = ['student', 'payment_category', 'session', 'term']
    
    # These fields will be automatically calculated and are read-only to prevent manual changes.
    readonly_fields = ('original_amount', 'balance_before_payment', 'balance_after_payment')

    fieldsets = (
        (None, {
            'fields': ('student', ('payment_category', 'term', 'session'))
        }),
        ('Payment Details', {
            # Add 'payment_date' to the list of fields here
            'fields': ('amount_received', 'payment_date', 'payment_method', 'transaction_id', 'status', 'notes',
                       'original_amount', 'balance_before_payment', 'balance_after_payment')
        }),
        ('Audit Information', {
            'fields': ('recorded_by', 'confirm_payment')
        }),
    )

    def save_model(self, request, obj, form, change):
        # Set recorded_by if it's a new object
        if not obj.pk and not obj.recorded_by:
            obj.recorded_by = request.user

        # Fetch the total amount due for the student's fees.
        total_due_aggr = StudentFeeAssignment.objects.filter(
            student=obj.student,
            term=obj.term,
            session=obj.session
        ).aggregate(total_due=Sum('amount_due'))
        
        total_due = total_due_aggr['total_due'] or Decimal('0.00')
        obj.original_amount = total_due

        # Calculate total payments made by the student before this one.
        total_paid_aggr = Payment.objects.filter(
            student=obj.student,
            term=obj.term,
            session=obj.session,
            status='completed'
        ).exclude(pk=obj.pk).aggregate(total_paid=Sum('amount_received'))
        
        total_previously_paid = total_paid_aggr['total_paid'] or Decimal('0.00')

        # Calculate the balance before and after this new payment.
        balance_before = total_due - total_previously_paid
        obj.balance_before_payment = balance_before
        
        balance_after = balance_before - obj.amount_received
        obj.balance_after_payment = balance_after
        
        # Check if the payment status is not completed, then set it to completed to ensure it's recorded
        if obj.status != 'completed':
            obj.status = 'completed'

        # Now, save the object with all the calculated values.
        super().save_model(request, obj, form, change)

# @admin.register(PaymentCategory)
# class PaymentCategoryAdmin(admin.ModelAdmin):
#     list_display = ('name',)
#     search_fields = ('name',)

@admin.register(PaymentCategory)
class PaymentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)      

@admin.register(BankDetail)
class BankDetailAdmin(admin.ModelAdmin):
    list_display = ('acc_name', 'acc_number', 'bank_name')
    search_fields = ('acc_name','acc_number', 'bank_name')
    list_filter = ('bank_name',)

# @admin.register(CategoryFee)
# class CategoryFeeAdmin(admin.ModelAdmin):
#     list_display = ('fee_name', 'payment_category', 'term', 'session', 'amount_due')
#     list_filter = ('payment_category', 'term', 'session')
#     search_fields = ('fee_name', 'payment_category__name', 'term__name', 'session__name')
#     raw_id_fields = ['payment_category', 'term', 'session']

@admin.register(StudentAccountLedger)
class StudentAccountLedgerAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'session', 'balance', 'last_updated')
    list_filter = ('term', 'session', 'last_updated')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')
    readonly_fields = ('balance', 'last_updated') 

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'payment', 'issue_date', 'generated_by')
    list_filter = ('issue_date', 'generated_by')
    search_fields = ('receipt_number', 'payment__student__first_name', 'payment__student__last_name')
    readonly_fields = ('receipt_number', 'issue_date', 'generated_by', 'payment')

@admin.register(StudentFeeAssignment)
class StudentFeeAssignmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'payment_category', 'term', 'session', 'amount_due')
    list_filter = ('term', 'session', 'payment_category', 'student__current_class')
    search_fields = ('student__USN', 'student__first_name', 'student__last_name', 'payment_category__name')
    raw_id_fields = ('student', 'payment_category', 'term', 'session')

# @admin.register(ClassFeeTemplate)
# class ClassFeeTemplateAdmin(admin.ModelAdmin):
#     # ... your existing admin configuration ...
#     autocomplete_fields = ['payment_category'] # This now works



# Payment Notification Admin
@admin.register(PaymentNotification)
class PaymentNotificationAdmin(admin.ModelAdmin):
    # Fields displayed in the list view
    list_display = (
        'student_name', 
        'amount_paid', 
        'payment_method', 
        'bank_account',      # ADDED
        'payment_date', 
        'transaction_id', 
        'notified_by', 
        'status', 
        'submission_date', 
    )
    
    # Fields that can be filtered
    list_filter = (
        'payment_method', 
        'bank_account',      # ADDED
        'status', 
        'session', 
        'term', 
        'submission_date'
    )
    
    # Fields that can be searched
    search_fields = (
        'student__user__first_name', 
        'student__user__last_name', 
        'transaction_id', 
        'notes',
        'bank_account__bank_name',  # CORRECTED to use 'bank_name'
        'bank_account__acc_number', # CORRECTED to use 'acc_number'
    )
    
    # Grouping fields in the detail view
    fieldsets = (
        ('Status', {
            'fields': ('status',),
        }),
        ('Student and Amount', {
            'fields': ('student', 'amount_paid')
        }),
        ('Payment Details', {
            'fields': (
                'payment_method', 
                'bank_account',      # ADDED
                'transaction_id', 
                'payment_date', 
                'notes'
            )
        }),
        ('Academic Period', {
            'fields': ('session', 'term')
        }),
        ('Audit Trail', {
            'fields': ('notified_by', 'submission_date')
        }),
    )

    # Make system info fields read-only
    readonly_fields = ('notified_by', 'submission_date', 'bank_account')
    
    # Custom method to display student's full name in list view
    def student_name(self, obj):
        return obj.student.user.get_full_name()
    student_name.admin_order_field = 'student__user__last_name'
    student_name.short_description = 'Student'
    
    # Retained formatted_status method 
    def formatted_status(self, obj):
        if obj.status == 'PENDING':
            return format_html('<span style="color:orange; font-weight:bold;">{}</span>', obj.get_status_display())
        elif obj.status == 'PROCESSED':
            return format_html('<span style="color:green; font-weight:bold;">{}</span>', obj.get_status_display())
        else:
            return obj.get_status_display()
