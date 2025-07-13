from django import forms
from curriculum.models import Term, Standard, Session# Import Standard



#works well 001
class ScoreEntryForm(forms.Form):
    """Form for a single student's score entry."""
    student_id = forms.IntegerField(widget=forms.HiddenInput())
    student_name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'readonly': 'readonly'}))
    score_id = forms.IntegerField(widget=forms.HiddenInput(), required=False) # To update existing scores

    ca1 = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'CA1', 'min': 0, 'max': 100})
    )
    ca2 = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'CA2', 'min': 0, 'max': 100})
    )
    ca3 = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'CA3', 'min': 0, 'max': 100})
    )
    exam_score = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'Exam', 'min': 0, 'max': 100})
    )

    def clean(self):
        cleaned_data = super().clean()
        ca1 = cleaned_data.get('ca1')
        ca2 = cleaned_data.get('ca2')
        ca3 = cleaned_data.get('ca3')
        exam_score = cleaned_data.get('exam_score')

        # Example validation: ensure scores are within a reasonable range (e.g., 0-100)
        # You can add more complex validation based on your school's grading system
        if ca1 is not None and (ca1 < 0 or ca1 > 100):
            self.add_error('ca1', "CA1 score must be between 0 and 100.")
        if ca2 is not None and (ca2 < 0 or ca2 > 100):
            self.add_error('ca2', "CA2 score must be between 0 and 100.")
        if ca3 is not None and (ca3 < 0 or ca3 > 100):
            self.add_error('ca3', "CA3 score must be between 0 and 100.")
        if exam_score is not None and (exam_score < 0 or exam_score > 100):
            self.add_error('exam_score', "Exam score must be between 0 and 100.")
       
        return cleaned_data


#in progress Worked For Each Term
class ReportCardFilterForm(forms.Form):
    """
    Form for selecting Term and Standard to filter students for report cards.
    """
    term = forms.ModelChoiceField(
        queryset=Term.objects.all().order_by('-start_date'), # Order by newest term first
        empty_label="Select Term",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}) # Add a class for potential styling
    )
    standard = forms.ModelChoiceField(
        queryset=Standard.objects.all().order_by('name'), # Order by standard name
        empty_label="Select Standard (Optional)", # Make it optional here for filtering all students in a term
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


#in progress for all the terms together
# schools/forms.py
# ... (Your existing forms like ScoreEntryForm, ReportCardFilterForm) ...

class SessionReportCardFilterForm(forms.Form):
    """
    Form for selecting Session and Standard to filter students for annual report cards.
    """
    session = forms.ModelChoiceField(
        queryset=Session.objects.all().order_by('-start_date'), # Order by newest session first
        empty_label="Select Session",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    standard = forms.ModelChoiceField(
        queryset=Standard.objects.all().order_by('name'),
        empty_label="Select Standard (Optional)",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
