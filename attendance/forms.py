# from tkinter import Widget
# from django import forms
# from django.contrib.auth.models import User
# from django.forms import modelformset_factory
# from attendance.models import Attendance




# # My attendance Logic
# class AttendanceForm(forms.ModelForm):
#     # This form will be used for each student in the formset
#     class Meta:
#         model = Attendance
#         fields = ['status'] # Only allow teacher to mark status
#         widgets = {
#             'status': forms.RadioSelect(choices=Attendance.STATUS_CHOICES),
#         }

# # This factory will create a form for each student
# # We'll use this in the view
# BaseAttendanceFormSet = modelformset_factory(
#     Attendance,
#     form=AttendanceForm,
#     extra=0, # We'll dynamically set the number of forms based on students
#     can_delete=False
# )

# # Custom formset to include student name for display
# class AttendanceFormSet(BaseAttendanceFormSet):
#     def __init__(self, *args, **kwargs):
#         self.students = kwargs.pop('students', None)
#         super().__init__(*args, **kwargs)
#         if self.students:
#             for i, form in enumerate(self.forms):
#                 # Attach student instance to each form for easy access in template
#                 form.instance.student = self.students[i]


# THIS MODULE IS WORKING WELL 1

# from django import forms
# from .models import Attendance
# from students.models import Student

# class AttendanceForm(forms.ModelForm):
#     # This field will be displayed, but its value will come from the instance
#     # It's primarily for display purposes in the formset
#     student_name = forms.CharField(
#         label="Student Name",
#         required=False, # Not required for submission, just display
#         widget=forms.TextInput(attrs={'readonly': 'readonly'}) # Make it read-only
#     )

#     class Meta:
#         model = Attendance
#         fields = ['id', 'student', 'present'] # Include 'id' for existing records, 'student' is hidden
#         widgets = {
#             'student': forms.HiddenInput(), # Hide the student ID, it's set by the initial data
#             'present': forms.CheckboxInput(attrs={'class': 'form-check-input'}) # Style if using Bootstrap
#         }

#     # Override the __init__ to populate student_name from the instance
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         if self.instance and self.instance.student:
#             self.fields['student_name'].initial = self.instance.student.first_name
#         else:
#             # For new forms in the formset, ensure student_name is set
#             # This is crucial if you're dynamically adding empty forms (though less common for attendance)
#             if 'initial' in kwargs and 'student' in kwargs['initial']:
#                 student_instance = Student.objects.get(pk=kwargs['initial']['student'])
#                 self.fields['student_name'].initial = student_instance.first_name



# # THIS MODULE WORK WELL WITH FIRST NAME AND LAST NAME
# from django import forms
# from .models import Attendance, Student

# class AttendanceForm(forms.ModelForm):
#     # Change from student_name to student_full_name
#     student_full_name = forms.CharField(
#         label="Student Name", # Label remains descriptive
#         required=False,
#         widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control-plaintext'}) # Add a class for styling
#     )

#     class Meta:
#         model = Attendance
#         fields = ['id', 'student', 'present']
#         widgets = {
#             'student': forms.HiddenInput(),
#             'present': forms.CheckboxInput(attrs={'class': 'form-check-input'})
#         }

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         if self.instance and self.instance.student:
#             # Use the get_full_name method from the Student model
#             self.fields['student_full_name'].initial = self.instance.student.get_full_name()
#         else:
#             # For new forms (though unlikely with extra=0), ensure name is set
#             if 'initial' in kwargs and 'student' in kwargs['initial']:
#                 try:
#                     student_instance = Student.objects.get(pk=kwargs['initial']['student'])
#                     self.fields['student_full_name'].initial = student_instance.get_full_name()
#                 except Student.DoesNotExist:
#                     self.fields['student_full_name'].initial = "Student Not Found" # Fallback


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
