from django import forms
from .models import Attendance, Student
from django.utils import timezone # For initial date values

# --- Form for taking attendance on a specific date ---
class AttendanceDateForm(forms.Form):
    # Use DateInput widget for a calendar picker in most browsers
    date = forms.DateField(
        label="Select Date",
        initial=timezone.localdate(), # Default to today's date
        widget=forms.DateInput(attrs={
            'type': 'date', # HTML5 date input
            'class': 'form-control'
        })
    )

# --- Form for taking individual student attendance (for formset) ---
class AttendanceForm(forms.ModelForm):
    student_full_name = forms.CharField(
        label="Student Name",
        required=False,
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control-plaintext'})
    )

    class Meta:
        model = Attendance
        fields = ['id', 'student', 'present']
        widgets = {
            'student': forms.HiddenInput(),
            'present': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.student:
            self.fields['student_full_name'].initial = self.instance.student.get_full_name()
        else:
            if 'initial' in kwargs and 'student' in kwargs['initial']:
                try:
                    student_instance = Student.objects.get(pk=kwargs['initial']['student'])
                    self.fields['student_full_name'].initial = student_instance.get_full_name()
                except Student.DoesNotExist:
                    self.fields['student_full_name'].initial = "Student Not Found"


# --- Form for generating attendance reports ---
class AttendanceReportForm(forms.Form):
    # Optional: Allow selecting a specific student
    student = forms.ModelChoiceField(
        queryset=Student.objects.none(), # Will be populated in the view based on teacher
        required=False,
        label="Select Student (Optional)",
        empty_label="All Students",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    start_date = forms.DateField(
        label="Start Date",
        initial=timezone.localdate(),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    end_date = forms.DateField(
        label="End Date",
        initial=timezone.localdate(),
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    def __init__(self, teacher, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter students based on the current teacher
        if teacher:
            self.fields['student'].queryset = Student.objects.filter(form_teacher=teacher).order_by('first_name', 'last_name')

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and start_date > end_date:
            self.add_error('end_date', "End date cannot be before start date.")
        return cleaned_data
