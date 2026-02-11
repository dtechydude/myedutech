from django import forms
from .models import Quiz, Question
from results.models import Examination
from curriculum.models import Standard # Assuming this is where Standard lives
from django_ckeditor_5.widgets import CKEditor5Widget


class AdminQuizForm(forms.ModelForm):
    """
    Form for Admin / Staff to create a new Quiz.
    Teachers no longer use this form.
    """
    class Meta:
        model = Quiz
        fields = ['examination', 'subject', 'term', 'number_of_questions', 'time']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Apply bootstrap classes
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})



class QuestionForm(forms.ModelForm):

    MCQ_CHOICES = [
        ('A', 'A'),
        ('B', 'B'),
        ('C', 'C'),
        ('D', 'D'),
    ]

    class Meta:
        model = Question
        fields = [
            'content',
            'question_type',
            'image_url',
            'option_a',
            'option_b',
            'option_c',
            'option_d',
            'correct_answer'
        ]
        widgets = {
            # ✅ CKEditor5 applied here
            'content': CKEditor5Widget(config_name='extends'),

            'question_type': forms.Select(attrs={'class': 'form-select'}),

            'image_url': forms.URLInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Paste Google Drive image link (optional)'
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Style option fields
        for field in ['option_a', 'option_b', 'option_c', 'option_d']:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

        # Default correct answer as text input
        self.fields['correct_answer'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter correct answer'
        })

        # Detect question type
        question_type = None

        if self.instance.pk:
            question_type = self.instance.question_type
        elif self.data.get('question_type'):
            question_type = self.data.get('question_type')

        # If MCQ → dropdown
        if question_type == 'MCQ':
            self.fields['correct_answer'].widget = forms.Select(
                choices=self.MCQ_CHOICES,
                attrs={'class': 'form-select'}
            )
