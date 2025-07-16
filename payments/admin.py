# student_management_app/admin.py (or payments/admin.py if you created a new app)

from django.contrib import admin
from .models import Payment, Receipt, PaymentCategory, StudentAccountLedger, CategoryFee # Import CategoryFee
from decimal import Decimal
from import_export.admin import ImportExportModelAdmin # Import ImportExportModelAdmin
from import_export import resources # Import resources
from curriculum.models import Term, Session

# Define a Resource for the Payment model
class PaymentResource(resources.ModelResource):
    class Meta:
        model = Payment
        # Define fields to include in import/export.
        # You can customize this list based on your needs.
        fields = (
            'id', 'student__first_name', 'student__last_name', 'student__USN',
            'original_amount', 'discount_amount', 'discount_percentage',
            'amount_received', 'payment_date', 'status', 'payment_method',
            'transaction_id', 'notes',
            'term__name', 'session__name', 'payment_category__name',
            'is_installment', 'installment_number', 'total_installments',
            'recorded_by__username', # Or recorded_by__first_name, recorded_by__last_name
        )
        # Define fields to exclude from import/export if necessary
        # exclude = ('id',) # Example: exclude 'id' if you want new IDs on import
        # Define fields that can be imported
        import_id_fields = ('id',) # Use 'id' for updating existing records on import
        # Set skip_unchanged to True to skip rows that haven't changed during import
        report_skipped = True
        # Set report_skipped to True to report rows that were skipped during import
        skip_unchanged = True


# Register your models here.

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

@admin.register(PaymentCategory)
class PaymentCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

@admin.register(CategoryFee) # Register the new CategoryFee model
class CategoryFeeAdmin(admin.ModelAdmin):
    list_display = ('payment_category', 'term', 'session', 'fee_name', 'amount_due') # Added fee_name
    list_filter = ('payment_category', 'term', 'session')
    search_fields = ('payment_category__name', 'term__name', 'session__name', 'fee_name') # Added fee_name
    raw_id_fields = ('payment_category', 'term', 'session') # Use raw_id_fields for FKs
    ordering = ('-session__name', '-term__name', 'payment_category__name', 'fee_name') # Added fee_name


@admin.register(StudentAccountLedger)
class StudentAccountLedgerAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'session', 'balance', 'last_updated')
    list_filter = ('term', 'session')
    search_fields = ('student__first_name', 'student__last_name', 'student__USN')
    readonly_fields = ('balance', 'last_updated') # Balance is managed by Payment save method

    fieldsets = (
        (None, {
            'fields': ('student', 'term', 'session', 'balance')
        }),
        ('Audit Information', {
            'fields': ('last_updated',),
            'classes': ('collapse',)
        }),
    )

@admin.register(Payment)
class PaymentAdmin(ImportExportModelAdmin, admin.ModelAdmin): # Inherit from ImportExportModelAdmin
    resource_class = PaymentResource # Link the resource class
    list_display = (
        'student', 'original_amount', 'discount_amount', 'discount_percentage',
        'net_amount_due', 'amount_received', 'payment_date', 'status',
        'payment_method', 'term', 'session', 'payment_category',
        'is_installment', 'installment_number', 'recorded_by'
    )
    list_filter = (
        'status', 'payment_method', 'term', 'session', 'payment_category',
        'is_installment', 'recorded_by'
    )
    search_fields = (
        'student__first_name', 'student__last_name', 'student__USN',
        'transaction_id', 'notes'
    )
    date_hierarchy = 'payment_date'
    raw_id_fields = ('student', 'term', 'session', 'payment_category', 'recorded_by') # Use raw_id_fields for FKs to improve performance with many related objects

    # Fields to display in the form for adding/editing payments
    fieldsets = (
        (None, {
            'fields': ('student', ('term', 'session'), 'payment_category')
        }),
        ('Payment Details', {
            'fields': (
                'original_amount', # This field is now optional for staff to override/set
                ('discount_amount', 'discount_percentage'),
                'amount_received', # This is the amount actually paid/received
                ('payment_method', 'transaction_id'),
                'status',
                'notes',
            )
        }),
        ('Installment Information', {
            'fields': ('is_installment', ('installment_number', 'total_installments')),
            'classes': ('collapse',) # Collapse this section by default
        }),
        ('Audit Information', {
            'fields': ('recorded_by',),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        # Optimize queryset by selecting related objects
        return super().get_queryset(request).select_related(
            'student', 'term', 'session', 'payment_category', 'recorded_by'
        )

    # Custom method to display net amount due in list_display
    def net_amount_due(self, obj):
        return obj.net_amount_due
    net_amount_due.short_description = 'Net Due (After Discount)'


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'payment', 'issue_date', 'generated_by')
    list_filter = ('issue_date', 'generated_by')
    search_fields = ('receipt_number', 'payment__student__first_name', 'payment__student__last_name')
    raw_id_fields = ('payment', 'generated_by')
    readonly_fields = ('receipt_number', 'issue_date') # Receipt number and issue date are auto-generated

    fieldsets = (
        (None, {
            'fields': ('payment', 'receipt_number', 'issue_date')
        }),
        ('Audit Information', {
            'fields': ('generated_by',),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        # Optimize queryset by selecting related objects
        return super().get_queryset(request).select_related(
            'payment__student', 'generated_by'
        )
