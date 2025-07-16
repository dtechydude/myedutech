# student_management_app/forms.py (or payments/forms.py)

from django import forms
from .models import Payment, PaymentCategory, CategoryFee # Import CategoryFee
from students.models import Student # Make sure Student is imported
from decimal import Decimal
from curriculum.models import Term, Session

class PaymentForm(forms.ModelForm):
    """
    Form for recording a new payment.
    Dynamically adjusts fields based on whether the user is staff or a student.
    Staff see all fields including original_amount and discounts.
    Students select a CategoryFee, and original_amount is derived.
    """
    # For students, they will select a CategoryFee
    # For staff, this field will be hidden, and they'll use term/session/payment_category/original_amount directly
    category_fee = forms.ModelChoiceField(
        queryset=CategoryFee.objects.all().select_related('term', 'session', 'payment_category').order_by('session__name', 'term__name', 'payment_category__name', 'fee_name'),
        required=False, # Required status set in __init__
        label="Select Fee Type",
        help_text="Select the specific fee (e.g., 'Tuition - Semester 1')",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Payment
        # All fields are listed here initially. Visibility will be controlled in __init__.
        fields = [
            'student', 'category_fee', # category_fee is new
            'original_amount', 'discount_amount', 'discount_percentage',
            'amount_received',
            'payment_method', 'transaction_id', 'notes',
            'term', 'session', 'payment_category', # These are for staff, or derived from category_fee for students
            'is_installment', 'installment_number', 'total_installments'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'original_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'e.g., 50.00'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100', 'placeholder': 'e.g., 10.00'}),
            'amount_received': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Enter amount paid'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional transaction ID'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Any additional notes'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'payment_category': forms.Select(attrs={'class': 'form-control'}),
            'is_installment': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-blue-600'}),
            # REMOVED style: 'display:none;' from here. Visibility will be controlled in the template.
            'installment_number': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'e.g., 1'}),
            'total_installments': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'e.g., 3'}),
        }
        labels = {
            'student': 'Select Student',
            'original_amount': 'Original Amount Due',
            'discount_amount': 'Fixed Discount Amount',
            'discount_percentage': 'Percentage Discount (%)',
            'amount_received': 'Amount Paid',
            'payment_method': 'Payment Method',
            'transaction_id': 'Transaction ID',
            'notes': 'Notes',
            'term': 'Academic Term',
            'session': 'Academic Session',
            'payment_category': 'Payment Category',
            'is_installment': 'Is this an installment payment?',
            'installment_number': 'Installment Number',
            'total_installments': 'Total Installments',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None) # Store user as an instance attribute
        super().__init__(*args, **kwargs)

        is_staff_user = self.user and self.user.is_staff
        is_student_user = self.user and hasattr(self.user, 'student')

        # Always populate these dropdowns for staff, and for initial student view
        self.fields['term'].queryset = Term.objects.all().order_by('-start_date')
        self.fields['session'].queryset = Session.objects.all().order_by('-start_date')
        self.fields['payment_category'].queryset = PaymentCategory.objects.all().order_by('name')
        self.fields['category_fee'].empty_label = "-- Select a Fee Type --"


        if is_student_user:
            student_instance = self.user.student
            self.fields['student'].queryset = Student.objects.filter(pk=student_instance.pk)
            self.fields['student'].initial = student_instance.pk
            self.fields['student'].widget = forms.HiddenInput()

            # For students, make category_fee required and visible
            self.fields['category_fee'].required = True
            # Remove staff-only fields (or make them hidden and not required)
            del self.fields['original_amount']
            del self.fields['discount_amount']
            del self.fields['discount_percentage']

            # Make term, session, payment_category hidden and not required for students
            # Their values will be derived from the selected category_fee in the view.
            self.fields['term'].required = False
            self.fields['term'].widget = forms.HiddenInput()
            self.fields['session'].required = False
            self.fields['session'].widget = forms.HiddenInput()
            self.fields['payment_category'].required = False
            self.fields['payment_category'].widget = forms.HiddenInput()


        elif is_staff_user:
            # For staff, make category_fee not required and hide it
            self.fields['category_fee'].required = False
            self.fields['category_fee'].widget = forms.HiddenInput()

            # Ensure staff-only fields are visible and required as needed
            self.fields['original_amount'].required = True # Staff must enter original amount
            self.fields['student'].empty_label = "-- Select a Student --"
            self.fields['term'].empty_label = "-- Select a Term --"
            self.fields['session'].empty_label = "-- Select a Session --"
            self.fields['payment_category'].empty_label = "-- Select a Category --"
            self.fields['term'].required = True
            self.fields['session'].required = True
            self.fields['payment_category'].required = True

        else: # Anonymous or other non-student/non-staff users (should be handled by @login_required)
            # Default to staff-like behavior but might want to redirect or show error
            self.fields['category_fee'].required = False
            self.fields['category_fee'].widget = forms.HiddenInput()
            self.fields['original_amount'].required = True
            self.fields['student'].empty_label = "-- Select a Student --"
            self.fields['term'].empty_label = "-- Select a Term --"
            self.fields['session'].empty_label = "-- Select a Session --"
            self.fields['payment_category'].empty_label = "-- Select a Category --"
            self.fields['term'].required = True
            self.fields['session'].required = True
            self.fields['payment_category'].required = True


    def clean(self):
        cleaned_data = super().clean()

        # Use the stored user attribute
        user = self.user
        is_staff_user = user and user.is_staff
        is_student_user = user and hasattr(user, 'student')

        amount_received = cleaned_data.get('amount_received')
        is_installment = cleaned_data.get('is_installment')

        # --- Common validation for amount_received ---
        if amount_received is None: # Ensure amount_received is not empty
            self.add_error('amount_received', 'Amount paid is required.')
        elif amount_received <= 0:
            self.add_error('amount_received', 'Amount paid must be greater than zero.')

        # --- Installment fields handling and validation ---
        installment_number = cleaned_data.get('installment_number')
        total_installments = cleaned_data.get('total_installments')

        if is_installment:
            if not installment_number:
                self.add_error('installment_number', 'Installment number is required for installment payments.')
            if not total_installments:
                self.add_error('total_installments', 'Total installments is required for installment payments.')
            if installment_number and total_installments and installment_number > total_installments:
                self.add_error('installment_number', 'Installment number cannot be greater than total installments.')
        else:
            # If not an installment, ensure installment fields are cleared
            cleaned_data['installment_number'] = None
            cleaned_data['total_installments'] = None


        # --- User-specific validation ---
        if is_student_user:
            category_fee = cleaned_data.get('category_fee')
            if not category_fee:
                self.add_error('category_fee', 'Please select a fee type.')
            else:
                original_amount = category_fee.amount_due # Get the amount from the selected CategoryFee
                net_amount_due = original_amount # For students, assuming no discounts applied in form

                # Validate amount_received against net_amount_due for students
                if not is_installment: # If not an installment, amount_received must exactly match net_amount_due
                    # Using quantize for precise Decimal comparison
                    if amount_received is not None and amount_received.quantize(Decimal('0.01')) != net_amount_due.quantize(Decimal('0.01')):
                        self.add_error('amount_received', f'Amount paid (${amount_received:.2f}) must be equal to the full amount due (${net_amount_due:.2f}) for a full payment. Please pay the full amount or select "Is this an installment payment?".')
                # If it IS an installment, any positive amount_received is valid here.
                # The ledger will track the balance.

        elif is_staff_user:
            original_amount = cleaned_data.get('original_amount')
            discount_amount = cleaned_data.get('discount_amount', Decimal('0.00'))
            discount_percentage = cleaned_data.get('discount_percentage', Decimal('0.00'))
            term = cleaned_data.get('term')
            session = cleaned_data.get('session')
            payment_category = cleaned_data.get('payment_category')

            if not original_amount:
                self.add_error('original_amount', 'Original amount due is required.')
            if not term:
                self.add_error('term', 'Academic Term is required.')
            if not session:
                self.add_error('session', 'Academic Session is required.')
            if not payment_category:
                self.add_error('payment_category', 'Payment Category is required.')

            if original_amount is not None:
                calculated_net_due = original_amount
                if discount_percentage > 0:
                    calculated_net_due -= (original_amount * (discount_percentage / Decimal('100.00')))
                if discount_amount > 0:
                    calculated_net_due -= discount_amount

                if calculated_net_due < 0:
                    self.add_error(None, 'Total discount cannot exceed the original amount due.')

                # Validate amount_received against net_amount_due for staff (if not installment)
                if not is_installment:
                    # Using quantize for precise Decimal comparison
                    if amount_received is not None and amount_received.quantize(Decimal('0.01')) != calculated_net_due.quantize(Decimal('0.01')):
                        self.add_error('amount_received', f'Amount paid (${amount_received:.2f}) must be equal to the net amount due (${calculated_net_due:.2f}) for a full payment. Please pay the full amount or mark as installment.')
                # If it IS an installment, any positive amount_received is valid here.

        return cleaned_data
