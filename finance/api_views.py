# finance/api_views.py
"""
REST API for the Finance app (mobile app integration). Mounted separately
from the HTML urls.py — see finance/api_urls.py.
"""
from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import (
    BankAccount, FeeCategory, FeeStructure, Invoice, Payment,
    StudentAccountLedger, PaymentNotification, ExpenseCategory, Vendor, Expense,
)
from .serializers import (
    BankAccountSerializer, FeeCategorySerializer, FeeStructureSerializer, InvoiceSerializer,
    PaymentSerializer, StudentAccountLedgerSerializer, PaymentNotificationSerializer,
    ExpenseCategorySerializer, VendorSerializer, ExpenseSerializer,
)
from .permissions import is_finance_staff, is_parent, is_student_user


class IsFinanceStaffOrReadOnlyOwn(permissions.BasePermission):
    """Staff get full access; parents/students may only read their own records."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if is_finance_staff(user):
            return True
        if request.method not in permissions.SAFE_METHODS:
            return False
        student = getattr(obj, 'student', None)
        if student is None:
            return False
        if is_student_user(user) and student == getattr(user, 'student', None):
            return True
        if is_parent(user) and student.parent_id == getattr(user.parent, 'id', None):
            return True
        return False


class BankAccountViewSet(viewsets.ModelViewSet):
    queryset = BankAccount.objects.filter(is_active=True)
    serializer_class = BankAccountSerializer
    permission_classes = [permissions.IsAuthenticated]


class FeeCategoryViewSet(viewsets.ModelViewSet):
    queryset = FeeCategory.objects.filter(is_active=True)
    serializer_class = FeeCategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.select_related('student_class', 'fee_category', 'term', 'session')
    serializer_class = FeeStructureSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['student_class', 'fee_category', 'term', 'session']


class InvoiceViewSet(viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    permission_classes = [permissions.IsAuthenticated, IsFinanceStaffOrReadOnlyOwn]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'term', 'session', 'student']
    search_fields = ['invoice_number', 'student__first_name', 'student__last_name']

    def get_queryset(self):
        user = self.request.user
        qs = Invoice.objects.select_related('student', 'term', 'session').prefetch_related('items')
        if is_finance_staff(user):
            return qs
        if is_student_user(user):
            return qs.filter(student=user.student)
        if is_parent(user):
            return qs.filter(student__parent=user.parent)
        return qs.none()


class PaymentViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated, IsFinanceStaffOrReadOnlyOwn]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['status', 'term', 'session', 'student', 'fee_category']

    def get_queryset(self):
        user = self.request.user
        qs = Payment.objects.select_related('student', 'fee_category', 'invoice', 'receipt')
        if is_finance_staff(user):
            return qs
        if is_student_user(user):
            return qs.filter(student=user.student)
        if is_parent(user):
            return qs.filter(student__parent=user.parent)
        return qs.none()


class StudentLedgerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = StudentAccountLedgerSerializer
    permission_classes = [permissions.IsAuthenticated, IsFinanceStaffOrReadOnlyOwn]

    def get_queryset(self):
        user = self.request.user
        qs = StudentAccountLedger.objects.select_related('student', 'term', 'session')
        if is_finance_staff(user):
            return qs
        if is_student_user(user):
            return qs.filter(student=user.student)
        if is_parent(user):
            return qs.filter(student__parent=user.parent)
        return qs.none()


class PaymentNotificationViewSet(viewsets.ModelViewSet):
    serializer_class = PaymentNotificationSerializer
    permission_classes = [permissions.IsAuthenticated, IsFinanceStaffOrReadOnlyOwn]

    def get_queryset(self):
        user = self.request.user
        qs = PaymentNotification.objects.select_related('student', 'bank_account')
        if is_finance_staff(user):
            return qs
        if is_student_user(user):
            return qs.filter(student=user.student)
        if is_parent(user):
            return qs.filter(student__parent=user.parent)
        return qs.none()


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.filter(is_active=True)
    serializer_class = ExpenseCategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.filter(is_active=True)
    serializer_class = VendorSerializer
    permission_classes = [permissions.IsAuthenticated]


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.select_related('category', 'vendor')
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]  # tighten with finance_staff check in production
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category', 'vendor', 'status', 'term', 'session']
