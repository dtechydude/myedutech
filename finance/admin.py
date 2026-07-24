# finance/admin.py
from django.contrib import admin
from django.utils.html import format_html

try:
    from import_export.admin import ImportExportModelAdmin as BaseModelAdmin
except ImportError:  # graceful fallback if django-import-export isn't installed
    BaseModelAdmin = admin.ModelAdmin

from .models import (
    BankAccount, FeeCategory, FeeStructure, Invoice, InvoiceItem, Payment, Receipt,
    StudentAccountLedger, StudentLedgerEntry, PaymentNotification,
    ExpenseCategory, Vendor, Expense, StudentDiscount, StudentFeeException,
    InstallmentPlan, Installment,
)


@admin.register(BankAccount)
class BankAccountAdmin(BaseModelAdmin):
    list_display = ('bank_name', 'account_number', 'account_name', 'is_primary', 'is_active')
    list_filter = ('bank_name', 'is_active', 'is_primary')
    search_fields = ('account_name', 'account_number', 'bank_name')


@admin.register(FeeCategory)
class FeeCategoryAdmin(BaseModelAdmin):
    list_display = ('name', 'category_type', 'is_active')
    list_filter = ('category_type', 'is_active')
    search_fields = ('name',)


@admin.register(FeeStructure)
class FeeStructureAdmin(BaseModelAdmin):
    list_display = ('fee_category', 'student_class', 'term', 'session', 'amount', 'is_mandatory', 'due_date')
    list_filter = ('term', 'session', 'fee_category', 'student_class', 'is_mandatory')
    search_fields = ('fee_category__name', 'label', 'student_class__name')
    raw_id_fields = ('student_class', 'fee_category', 'term', 'session')


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0
    autocomplete_fields = ['fee_category']
    readonly_fields = ('original_amount', 'discount_amount', 'applied_discount')


@admin.register(StudentDiscount)
class StudentDiscountAdmin(BaseModelAdmin):
    list_display = ('student', 'fee_category', 'term', 'session', 'discount_type', 'value', 'reason',
                     'is_active', 'approved_by')
    list_filter = ('discount_type', 'is_active', 'fee_category', 'term', 'session')
    search_fields = ('student__first_name', 'student__last_name', 'reason')
    raw_id_fields = ('student',)

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.approved_by:
            obj.approved_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(StudentFeeException)
class StudentFeeExceptionAdmin(BaseModelAdmin):
    list_display = ('student', 'fee_structure', 'action', 'reason', 'created_by', 'created_at')
    list_filter = ('action', 'fee_structure__term', 'fee_structure__session', 'fee_structure__fee_category')
    search_fields = ('student__first_name', 'student__last_name', 'reason')
    raw_id_fields = ('student', 'fee_structure')

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class InstallmentInline(admin.TabularInline):
    model = Installment
    extra = 0


@admin.register(InstallmentPlan)
class InstallmentPlanAdmin(BaseModelAdmin):
    list_display = ('invoice', 'created_by', 'created_at', 'installment_count')
    search_fields = ('invoice__invoice_number', 'invoice__student__first_name', 'invoice__student__last_name')
    raw_id_fields = ('invoice',)
    inlines = [InstallmentInline]

    def installment_count(self, obj):
        return obj.installments.count()
    installment_count.short_description = "Installments"


@admin.register(Invoice)
class InvoiceAdmin(BaseModelAdmin):
    list_display = ('invoice_number', 'student', 'term', 'session', 'total_amount', 'total_paid',
                     'balance', 'status', 'issue_date', 'due_date')
    list_filter = ('status', 'term', 'session')
    search_fields = ('invoice_number', 'student__first_name', 'student__last_name', 'student__USN')
    raw_id_fields = ('student',)
    readonly_fields = ('invoice_number', 'created_at', 'updated_at')
    inlines = [InvoiceItemInline]
    date_hierarchy = 'issue_date'

    def total_amount(self, obj):
        return obj.total_amount
    total_amount.short_description = "Total"

    def total_paid(self, obj):
        return obj.total_paid
    total_paid.short_description = "Paid"

    def balance(self, obj):
        return obj.balance
    balance.short_description = "Balance"


@admin.register(Payment)
class PaymentAdmin(BaseModelAdmin):
    list_display = ('student', 'fee_category', 'invoice', 'amount_received', 'balance_after_payment',
                     'status', 'payment_method', 'payment_date', 'recorded_by')
    list_filter = ('status', 'payment_method', 'payment_date', 'fee_category', 'term', 'session')
    search_fields = ('student__first_name', 'student__last_name', 'student__USN', 'transaction_id',
                      'invoice__invoice_number')
    raw_id_fields = ('student', 'invoice', 'fee_category', 'term', 'session', 'recorded_by')
    readonly_fields = ('balance_before_payment', 'balance_after_payment', 'date_recorded')
    date_hierarchy = 'payment_date'

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Receipt)
class ReceiptAdmin(BaseModelAdmin):
    list_display = ('receipt_number', 'payment', 'issue_date', 'generated_by')
    search_fields = ('receipt_number', 'payment__student__first_name', 'payment__student__last_name')
    readonly_fields = ('receipt_number', 'issue_date')


@admin.register(StudentAccountLedger)
class StudentAccountLedgerAdmin(BaseModelAdmin):
    list_display = ('student', 'term', 'session', 'total_invoiced', 'total_paid', 'balance', 'last_updated')
    list_filter = ('term', 'session')
    search_fields = ('student__first_name', 'student__last_name', 'student__USN')
    readonly_fields = ('total_invoiced', 'total_paid', 'balance', 'last_updated')


@admin.register(StudentLedgerEntry)
class StudentLedgerEntryAdmin(BaseModelAdmin):
    list_display = ('student', 'entry_type', 'amount', 'running_balance', 'term', 'session', 'created_at')
    list_filter = ('entry_type', 'term', 'session')
    search_fields = ('student__first_name', 'student__last_name', 'description')
    readonly_fields = [f.name for f in StudentLedgerEntry._meta.fields]


@admin.register(PaymentNotification)
class PaymentNotificationAdmin(BaseModelAdmin):
    list_display = ('student', 'amount_paid', 'payment_method', 'bank_account', 'payment_date',
                     'status_badge', 'submission_date')
    list_filter = ('status', 'payment_method', 'bank_account', 'session', 'term')
    search_fields = ('student__first_name', 'student__last_name', 'transaction_id')
    readonly_fields = ('notified_by', 'submission_date', 'processed_by', 'processed_at', 'resulting_payment')

    def status_badge(self, obj):
        colors = {'PENDING': '#f59e0b', 'PROCESSED': '#16a34a', 'REJECTED': '#dc2626'}
        return format_html('<span style="color:{}; font-weight:600;">{}</span>',
                            colors.get(obj.status, '#333'), obj.get_status_display())
    status_badge.short_description = 'Status'


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(BaseModelAdmin):
    list_display = ('name', 'category_type', 'is_active')
    list_filter = ('category_type', 'is_active')
    search_fields = ('name',)


@admin.register(Vendor)
class VendorAdmin(BaseModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'email', 'is_active')
    search_fields = ('name', 'contact_person', 'phone', 'email')
    list_filter = ('is_active',)


@admin.register(Expense)
class ExpenseAdmin(BaseModelAdmin):
    list_display = ('title', 'category', 'vendor', 'amount', 'expense_date', 'status',
                     'payment_method', 'recorded_by', 'approved_by')
    list_filter = ('status', 'category', 'payment_method', 'expense_date', 'term', 'session')
    search_fields = ('title', 'vendor__name', 'reference_number')
    raw_id_fields = ('vendor', 'term', 'session', 'recorded_by', 'approved_by')
    date_hierarchy = 'expense_date'

    def save_model(self, request, obj, form, change):
        if not obj.pk and not obj.recorded_by:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)
