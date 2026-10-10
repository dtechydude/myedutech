from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from .models import LessonNote

_CTRL = {'class': 'form-control'}
_SEL = {'class': 'form-select'}


class NoteForm(forms.ModelForm):
    class Meta:
        model = LessonNote
        fields = ('standard', 'subject_name', 'academic_session', 'term', 'week',
                  'title', 'doc_link', 'teacher_note')
        widgets = {
            'standard': forms.Select(attrs=_SEL),
            'subject_name': forms.TextInput(attrs={**_CTRL, 'placeholder': 'e.g. Mathematics'}),
            'academic_session': forms.TextInput(attrs={**_CTRL, 'placeholder': '2026/2027'}),
            'term': forms.Select(attrs=_SEL),
            'week': forms.NumberInput(attrs={**_CTRL, 'min': 1, 'max': 20}),
            'title': forms.TextInput(attrs={**_CTRL, 'placeholder': 'Leave blank to fill in automatically'}),
            'doc_link': forms.URLInput(attrs={**_CTRL, 'placeholder': 'https://docs.google.com/document/d/...'}),
            'teacher_note': forms.Textarea(attrs={**_CTRL, 'rows': 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['standard'].empty_label = 'Select class'

    def clean_subject_name(self):
        return ' '.join(self.cleaned_data['subject_name'].split())

    def clean(self):
        cleaned = super().clean()
        keys = ('standard', 'subject_name', 'academic_session', 'term', 'week')
        owner = self.instance.teacher if self.instance.pk else self.user
        if owner is not None and all(cleaned.get(k) not in (None, '') for k in keys):
            clash = LessonNote.objects.filter(
                teacher=owner, standard=cleaned['standard'],
                subject_name__iexact=cleaned['subject_name'],
                academic_session=cleaned['academic_session'],
                term=cleaned['term'], week=cleaned['week'],
            ).exclude(pk=self.instance.pk)
            if clash.exists():
                raise ValidationError(
                    'You have already submitted a note for this class, subject and week. '
                    'Open it and use Edit instead.')
        return cleaned


class NoteFilterForm(forms.Form):
    q = forms.CharField(required=False, widget=forms.TextInput(
        attrs={**_CTRL, 'placeholder': 'Search teacher, subject or title'}))
    status = forms.ChoiceField(required=False, widget=forms.Select(attrs=_SEL),
                               choices=[('', 'Any status')] + list(LessonNote.Status.choices))
    term = forms.ChoiceField(required=False, widget=forms.Select(attrs=_SEL),
                             choices=[('', 'Any term')] + list(LessonNote.Term.choices))
    session = forms.CharField(required=False, widget=forms.TextInput(
        attrs={**_CTRL, 'placeholder': 'Session e.g. 2026/2027'}))
    week = forms.IntegerField(required=False, min_value=1, max_value=20,
                              widget=forms.NumberInput(attrs={**_CTRL, 'placeholder': 'Week'}))
    standard = forms.ModelChoiceField(required=False, queryset=None, empty_label='Any class',
                                      widget=forms.Select(attrs=_SEL))
    teacher = forms.ModelChoiceField(required=False, queryset=None, empty_label='Any teacher',
                                     widget=forms.Select(attrs=_SEL))

    def __init__(self, *args, show_teacher=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['standard'].queryset = apps.get_model('curriculum', 'Standard').objects.all()
        if show_teacher:
            User = get_user_model()
            teachers = User.objects.filter(
                pk__in=LessonNote.objects.values('teacher')).order_by('first_name', 'username')
            self.fields['teacher'].queryset = teachers
            self.fields['teacher'].label_from_instance = lambda u: u.get_full_name() or u.get_username()
        else:
            del self.fields['teacher']


class SummaryFilterForm(forms.Form):
    session = forms.CharField(required=False, widget=forms.TextInput(
        attrs={**_CTRL, 'placeholder': 'Session e.g. 2026/2027'}))
    term = forms.ChoiceField(required=False, widget=forms.Select(attrs=_SEL),
                             choices=[('', 'Any term')] + list(LessonNote.Term.choices))


class ReviewForm(forms.Form):
    decision = forms.ChoiceField(choices=[('approve', 'Approve'), ('request_changes', 'Request changes')])
    remark = forms.CharField(required=False, max_length=1000,
                             widget=forms.Textarea(attrs={**_CTRL, 'rows': 3}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('decision') == 'request_changes' and not (cleaned.get('remark') or '').strip():
            self.add_error('remark', 'Tell the teacher what needs to change.')
        return cleaned