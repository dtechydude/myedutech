from django import forms
from .models import Lesson, Comment, Reply, Assignment, AssignmentSubmission

# <input type="datetime-local"> only understands "YYYY-MM-DDTHH:MM". Django's
# default rendering ("YYYY-MM-DD HH:MM:SS") makes the browser show an EMPTY
# box when a teacher edits an existing assignment, so the due date appeared
# to vanish. Render and parse this format explicitly.
DATETIME_LOCAL_FORMAT = '%Y-%m-%dT%H:%M'


class LessonForm(forms.ModelForm):

    class Meta:
        model = Lesson
        # ✅ notes_link added — Google Drive link for the lesson file
        fields = ('lesson_id', 'name', 'position', 'video', 'notes_link', 'comment')
        widgets = {
            'lesson_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. MATH-JSS1-001'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Algebraic Expressions'}),
            'position': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'video': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://www.youtube.com/watch?v=...'}),
            'notes_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://drive.google.com/file/d/...'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'cols': 70, 'placeholder': "Enter Your Comment"}),
        }


class LessonUpdateForm(LessonForm):
    """
    Same widgets as LessonForm (so the create and update pages behave and look
    the same), but without `lesson_id` — a lesson's unique ID should not change
    once it exists.
    """

    class Meta(LessonForm.Meta):
        fields = ('name', 'position', 'video', 'notes_link', 'comment')

        

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ('body',)

        labels = {"body": "Comment:"}

        widgets = {
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'cols': 70, 'placeholder': "Enter Your Comment"}),
        }


class ReplyForm(forms.ModelForm):
    class Meta:
        model = Reply
        fields = ('reply_body',)

        widgets = {
            'reply_body': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'cols': 10}),
        }


# =====================================================================
# Assignments / Homework
# =====================================================================

class AssignmentForm(forms.ModelForm):
    """Used by teachers/staff to create or update an Assignment/Homework."""

    class Meta:
        model = Assignment
        fields = ('title', 'instructions', 'resource_link', 'due_date', 'max_score')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Worksheet 3 — Fractions'}),
            'resource_link': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://drive.google.com/... or https://yourschool.com/files/...'
            }),
            # ✅ FIX — explicit format so the existing due date shows when editing
            'due_date': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local'},
                format=DATETIME_LOCAL_FORMAT,
            ),
            'max_score': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['due_date'].input_formats = [
            DATETIME_LOCAL_FORMAT, '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M',
        ]

    def clean_max_score(self):
        score = self.cleaned_data.get('max_score')
        if score is not None and score < 1:
            raise forms.ValidationError("Maximum score must be at least 1.")
        return score


class AssignmentSubmissionForm(forms.ModelForm):
    """Used by students to submit an external link for an Assignment."""

    class Meta:
        model = AssignmentSubmission
        fields = ('submission_link', 'comment')
        labels = {
            'submission_link': 'Link to your work',
            'comment': 'Note to your teacher (optional)',
        }
        widgets = {
            'submission_link': forms.URLInput(attrs={
                'class': 'form-control form-control-sm',
                'placeholder': 'https://drive.google.com/... or https://yourschool.com/files/...'
            }),
            'comment': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2, 'placeholder': 'Optional note for your teacher'}),
        }