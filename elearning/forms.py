from django import forms
from .models import Lesson, Comment, Reply, Assignment, AssignmentSubmission


class LessonForm(forms.ModelForm):

    class Meta:
        model = Lesson
        fields = ('lesson_id', 'name', 'position', 'video', 'comment')
        widgets = {
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'cols': 70, 'placeholder': "Enter Your Comment"}),
        }


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
# ✅ NEW — Assignments / Homework
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
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'max_score': forms.NumberInput(attrs={'class': 'form-control'}),
        }


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
