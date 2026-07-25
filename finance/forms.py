# finance/forms.py
from decimal import Decimal

from django import forms
from django.utils import timezone

from curriculum.models import Term, Session, Standard
from students.models import Student

from .models import (
    BankAccount, FeeCategory, FeeStructure, Invoice, InvoiceItem, Payment,
    PaymentNotification, ExpenseCategory, Vendor, Expense, StudentDiscount, StudentFeeException,
    InstallmentPlan, Installment,
)

DATE_INPUT = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})


class BootstrapFormMixin:
    """Adds `.form-control` / `.form-select` classes to all fields automatically."""

    def _apply_bootstrap(self):
        for name, field in self.fields.items():
            widget = field.widget
            css = widget.attrs.get('class', '')
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs['class'] = (css + ' form-check-input').strip()
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs['class'] = (css + ' form-select').strip()
            else:
                widget.attrs['class'] = (css + ' form-control').strip()


class StudentClassAwareSelect(forms.Select):
    """
    A <select> widget that stamps each student <option> with a
    `data-class-id` attribute, so a small bit of front-end JS can filter a
    long student list down to one class instantly — no page reload, no
    extra AJAX round-trip needed just to narrow the list. Used anywhere a
    staff member has to pick a student out of the whole school.
    """
    def __init__(self, *args, class_lookup=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_lookup = class_lookup or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        raw_value = value.value if hasattr(value, 'value') else value
        class_id = self.class_lookup.get(str(raw_value)) if raw_value not in (None, '') else None
        if class_id:
            option['attrs']['data-class-id'] = str(class_id)
        return option


class StudentClassFilterMixin:
    """
    Mixin for any ModelForm with a `student` field: swaps in
    StudentClassAwareSelect and exposes `self.classes` for the template to
    render a "Filter by Class" dropdown next to the student picker.
    """
    def _enable_student_class_filter(self, queryset=None):
        queryset = queryset if queryset is not None else Student.objects.all().order_by('last_name', 'first_name')
        class_lookup = {str(pk): class_id for pk, class_id in queryset.values_list('pk', 'current_class_id')
                         if class_id}
        self.fields['student'].widget = StudentClassAwareSelect(
            attrs={'class': 'form-select'}, class_lookup=class_lookup,
        )
        self.classes = Standard.objects.all().order_by('name')


# ---------------------------------------------------------------------------
# Fee structure / setup
# ---------------------------------------------------------------------------
class FeeCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ['name', 'category_type', 'description', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class FeeStructureForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = FeeStructure
        fields = ['student_class', 'fee_category', 'term', 'session', 'label', 'amount',
                   'is_mandatory', 'due_date']
        widgets = {'due_date': DATE_INPUT}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
        self.fields['student_class'].required = False
        self.fields['student_class'].empty_label = "-- All Classes --"


class StudentDiscountForm(StudentClassFilterMixin, BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StudentDiscount
        fields = ['student', 'fee_category', 'term', 'session', 'discount_type', 'value', 'reason', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
        self.fields['student'].queryset = Student.objects.all().order_by('last_name', 'first_name')
        self._enable_student_class_filter()
        self.fields['fee_category'].required = False
        self.fields['fee_category'].empty_label = "-- All Categories --"
        self.fields['term'].required = False
        self.fields['term'].empty_label = "-- Every Term --"
        self.fields['session'].required = False
        self.fields['session'].empty_label = "-- Every Session --"

    def clean_value(self):
        value = self.cleaned_data['value']
        if self.cleaned_data.get('discount_type') == StudentDiscount.DiscountType.PERCENTAGE and value > 100:
            raise forms.ValidationError("A percentage discount can't exceed 100%.")
        if value <= 0:
            raise forms.ValidationError("Discount value must be greater than zero.")
        return value


class StudentFeeExceptionForm(StudentClassFilterMixin, BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = StudentFeeException
        fields = ['student', 'fee_structure', 'action', 'reason']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
        self.fields['student'].queryset = Student.objects.all().order_by('last_name', 'first_name')
        self._enable_student_class_filter()
        self.fields['fee_structure'].queryset = FeeStructure.objects.select_related(
            'fee_category', 'student_class', 'term', 'session'
        ).order_by('term__name', 'fee_category__name')
        self.fields['fee_structure'].label_from_instance = lambda fs: (
            f"{fs.fee_category.name} — {fs.student_class.name if fs.student_class else 'All Classes'} "
            f"({fs.term} {fs.session}) {'[optional]' if not fs.is_mandatory else ''}"
        )

    def clean(self):
        cleaned = super().clean()
        fee_structure = cleaned.get('fee_structure')
        action = cleaned.get('action')
        if fee_structure and action:
            if action == StudentFeeException.Action.EXCLUDE and not fee_structure.is_mandatory:
                raise forms.ValidationError(
                    "This fee is already optional — nobody is charged unless they're specifically "
                    "included, so there's nothing to exclude. Did you mean to remove an existing "
                    "'Include' exception instead?"
                )
            if action == StudentFeeException.Action.INCLUDE and fee_structure.is_mandatory:
                raise forms.ValidationError(
                    "This fee is already mandatory for the whole class — everyone is charged by "
                    "default, so there's nothing to include. Did you mean to remove an existing "
                    "'Exclude' exception instead?"
                )
        return cleaned


class GenerateInvoicesForm(forms.Form):
    """Bulk-generate invoices for a whole class from the current fee structure."""
    student_class = forms.ModelChoiceField(queryset=Standard.objects.all(), required=True, label="Class")
    term = forms.ModelChoiceField(queryset=Term.objects.all(), required=True)
    session = forms.ModelChoiceField(queryset=Session.objects.all().order_by('-start_date'), required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select'


class BankAccountForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['account_name', 'account_number', 'bank_name', 'branch', 'is_primary', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


# ---------------------------------------------------------------------------
# Invoicing
# ---------------------------------------------------------------------------
class InvoiceForm(StudentClassFilterMixin, BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['student', 'term', 'session', 'due_date', 'status', 'notes']
        widgets = {'due_date': DATE_INPUT}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
        self.fields['student'].queryset = Student.objects.all().order_by('last_name', 'first_name')
        self._enable_student_class_filter()


InvoiceItemFormSet = forms.inlineformset_factory(
    Invoice, InvoiceItem,
    fields=['fee_category', 'description', 'quantity', 'amount'],
    extra=1, can_delete=True,
    widgets={
        'fee_category': forms.Select(attrs={'class': 'form-select'}),
        'description': forms.TextInput(attrs={'class': 'form-control'}),
        'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
    },
)


class InstallmentPlanQuickForm(forms.Form):
    """Auto-splits an invoice's total into N equal installments, spaced N days apart."""
    count = forms.IntegerField(min_value=2, max_value=12, initial=2, label="Number of installments",
                                widget=forms.NumberInput(attrs={'class': 'form-control'}))
    first_due_date = forms.DateField(required=False, label="First installment due date", widget=DATE_INPUT)
    interval_days = forms.IntegerField(required=False, initial=30, label="Days between installments",
                                        widget=forms.NumberInput(attrs={'class': 'form-control'}))


InstallmentFormSet = forms.inlineformset_factory(
    InstallmentPlan, Installment,
    fields=['label', 'amount_due', 'due_date'],
    extra=1, can_delete=True,
    widgets={
        'label': forms.TextInput(attrs={'class': 'form-control'}),
        'amount_due': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        'due_date': DATE_INPUT,
    },
)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
class StaffPaymentForm(StudentClassFilterMixin, forms.Form):
    """Staff-facing "record a payment" form, settling an invoice balance."""
    student = forms.ModelChoiceField(queryset=Student.objects.all().order_by('last_name'),
                                      widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_student'}))
    invoice = forms.ModelChoiceField(queryset=Invoice.objects.none(), required=False,
                                      label="Invoice (outstanding balances)",
                                      widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_invoice'}))
    fee_category = forms.ModelChoiceField(queryset=FeeCategory.objects.filter(is_active=True), required=False,
                                           help_text="Only needed for a payment not tied to an invoice.")
    amount_received = forms.DecimalField(min_value=Decimal('0.01'), max_digits=12, decimal_places=2,
                                          widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    payment_method = forms.ChoiceField(choices=Payment._meta.get_field('payment_method').choices,
                                        widget=forms.Select(attrs={'class': 'form-select'}))
    payment_date = forms.DateField(initial=timezone.localdate, widget=DATE_INPUT)
    transaction_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._enable_student_class_filter()
        initial_student = self.initial.get('student')
        initial_student_id = initial_student.pk if isinstance(initial_student, Student) else initial_student
        student_id = self.data.get('student') or initial_student_id
        if student_id:
            self.fields['invoice'].queryset = Invoice.objects.filter(
                student_id=student_id).exclude(status=Invoice.Status.CANCELLED)

    def clean(self):
        cleaned = super().clean()
        invoice = cleaned.get('invoice')
        amount = cleaned.get('amount_received')
        if not invoice and not cleaned.get('fee_category'):
            raise forms.ValidationError("Select either an invoice to pay against, or a fee category for a "
                                         "standalone payment.")
        if invoice and amount and amount > invoice.balance:
            self.add_error('amount_received',
                            f"Amount cannot exceed the outstanding invoice balance of {invoice.balance}.")
        return cleaned


class ParentPaymentForm(forms.Form):
    """Parent-facing payment form — restricted to their own children's invoices."""
    student = forms.ModelChoiceField(queryset=Student.objects.none(), label="Select Child",
                                      widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_student'}))
    invoice = forms.ModelChoiceField(queryset=Invoice.objects.none(), label="Outstanding Invoice",
                                      widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_invoice'}))
    amount_received = forms.DecimalField(min_value=Decimal('0.01'), max_digits=12, decimal_places=2,
                                          widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}))
    payment_method = forms.ChoiceField(choices=Payment._meta.get_field('payment_method').choices,
                                        widget=forms.Select(attrs={'class': 'form-select'}))
    payment_date = forms.DateField(initial=timezone.localdate, widget=DATE_INPUT)
    transaction_id = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}))

    def __init__(self, *args, parent=None, **kwargs):
        super().__init__(*args, **kwargs)
        if parent is not None:
            children = Student.objects.filter(parent=parent).order_by('last_name')
            self.fields['student'].queryset = children
            student_id = self.data.get('student')
            if student_id:
                self.fields['invoice'].queryset = Invoice.objects.filter(
                    student_id=student_id, student__in=children).exclude(status=Invoice.Status.CANCELLED)

    def clean(self):
        cleaned = super().clean()
        invoice = cleaned.get('invoice')
        amount = cleaned.get('amount_received')
        if invoice and amount and amount > invoice.balance:
            self.add_error('amount_received',
                            f"Amount cannot exceed the outstanding balance of {invoice.balance}.")
        return cleaned


class PaymentNotificationForm(StudentClassFilterMixin, BootstrapFormMixin, forms.ModelForm):
    """Parents/students declare an offline payment for staff to verify."""
    class Meta:
        model = PaymentNotification
        fields = ['student', 'amount_paid', 'payment_method', 'bank_account', 'transaction_id',
                  'payment_date', 'session', 'term', 'proof_of_payment', 'notes']
        widgets = {'payment_date': DATE_INPUT}

    def __init__(self, *args, user=None, parent=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
        self.fields['session'].required = False
        self.fields['term'].required = False
        self.fields['bank_account'].queryset = BankAccount.objects.filter(is_active=True)

        if user and hasattr(user, 'parent') and parent:
            children = Student.objects.filter(parent=parent).order_by('last_name')
            self.fields['student'].queryset = children
            if children.count() == 1:
                self.fields['student'].initial = children.first().pk
                self.fields['student'].widget = forms.HiddenInput()
        elif user and hasattr(user, 'student'):
            self.fields['student'].queryset = Student.objects.filter(pk=user.student.pk)
            self.fields['student'].initial = user.student.pk
            self.fields['student'].widget = forms.HiddenInput()
        elif user and user.is_staff:
            self.fields['student'].queryset = Student.objects.all().order_by('last_name')
            self._enable_student_class_filter()
        else:
            self.fields['student'].queryset = Student.objects.none()


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------
class ExpenseCategoryForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'category_type', 'description', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class VendorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ['name', 'contact_person', 'phone', 'email', 'address', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()


class ExpenseForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Expense
        fields = ['title', 'category', 'vendor', 'amount', 'expense_date', 'term', 'session',
                   'payment_method', 'reference_number', 'status', 'attachment', 'notes']
        widgets = {'expense_date': DATE_INPUT}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_bootstrap()
        self.fields['term'].required = False
        self.fields['session'].required = False
        self.fields['vendor'].required = False


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
class ReportFilterForm(forms.Form):
    start_date = forms.DateField(required=False, widget=DATE_INPUT)
    end_date = forms.DateField(required=False, widget=DATE_INPUT)
    term = forms.ModelChoiceField(queryset=Term.objects.all(), required=False)
    session = forms.ModelChoiceField(queryset=Session.objects.all().order_by('-start_date'), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select' if isinstance(field, forms.ModelChoiceField) \
                else 'form-control'


class FeeTableFilterForm(forms.Form):
    student_class = forms.ModelChoiceField(queryset=Standard.objects.all(), required=False, label="Class")
    term = forms.ModelChoiceField(queryset=Term.objects.all(), required=False)
    session = forms.ModelChoiceField(queryset=Session.objects.all().order_by('-start_date'), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select'


class StudentPaymentDirectoryFilterForm(forms.Form):
    """Filters the 'pick a student to record a payment for' directory — class + free-text search."""
    student_class = forms.ModelChoiceField(queryset=Standard.objects.all(), required=False, label="Class")
    q = forms.CharField(required=False, label="Search", widget=forms.TextInput(
        attrs={'placeholder': 'Search by name or admission no.'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student_class'].widget.attrs['class'] = 'form-select'
        self.fields['q'].widget.attrs['class'] = 'form-control'
