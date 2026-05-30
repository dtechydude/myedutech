"""
KwikSchools — Prep Report Card Forms
"""

from django import forms
from django.forms import modelformset_factory

from .models import (
    PrepReportCard, PrepSkillEntry, PrepDomainRating,
    PrepClass, PrepAcademicPeriod, RatingScale,
)


class PrepReportCardCommentForm(forms.ModelForm):
    """Form for saving teacher/head-teacher comments on a report card."""

    class_teacher_comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': "Class teacher's comment…",
        }),
        required=False,
        label="Class Teacher's Comment",
    )
    head_teacher_comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'form-control',
            'placeholder': "Head Teacher's comment…",
        }),
        required=False,
        label="Head Teacher's Comment",
    )
    days_present = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:100px'}),
        required=False,
        label="Days Present",
    )
    days_absent = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'width:100px'}),
        required=False,
        label="Days Absent",
    )
    promoted_to = forms.ModelChoiceField(
        queryset=None,  # set in __init__
        required=False,
        empty_label="— Not Yet Decided —",
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Promote To",
    )

    class Meta:
        model = PrepReportCard
        fields = [
            'class_teacher_comment',
            'head_teacher_comment',
            'days_present',
            'days_absent',
            'promoted_to',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from curriculum.models import Standard
        self.fields['promoted_to'].queryset = Standard.objects.all().order_by('name')


class PrepDomainRatingForm(forms.ModelForm):
    """Individual domain rating form (used in formset)."""

    class Meta:
        model = PrepDomainRating
        fields = ['rating_text']
        widgets = {
            'rating_text': forms.TextInput(attrs={
                'class': 'form-control form-control-sm',
                'maxlength': 50,
                'placeholder': 'e.g. Excellent, 4',
            })
        }


# Inline formset for domain ratings
PrepDomainRatingFormSet = modelformset_factory(
    PrepDomainRating,
    form=PrepDomainRatingForm,
    extra=0,
    can_delete=False,
)


class BulkCreateReportForm(forms.Form):
    """Admin form to bulk-create report cards for an entire class."""
    prep_class = forms.ModelChoiceField(
        queryset=PrepClass.objects.filter(is_active=True).select_related('standard'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Prep Class",
    )
    period = forms.ModelChoiceField(
        queryset=PrepAcademicPeriod.objects.select_related('session', 'term').order_by('-session__start_date', 'term__start_date'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Academic Period",
    )
    rating_scale = forms.ModelChoiceField(
        queryset=RatingScale.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        empty_label="— Use Default Scale —",
        label="Rating Scale",
    )

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('rating_scale'):
            default = RatingScale.objects.filter(is_default=True).first()
            if not default:
                raise forms.ValidationError(
                    "No default rating scale is set. Please select one or "
                    "configure a default in Admin."
                )
            cleaned['rating_scale'] = default
        return cleaned
