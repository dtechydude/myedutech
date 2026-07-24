# finance/serializers.py
from rest_framework import serializers

from .models import (
    BankAccount, FeeCategory, FeeStructure, Invoice, InvoiceItem, Payment, Receipt,
    StudentAccountLedger, PaymentNotification, ExpenseCategory, Vendor, Expense,
)
from . import services


class BankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankAccount
        fields = ['id', 'account_name', 'account_number', 'bank_name', 'branch', 'is_primary', 'is_active']


class FeeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeCategory
        fields = ['id', 'name', 'category_type', 'description', 'is_active']


class FeeStructureSerializer(serializers.ModelSerializer):
    fee_category_name = serializers.CharField(source='fee_category.name', read_only=True)
    student_class_name = serializers.CharField(source='student_class.name', read_only=True, default='All Classes')

    class Meta:
        model = FeeStructure
        fields = ['id', 'student_class', 'student_class_name', 'fee_category', 'fee_category_name',
                   'term', 'session', 'label', 'amount', 'is_mandatory', 'due_date']


class InvoiceItemSerializer(serializers.ModelSerializer):
    fee_category_name = serializers.CharField(source='fee_category.name', read_only=True)

    class Meta:
        model = InvoiceItem
        fields = ['id', 'fee_category', 'fee_category_name', 'description', 'quantity', 'amount']


class InvoiceSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, read_only=True)
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Invoice
        fields = ['id', 'invoice_number', 'student', 'student_name', 'term', 'session', 'issue_date',
                   'due_date', 'status', 'notes', 'items', 'total_amount', 'total_paid', 'balance']
        read_only_fields = ['invoice_number', 'status']


class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = ['id', 'receipt_number', 'issue_date', 'generated_by']


class PaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)
    receipt = ReceiptSerializer(read_only=True)
    fee_category_name = serializers.CharField(source='fee_category.name', read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'student', 'student_name', 'invoice', 'fee_category', 'fee_category_name',
                   'term', 'session', 'amount_received', 'discount_amount', 'discount_percentage',
                   'payment_date', 'payment_method', 'status', 'transaction_id', 'notes',
                   'balance_before_payment', 'balance_after_payment', 'recorded_by', 'date_recorded', 'receipt']
        read_only_fields = ['status', 'balance_before_payment', 'balance_after_payment', 'recorded_by',
                              'date_recorded']

    def create(self, validated_data):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        return services.record_payment(
            user=user,
            student=validated_data['student'],
            invoice=validated_data.get('invoice'),
            fee_category=validated_data.get('fee_category'),
            amount_received=validated_data['amount_received'],
            payment_method=validated_data['payment_method'],
            payment_date=validated_data.get('payment_date'),
            transaction_id=validated_data.get('transaction_id'),
            notes=validated_data.get('notes', ''),
            discount_amount=validated_data.get('discount_amount', 0),
            discount_percentage=validated_data.get('discount_percentage', 0),
        )


class StudentAccountLedgerSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.get_full_name', read_only=True)

    class Meta:
        model = StudentAccountLedger
        fields = ['id', 'student', 'student_name', 'term', 'session', 'total_invoiced', 'total_paid',
                   'balance', 'last_updated']


class PaymentNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentNotification
        fields = ['id', 'student', 'amount_paid', 'payment_method', 'bank_account', 'transaction_id',
                   'payment_date', 'proof_of_payment', 'session', 'term', 'status', 'submission_date', 'notes']
        read_only_fields = ['status', 'submission_date']

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['notified_by'] = getattr(request, 'user', None)
        return super().create(validated_data)


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = ['id', 'name', 'category_type', 'description', 'is_active']


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ['id', 'name', 'contact_person', 'phone', 'email', 'address', 'is_active']


class ExpenseSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    vendor_name = serializers.CharField(source='vendor.name', read_only=True, default=None)

    class Meta:
        model = Expense
        fields = ['id', 'title', 'category', 'category_name', 'vendor', 'vendor_name', 'amount', 'expense_date',
                   'term', 'session', 'payment_method', 'reference_number', 'status', 'attachment', 'notes',
                   'recorded_by', 'approved_by', 'created_at']
        read_only_fields = ['recorded_by', 'approved_by', 'created_at']

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['recorded_by'] = getattr(request, 'user', None)
        return super().create(validated_data)
