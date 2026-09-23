from django import forms

from curriculum.models import Standard

from .constants import ACTIVE, ASSIGNABLE_CHOICES, STATUS_CHOICES


class StatusChangeForm(forms.Form):
    new_status = forms.ChoiceField(
        label='New status',
        choices=ASSIGNABLE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    reason = forms.CharField(
        label='Reason / note',
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 3,
            'placeholder': 'e.g. Suspended for two weeks following disciplinary hearing',
        }),
    )

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        if student is not None:
            # Offer every assignable status except the one the student already has.
            self.fields['new_status'].choices = [
                (value, label) for value, label in ASSIGNABLE_CHOICES
                if value != student.student_status
            ]

    def clean_reason(self):
        return (self.cleaned_data.get('reason') or '').strip()

    def clean(self):
        cleaned = super().clean()
        new_status = cleaned.get('new_status')
        if new_status and new_status != ACTIVE and not cleaned.get('reason'):
            self.add_error('reason', "Please give a reason — it is kept in the audit log.")
        return cleaned


class StudentStatusFilterForm(forms.Form):
    q = forms.CharField(
        required=False, label='Search',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name or USN'}),
    )
    status = forms.ChoiceField(
        required=False, label='Status',
        choices=[('', 'All statuses')] + STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    standard = forms.ModelChoiceField(
        required=False, label='Class',
        queryset=Standard.objects.none(), empty_label='All classes',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['standard'].queryset = Standard.objects.order_by('name')