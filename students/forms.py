from tkinter import Widget
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from .models import Student


class StudentRegisterForm(forms.ModelForm):

    class Meta:
        model = Student
        fields = '__all__'
        
        # widgets = {
        #     'date_employed': forms.DateInput(
        #         format=('%d/%m/%Y'),
        #         attrs={'class': 'form-control', 
        #                'placeholder': 'Select a date',
        #                'type': 'date'  # <--- IF I REMOVE THIS LINE, THE INITIAL VALUE IS DISPLAYED
        #               }),

        #     'year': forms.DateInput(
        #         format=('%d/%m/%Y'),
        #         attrs={'class': 'form-control', 
        #                'placeholder': 'Select a date',
        #                'type': 'date'  # <--- IF I REMOVE THIS LINE, THE INITIAL VALUE IS DISPLAYED
        #               }),

        #  }

       # Widget = {'date_employed': forms.DateInput()}

class StudentUpdateForm(forms.ModelForm):

    class Meta:
        model = Student
        fields = '__all__'
        exclude = ('user', 'USN', 'student_status', 'badge', 'form_teacher', 'date_admitted', 'last_name', 'first_name',  'standard', 'class_on_admission', 'fee_balance')


class SuperUserStudentUpdateForm(forms.ModelForm):

    class Meta:
        model = Student
        fields = '__all__'
        exclude = ('fee_balance',)


# import students
import csv
import io
import logging
from django import forms
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

REQUIRED_HEADERS = [
    'USN', 'first_name', 'last_name', 'gender', 'DOB',
    'student_type', 'date_admitted',
]

OPTIONAL_HEADERS = [
    'middle_name', 'blood_group', 'genotype', 'health_remark',
    'guardian_name', 'guardian_phone', 'guardian_email',
    'guardian_address', 'relationship', 'student_status',
    'current_class', 'class_group',
]

ALL_HEADERS = REQUIRED_HEADERS + OPTIONAL_HEADERS


class StudentBulkUploadForm(forms.Form):
    """
    Form for validating CSV file uploads for bulk student creation.
    Accepts .csv files only. Max 5MB.
    """
    csv_file = forms.FileField(
        label='CSV File',
        help_text='Upload a .csv file with student data. Max size: 5MB.',
        widget=forms.FileInput(attrs={
            'accept': '.csv',
            'class': 'hidden',
            'id': 'csv-file-input',
        })
    )
    overwrite_existing = forms.BooleanField(
        required=False,
        label='Overwrite existing students (matched by USN)',
        initial=False,
    )

    def clean_csv_file(self):
        csv_file = self.cleaned_data.get('csv_file')
        if not csv_file:
            raise ValidationError('No file was uploaded.')

        # Validate extension
        if not csv_file.name.lower().endswith('.csv'):
            raise ValidationError('Only CSV files are accepted (.csv extension).')

        # Validate file size (5MB max)
        max_size = 5 * 1024 * 1024
        if csv_file.size > max_size:
            raise ValidationError(f'File size must not exceed 5MB. Your file is {csv_file.size / 1024 / 1024:.2f}MB.')

        # Validate CSV headers
        try:
            content = csv_file.read().decode('utf-8-sig')  # utf-8-sig handles BOM
            csv_file.seek(0)
            reader = csv.DictReader(io.StringIO(content))
            headers = [h.strip() for h in (reader.fieldnames or [])]

            missing = [h for h in REQUIRED_HEADERS if h not in headers]
            if missing:
                raise ValidationError(
                    f'Missing required columns: {", ".join(missing)}. '
                    f'Required columns are: {", ".join(REQUIRED_HEADERS)}'
                )

            # Check at least one data row
            rows = list(reader)
            if len(rows) == 0:
                raise ValidationError('The CSV file contains no data rows.')

            if len(rows) > 1000:
                raise ValidationError('Maximum 1,000 students per upload. Please split into smaller batches.')

        except UnicodeDecodeError:
            raise ValidationError('File encoding error. Please save your CSV file as UTF-8 and try again.')

        csv_file.seek(0)
        return csv_file




