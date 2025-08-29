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
    """
    category_fee = forms.ModelChoiceField(
        queryset=CategoryFee.objects.all().select_related('term', 'session', 'payment_category').order_by('session__name', 'term__name', 'payment_category__name', 'fee_name'),
        required=False,
        label="Select Fee Type",
        help_text="Select the specific fee (e.g., 'Tuition - Semester 1')",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Payment
        fields = [
            'student', 'category_fee',
            'original_amount', 'discount_amount', 'discount_percentage',
            'amount_received',
            'payment_method', 'transaction_id', 'notes',
            'term', 'session', 'payment_category',
            'is_installment', 'total_installments'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-control'}),
            'original_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'discount_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'e.g., 50.00'}),
            'discount_percentage': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100', 'placeholder': 'e.g., 10.00'}),
            'amount_received': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': 'Enter amount paid'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional transaction ID'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Any additional notes'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'payment_category': forms.Select(attrs={'class': 'form-control'}),
            'is_installment': forms.CheckboxInput(attrs={'class': 'form-checkbox h-5 w-5 text-blue-600'}),
            'total_installments': forms.HiddenInput(), # Hiding the input field
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
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        is_staff_user = self.user and self.user.is_staff
        is_student_user = self.user and hasattr(self.user, 'student')

        self.fields['term'].queryset = Term.objects.all().order_by('-start_date')
        self.fields['session'].queryset = Session.objects.all().order_by('-start_date')
        self.fields['payment_category'].queryset = PaymentCategory.objects.all().order_by('name')
        self.fields['category_fee'].empty_label = "-- Select a Fee Type --"

        if is_student_user:
            student_instance = self.user.student
            self.fields['student'].queryset = Student.objects.filter(pk=student_instance.pk)
            self.fields['student'].initial = student_instance.pk
            self.fields['student'].widget = forms.HiddenInput()

            self.fields['category_fee'].required = True
            
            del self.fields['original_amount']
            del self.fields['discount_amount']
            del self.fields['discount_percentage']
            
            self.fields['term'].required = False
            self.fields['term'].widget = forms.HiddenInput()
            self.fields['session'].required = False
            self.fields['session'].widget = forms.HiddenInput()
            self.fields['payment_category'].required = False
            self.fields['payment_category'].widget = forms.HiddenInput()

        elif is_staff_user:
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
            
        else:
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
        user = self.user
        is_staff_user = user and user.is_staff
        is_student_user = user and hasattr(user, 'student')
        amount_received = cleaned_data.get('amount_received')
        is_installment = cleaned_data.get('is_installment')
        
        if amount_received is None:
            self.add_error('amount_received', 'Amount paid is required.')
        elif amount_received <= 0:
            self.add_error('amount_received', 'Amount paid must be greater than zero.')

        if is_student_user:
            category_fee = cleaned_data.get('category_fee')
            if not category_fee:
                self.add_error('category_fee', 'Please select a fee type.')
            else:
                original_amount = category_fee.amount_due
                net_amount_due = original_amount
                if not is_installment:
                    if amount_received is not None and amount_received.quantize(Decimal('0.01')) != net_amount_due.quantize(Decimal('0.01')):
                        self.add_error('amount_received', f'Amount paid (N{amount_received:.2f}) must be equal to the full amount due (N{net_amount_due:.2f}) for a full payment. Please pay the full amount or select "Is this an installment payment?".')

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

                if not is_installment:
                    if amount_received is not None and amount_received.quantize(Decimal('0.01')) != calculated_net_due.quantize(Decimal('0.01')):
                        self.add_error('amount_received', f'Amount paid (N{amount_received:.2f}) must be equal to the net amount due (N{calculated_net_due:.2f}) for a full payment. Please pay the full amount or mark as installment.')

        return cleaned_data
    


# Parent make payment for child's form
class ParentPaymentForm(forms.ModelForm):
    category_fee = forms.ModelChoiceField(
        queryset=CategoryFee.objects.all().order_by('payment_category__name'),
        label="Payment Item",
        help_text="Select the fee you want to pay for."
    )

    class Meta:
        model = Payment
        fields = ['category_fee', 'amount_received']

    def __init__(self, *args, **kwargs):
        student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)

    def clean_amount_received(self):
        amount_received = self.cleaned_data.get('amount_received')
        category_fee = self.cleaned_data.get('category_fee')

        if category_fee and amount_received and amount_received > category_fee.amount_due:
            self.add_error('amount_received', 'The payment amount cannot exceed the fee amount.')
        return amount_received