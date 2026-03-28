from django import forms
from curriculum.models import Term, Standard, Session# Import Standard
from.models import MotorAbilityScore, MidTermScore
from django.core.validators import MinValueValidator, MaxValueValidator
from django.forms import ValidationError




# # Score Entry For CA 40 & Exams 60
# class ScoreEntryForm(forms.Form):
#     """
#     Form for a single student's score entry, aligned with Score model constraints:
#     CA fields max 40, Exam field max 60.
#     """
#     student_id = forms.IntegerField(widget=forms.HiddenInput())
#     # Note: Using TextInput(attrs={'readonly': 'readonly'}) is fine for display
#     student_name = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'readonly': 'readonly'})) 
#     score_id = forms.IntegerField(widget=forms.HiddenInput(), required=False) 

#     # CA fields should have a MAX of 40 (based on your model definition)
#     ca1 = forms.DecimalField(
#         max_digits=5, decimal_places=2, required=False,
#         widget=forms.NumberInput(attrs={'placeholder': 'CA1 (Max 40)', 'min': 0, 'max': 40}),
#         # Use explicit validators for robust form-level checking
#         validators=[MinValueValidator(0), MaxValueValidator(40)] 
#     )
#     ca2 = forms.DecimalField(
#         max_digits=5, decimal_places=2, required=False,
#         widget=forms.NumberInput(attrs={'placeholder': 'CA2 (Max 40)', 'min': 0, 'max': 40}),
#         validators=[MinValueValidator(0), MaxValueValidator(40)] 
#     )
#     ca3 = forms.DecimalField(
#         max_digits=5, decimal_places=2, required=False,
#         widget=forms.NumberInput(attrs={'placeholder': 'CA3 (Max 40)', 'min': 0, 'max': 40}),
#         validators=[MinValueValidator(0), MaxValueValidator(40)] 
#     )
    
#     # Exam score should have a MAX of 60 (based on your model definition)
#     exam_score = forms.DecimalField(
#         max_digits=5, decimal_places=2, required=False,
#         widget=forms.NumberInput(attrs={'placeholder': 'Exam (Max 60)', 'min': 0, 'max': 60}),
#         validators=[MinValueValidator(0), MaxValueValidator(60)] 
#     )

#     def clean(self):
#         cleaned_data = super().clean()
#         ca1 = cleaned_data.get('ca1')
#         ca2 = cleaned_data.get('ca2')
#         ca3 = cleaned_data.get('ca3')
#         # exam_score = cleaned_data.get('exam_score') # Not needed for total CA check

#         # --- CRITICAL: Total CA Validation (Max 40) ---
#         # This mirrors the logic from your Score model's clean method to catch errors early.
#         total_ca = (ca1 or 0) + (ca2 or 0) + (ca3 or 0)
        
#         if total_ca > 40:
#             # Adding a general form error to capture the combined validation failure
#             # This will display at the top of the formset.
#             raise ValidationError('The combined total of CA scores (CA1 + CA2 + CA3) cannot exceed 40 for any student.')
            
#         return cleaned_data

# New logics for twiking the scores
class ScoreEntryForm(forms.Form):
    """
    Form for a single student's score entry with dynamic CA and Exam totals.
    Limits are passed during initialization from the view.
    """
    student_id = forms.IntegerField(widget=forms.HiddenInput())
    student_name = forms.CharField(
        max_length=200, 
        widget=forms.TextInput(attrs={'readonly': 'readonly', 'class': 'form-control-plaintext'})
    ) 
    score_id = forms.IntegerField(widget=forms.HiddenInput(), required=False) 

    # Fields defined without MaxValueValidator here because it will be added dynamically in __init__
    ca1 = forms.DecimalField(max_digits=5, decimal_places=2, required=False, validators=[MinValueValidator(0)])
    ca2 = forms.DecimalField(max_digits=5, decimal_places=2, required=False, validators=[MinValueValidator(0)])
    ca3 = forms.DecimalField(max_digits=5, decimal_places=2, required=False, validators=[MinValueValidator(0)])
    exam_score = forms.DecimalField(max_digits=5, decimal_places=2, required=False, validators=[MinValueValidator(0)])

    def __init__(self, *args, **kwargs):
        # Pop the dynamic limits passed from the view (with defaults just in case)
        self.max_ca = kwargs.pop('max_ca', 40)
        self.max_exam = kwargs.pop('max_exam', 60)
        super().__init__(*args, **kwargs)

        # Update CA fields with dynamic placeholders and max attributes
        for field_name in ['ca1', 'ca2', 'ca3']:
            self.fields[field_name].widget = forms.NumberInput(attrs={
                'placeholder': f'Max total: {self.max_ca}',
                'min': 0,
                'max': self.max_ca,
                'class': 'form-control ca-field'
            })

        # Update Exam field with dynamic placeholders and max attributes
        self.fields['exam_score'].widget = forms.NumberInput(attrs={
            'placeholder': f'Max: {self.max_exam}',
            'min': 0,
            'max': self.max_exam,
            'class': 'form-control'
        })

    def clean(self):
        cleaned_data = super().clean()
        ca1 = cleaned_data.get('ca1') or 0
        ca2 = cleaned_data.get('ca2') or 0
        ca3 = cleaned_data.get('ca3') or 0
        exam_score = cleaned_data.get('exam_score')

        # --- DYNAMIC: Total CA Validation ---
        total_ca = ca1 + ca2 + ca3
        if total_ca > self.max_ca:
            raise ValidationError(
                f'The combined total of CA scores ({total_ca}) cannot exceed {self.max_ca}.'
            )
            
        # --- DYNAMIC: Exam Score Validation ---
        if exam_score is not None and exam_score > self.max_exam:
            raise ValidationError(
                f'The exam score ({exam_score}) cannot exceed {self.max_exam}.'
            )
            
        return cleaned_data
    



class ReportCardFilterForm(forms.Form):
    """
    Form for selecting Term and Standard to filter students for report cards.
    Restricts the Standard dropdown for teachers to only their assigned class.
    """
    term = forms.ModelChoiceField(
        queryset=Term.objects.all().order_by('-start_date'),
        empty_label="Select Term",
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    standard = forms.ModelChoiceField(
        queryset=Standard.objects.all().order_by('name'),
        empty_label="Select Standard (Optional)",
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        # Pop the user object passed from the view
        user = kwargs.pop('user', None)
        super(ReportCardFilterForm, self).__init__(*args, **kwargs)

        if user:
            # Check if user is NOT a superuser or staff
            if not (user.is_superuser or user.is_staff):
                # If they are a teacher, restrict the 'standard' dropdown
                if hasattr(user, 'teacher'):
                    self.fields['standard'].queryset = Standard.objects.filter(
                        form_teacher=user.teacher
                    ).order_by('name')
                    
                    # Optional: Change the empty label to be more specific for teachers
                    self.fields['standard'].empty_label = "Select Your Class"
                else:
                    # If for some reason a student or someone else accesses this, 
                    # show nothing in standard to be safe
                    self.fields['standard'].queryset = Standard.objects.none()



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

    def __init__(self, *args, **kwargs):
        # Extract the user passed from the view
        user = kwargs.pop('user', None)
        super(SessionReportCardFilterForm, self).__init__(*args, **kwargs)

        if user:
            # Check if user is a teacher (not superuser or staff)
            if not (user.is_superuser or user.is_staff):
                if hasattr(user, 'teacher'):
                    # Filter the standard dropdown to only show the teacher's assigned class
                    self.fields['standard'].queryset = Standard.objects.filter(
                        form_teacher=user.teacher
                    ).order_by('name')
                    
                    # Update label to reflect the restriction
                    self.fields['standard'].empty_label = "Select Your Assigned Class"
                else:
                    # Fallback for users with no teacher profile
                    self.fields['standard'].queryset = Standard.objects.none()


class MotorAbilityScoreForm(forms.ModelForm):
    class Meta:
        model = MotorAbilityScore
        fields = [
            'honesty', 'politeness', 'neatness', 'cooperation', 'punctuality', 'leadership', 'attitude', 'emotional_stability', 'perseverance', 'attentiveness',   
            'obedience', 'punctuality', 'musical', 'physical_education', 'games', 'handwriting', 'reading', 'verbal_fluency', 'handling_tools'
        ]
        widgets = {
            'honesty': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'politeness': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'neatness': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'cooperation': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'obedience': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'punctuality': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'leadership': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'attitude': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'emotional_stability': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'perseverance': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'attentiveness': forms.NumberInput(attrs={'min': 1, 'max': 5}),

            'musical': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'physical_education': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'games': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'handwriting': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'reading': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'verbal_fluency': forms.NumberInput(attrs={'min': 1, 'max': 5}),
            'handling_tools': forms.NumberInput(attrs={'min': 1, 'max': 5}),

        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            self.fields[field_name].required = True # Make all fields required
            self.fields[field_name].widget.attrs.update({
                'class': 'form-control', # For Bootstrap styling
                'placeholder': '1-5'
            })


class MidTermScoreForm(forms.ModelForm):

    class Meta:
        model = MidTermScore
        fields = ['exam_total_score']
        widgets = {
            'exam_total_score': forms.NumberInput(attrs={
                'class': 'form-control form-control-score',
                'style': 'max-width:120px; text-align:center;'
            })
        }

    def __init__(self, *args, **kwargs):
        self.max_score = kwargs.pop('max_score', None)
        super().__init__(*args, **kwargs)

    def clean_exam_total_score(self):
        score = self.cleaned_data.get('exam_total_score')

        if score is None:
            return score

        if self.max_score and score > self.max_score:
            raise forms.ValidationError(
                f"Score cannot exceed {self.max_score}"
            )

        return score
