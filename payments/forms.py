# payments/forms.py
from django import forms
from django.db.models import Sum, F
from django.db.models.functions import Coalesce  # Correct import for the Coalesce function
from .models import Payment, StudentFeeAssignment, PaymentCategory, PaymentNotification, BankDetail
from students.models import Student
from decimal import Decimal
from curriculum.models import Term, Session



class StudentPaymentForm(forms.ModelForm):
    # This field is now used for both staff and student payments
    payment_category = forms.ModelChoiceField(
        queryset=None,
        label="Payment Category",
        required=True,
        empty_label="--- Select a category ---",
    )
    
    # Add the session and term fields
    session = forms.ModelChoiceField(
        queryset=Session.objects.all().order_by('-start_date'),
        label="Session",
        empty_label="--- Select a session ---",
        required=True,
    )
    term = forms.ModelChoiceField(
        queryset=Term.objects.all().order_by('name'),
        label="Term",
        empty_label="--- Select a term ---",
        required=True,
    )
    
    # Add the payment_date field here
    payment_date = forms.DateField(
        label='Payment Date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    class Meta:
        model = Payment
        fields = [
            'student',
            'session',  # Add these fields to the Meta.fields list
            'term',     # Add these fields to the Meta.fields list
            'payment_category',
            'amount_received',
            'payment_method',
            'transaction_id',
            'payment_date',
            'notes',
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Add a widget to the student field for consistent styling
        self.fields['student'].widget = forms.Select(attrs={'class': 'form-control'})

        is_student_user = self.user and hasattr(self.user, 'student')

        # Populate the payment_category field for all users
        self.fields['payment_category'].queryset = PaymentCategory.objects.all().order_by('name')

        if is_student_user:
            student_instance = self.user.student
            self.fields['student'].queryset = Student.objects.filter(pk=student_instance.pk)
            self.fields['student'].initial = student_instance.pk
            self.fields['student'].widget = forms.HiddenInput()
        else:
            self.fields['student'].queryset = Student.objects.all().order_by('last_name')
            self.fields['student'].empty_label = "-- Select a Student --"


# PARENT PAYMENT FORM
class ParentPaymentForm(forms.ModelForm):
    """
    Form for parents to make a payment on behalf of a student.
    Uses AJAX to dynamically load outstanding fees for the selected child.
    """
    student = forms.ModelChoiceField(
        queryset=None,
        label="Select Child",
        empty_label="--- Select a child ---",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'student-select'})
    )
    
    student_fee_assignment = forms.ModelChoiceField(
        queryset=None,
        label="Select Outstanding Fee",
        empty_label="--- Select an outstanding fee ---",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'fee-assignment-select'}),
        required=False
    )
    
    # Add the payment_date field here
    payment_date = forms.DateField(
        label='Payment Date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    class Meta:
        model = Payment
        fields = [
            'student',
            'student_fee_assignment',
            'amount_received',
            'payment_method',
            'transaction_id',
            'payment_date',
            'notes',
        ]
        widgets = {
            'amount_received': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.parent = kwargs.pop('parent', None)
        super().__init__(*args, **kwargs)

        if self.parent:
            self.fields['student'].queryset = Student.objects.filter(parent=self.parent).order_by('last_name')
            self.fields['student_fee_assignment'].queryset = StudentFeeAssignment.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        amount_received = cleaned_data.get('amount_received')
        student_fee_assignment = cleaned_data.get('student_fee_assignment')

        if not student_fee_assignment:
            self.add_error('student_fee_assignment', 'Please select a fee to pay.')
            
        if amount_received is None:
            self.add_error('amount_received', 'Amount paid is required.')
        elif amount_received <= 0:
            self.add_error('amount_received', 'Amount paid must be greater than zero.')

        if student_fee_assignment and amount_received:
            total_paid_result = student_fee_assignment.payments.aggregate(total=Sum('amount_received'))['total']
            total_paid = total_paid_result if total_paid_result is not None else Decimal('0.00')
            
            balance_due = student_fee_assignment.amount_due - total_paid

            if amount_received > balance_due:
                self.add_error('amount_received', f'The payment amount cannot exceed the outstanding balance of ₦{balance_due:.2f}.')

        return cleaned_data
    


class SpecificItemPaymentForm(forms.ModelForm):
    """
    Form for making payments for specific, non-invoice items (e.g., uniforms).
    """
    # The 'student' field will be used for staff to select a student.
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        label="Select Student",
        required=True
    )
    # This field allows the user to select the specific item category.
    payment_category = forms.ModelChoiceField(
        queryset=PaymentCategory.objects.all(),
        label="Item/Fee Category",
        required=True
    )
    
    class Meta:
        model = Payment
        fields = ['student', 'payment_category', 'amount_received', 'payment_method', 'payment_date', 'notes']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
        }

# full payment form
class FullPaymentForm(forms.ModelForm):
    # This form is for making a full or partial payment against the total balance
    class Meta:
        model = Payment
        fields = ['student', 'session', 'term', 'amount_received', 'payment_method', 'transaction_id']
        widgets = {
            'student': forms.HiddenInput(),
            'session': forms.HiddenInput(),
            'term': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Use crispy_forms layout for a cleaner appearance
        self.helper = FormHelper()
        self.helper.layout = Layout(
            'amount_received',
            'payment_method',
            'transaction_id',
        )


# PAYMENT NOTIFICATION
class PaymentNotificationForm(forms.ModelForm):
    """
    Form for parents/students to notify the school of an offline payment,
    with user-role based restrictions on student selection.
    """     
    # Use ModelChoiceFields for Session and Term
    session = forms.ModelChoiceField(
        queryset=Session.objects.all().order_by('-start_date'),
        label="Session (Optional)",
        empty_label="--- Select a session ---",
        required=False,
    )
    term = forms.ModelChoiceField(
        queryset=Term.objects.all().order_by('name'),
        label="Term (Optional)",
        empty_label="--- Select a term ---",
        required=False,
    )

    # --- CORRECTED: Custom ModelChoiceField for Bank Account ---
    bank_account = forms.ModelChoiceField(
        # The .filter(is_active=True) part is REMOVED as that field doesn't exist
        queryset=BankDetail.objects.all().order_by('bank_name'), 
        label="School Bank Account Paid To",
        empty_label="--- Select the School's Bank Account ---",
        required=True, # This remains required for a valid payment notification
    )
    
    class Meta:
        model = PaymentNotification
        fields = [
            'student',
            'amount_paid',
            'payment_method',
            'bank_account', # Included in fields
            'transaction_id',
            'payment_date',
            'session',
            'term',
            'notes',
        ]
        widgets = {
            'amount_paid': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'transaction_id': forms.TextInput(attrs={'placeholder': 'Bank/Gateway Reference ID'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Pop user and parent objects passed from the view
        self.user = kwargs.pop('user', None)
        self.parent = kwargs.pop('parent', None)
        super().__init__(*args, **kwargs)

        # --- SECURITY AND UX LOGIC ---
        is_staff_user = self.user and self.user.is_staff

        if self.user and hasattr(self.user, 'parent') and self.parent:
            # CASE 1: LOGGED-IN USER IS A PARENT
            children_qs = Student.objects.filter(parent=self.parent).order_by('last_name')
            self.fields['student'].queryset = children_qs
            self.fields['student'].empty_label = "--- Select a child ---"
            
            # If they have only one child, pre-select it AND HIDE THE FIELD
            if children_qs.count() == 1:
                single_child = children_qs.first()
                self.fields['student'].initial = single_child.pk
                self.fields['student'].widget = forms.HiddenInput()
                
        elif self.user and hasattr(self.user, 'student'):
            # CASE 2: LOGGED-IN USER IS A STUDENT
            student_instance = self.user.student
            
            # Restrict queryset to only themselves, set initial, and hide
            self.fields['student'].queryset = Student.objects.filter(pk=student_instance.pk)
            self.fields['student'].initial = student_instance.pk
            self.fields['student'].widget = forms.HiddenInput()
            
        elif is_staff_user:
            # CASE 3: ADMIN/STAFF USER (Keep default behavior for staff)
            self.fields['student'].queryset = Student.objects.all().order_by('last_name')
            self.fields['student'].empty_label = "-- Select a Student --"
        else:
            # Fallback for unauthenticated or unlinked users
            self.fields['student'].queryset = Student.objects.none()