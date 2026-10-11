from django import forms
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import LessonNote, subject_display
from .services import DUPLICATE_MESSAGE

_CTRL = {'class': 'form-control'}
_SEL = {'class': 'form-select'}


def subject_standard_field(subject_model=None):
    """
    If curriculum.Subject is tied to a class (a ForeignKey to Standard), return that
    field's name so the form can show only the chosen class's subjects; else None.
    """
    subject_model = subject_model or apps.get_model('curriculum', 'Subject')
    standard_model = apps.get_model('curriculum', 'Standard')
    for field in subject_model._meta.get_fields():
        if getattr(field, 'many_to_one', False) and field.related_model is standard_model:
            return field.name
    return None


class SubjectSelect(forms.Select):
    """A <select> whose options carry data-standard, so the page can filter them by class."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.standard_map = {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        standard_id = self.standard_map.get(getattr(value, 'value', value))
        if standard_id is not None:
            option['attrs']['data-standard'] = str(standard_id)
        return option


class NoteForm(forms.ModelForm):
    class Meta:
        model = LessonNote
        fields = ('standard', 'subject', 'academic_session', 'term', 'week',
                  'title', 'doc_link', 'teacher_note')
        widgets = {
            'standard': forms.Select(attrs=_SEL),
            'subject': SubjectSelect(attrs=_SEL),
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

        subject_field = self.fields['subject']
        subject_field.required = True            # optional on the model only for older notes
        subject_field.empty_label = 'Select subject'
        subject_field.label_from_instance = subject_display
        subjects = subject_field.queryset
        self.standard_field = subject_standard_field(subjects.model)
        if self.standard_field:
            subject_field.widget.standard_map = dict(subjects.values_list('pk', self.standard_field))

    def clean(self):
        cleaned = super().clean()
        subject, standard = cleaned.get('subject'), cleaned.get('standard')

        if subject and standard and self.standard_field:
            if getattr(subject, f'{self.standard_field}_id') != standard.pk:
                self.add_error('subject', 'This subject is not taught in the selected class.')

        keys = ('standard', 'subject', 'academic_session', 'term', 'week')
        owner = self.instance.teacher if self.instance.pk else self.user
        if owner is not None and all(cleaned.get(k) not in (None, '') for k in keys):
            clash = LessonNote.objects.filter(
                Q(subject=subject) | Q(subject__isnull=True, subject_name__iexact=subject_display(subject)),
                teacher=owner, standard=standard, academic_session=cleaned['academic_session'],
                term=cleaned['term'], week=cleaned['week'],
            ).exclude(pk=self.instance.pk)
            if clash.exists():
                raise ValidationError(DUPLICATE_MESSAGE)
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