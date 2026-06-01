# """
# KwikSchools — Prep Report Card Admin
# ======================================
# """

# from django.contrib import admin
# from django.utils.html import format_html

# from .models import (
#     PrepClass, RatingScale, RatingColumn,
#     PrepSubjectSkill, PrepAcademicPeriod,
#     PrepReportCard, PrepSkillEntry,
#     PrepDomainRating, PrepDomainTraitTemplate,
# )


# # ---------------------------------------------------------------------------
# # Inline classes
# # ---------------------------------------------------------------------------

# class RatingColumnInline(admin.TabularInline):
#     model = RatingColumn
#     extra = 1
#     ordering = ['order']
#     fields = ['label', 'order']


# class PrepSubjectSkillInline(admin.TabularInline):
#     model = PrepSubjectSkill
#     extra = 2
#     ordering = ['order']
#     fields = ['description', 'prep_class', 'order', 'is_active']


# class PrepSkillEntryInline(admin.TabularInline):
#     model = PrepSkillEntry
#     extra = 0
#     readonly_fields = ['skill', 'selected_column', 'entered_by', 'entered_at']
#     can_delete = False

#     def has_add_permission(self, request, obj=None):
#         return False


# class PrepDomainRatingInline(admin.TabularInline):
#     model = PrepDomainRating
#     extra = 0
#     fields = ['domain', 'trait_name', 'rating_text', 'order']
#     ordering = ['domain', 'order']


# class PrepDomainTraitTemplateInline(admin.TabularInline):
#     model = PrepDomainTraitTemplate
#     extra = 2
#     fields = ['domain', 'trait_name', 'order']
#     ordering = ['domain', 'order']


# # ---------------------------------------------------------------------------
# # Model admins
# # ---------------------------------------------------------------------------

# @admin.register(PrepClass)
# class PrepClassAdmin(admin.ModelAdmin):
#     list_display = ['standard', 'is_active', 'created_at']
#     list_filter = ['is_active']
#     search_fields = ['standard__name']
#     inlines = [PrepDomainTraitTemplateInline]

#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related('standard')


# @admin.register(RatingScale)
# class RatingScaleAdmin(admin.ModelAdmin):
#     list_display = ['name', 'is_default', 'column_summary', 'created_at']
#     list_filter = ['is_default']
#     search_fields = ['name']
#     inlines = [RatingColumnInline]

#     def column_summary(self, obj):
#         cols = obj.columns.order_by('order').values_list('label', flat=True)
#         return " | ".join(cols) if cols else "—"
#     column_summary.short_description = "Columns"


# @admin.register(PrepSubjectSkill)
# class PrepSubjectSkillAdmin(admin.ModelAdmin):
#     list_display = ['subject', 'description_short', 'prep_class', 'order', 'is_active']
#     list_filter = ['subject', 'prep_class', 'is_active']
#     search_fields = ['description', 'subject__name']
#     list_editable = ['order', 'is_active']
#     ordering = ['subject', 'order']

#     def description_short(self, obj):
#         return obj.description[:80] + ('…' if len(obj.description) > 80 else '')
#     description_short.short_description = "Skill / Objective"


# @admin.register(PrepAcademicPeriod)
# class PrepAcademicPeriodAdmin(admin.ModelAdmin):
#     list_display = [
#         '__str__', 'session', 'term', 'days_school_opened',
#         'next_term_begins', 'is_current_display',
#     ]
#     list_filter = ['session', 'term']
#     ordering = ['-session__start_date', 'term__start_date']
#     raw_id_fields = []
#     autocomplete_fields = []

#     def is_current_display(self, obj):
#         # is_current is now a @property derived from curriculum flags
#         from django.utils.html import format_html
#         if obj.is_current:
#             return format_html('<span style="color:green;font-weight:bold">✔ Current</span>')
#         return format_html('<span style="color:#aaa">—</span>')
#     is_current_display.short_description = "Current?"

#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related('session', 'term')


# @admin.register(PrepReportCard)
# class PrepReportCardAdmin(admin.ModelAdmin):
#     list_display = [
#         'student_name', 'prep_class', 'period', 'status',
#         'days_present', 'days_absent', 'promoted_to', 'created_at'
#     ]
#     list_filter = ['status', 'prep_class', 'period']
#     search_fields = [
#         'student__user__last_name', 'student__user__first_name',
#         'student__usn'
#     ]
#     readonly_fields = ['created_by', 'approved_by', 'created_at', 'updated_at']
#     inlines = [PrepSkillEntryInline, PrepDomainRatingInline]
#     actions = ['approve_selected', 'publish_selected']

#     def student_name(self, obj):
#         return obj.student_full_name
#     student_name.short_description = "Student"

#     def approve_selected(self, request, queryset):
#         updated = queryset.filter(status='submitted').update(
#             status='approved', approved_by=request.user
#         )
#         self.message_user(request, f"{updated} report card(s) approved.")
#     approve_selected.short_description = "Approve selected report cards"

#     def publish_selected(self, request, queryset):
#         updated = queryset.filter(status='approved').update(status='published')
#         self.message_user(request, f"{updated} report card(s) published.")
#     publish_selected.short_description = "Publish selected report cards"

#     def get_queryset(self, request):
#         return super().get_queryset(request).select_related(
#             'student__user', 'prep_class__standard', 'period'
#         )


# @admin.register(PrepDomainTraitTemplate)
# class PrepDomainTraitTemplateAdmin(admin.ModelAdmin):
#     list_display = ['trait_name', 'domain', 'prep_class', 'order']
#     list_filter = ['domain', 'prep_class']
#     list_editable = ['order']
#     ordering = ['domain', 'order']





"""
KwikSchools — Prep Report Card Admin  (complete, production-ready)
===================================================================

ROOT CAUSE OF THE EMPTY INLINE (diagnosed from full models.py)
──────────────────────────────────────────────────────────────
PrepSkillEntry rows are created by _populate_card() which is ONLY
called by services.create_report_card().  The Django admin NEVER
calls that service — it calls ModelAdmin.save_model() directly.
So on any card created through the admin, zero PrepSkillEntry rows
existed, giving an inline with headers but no rows.

SECONDARY BUG (previous fix attempt)
─────────────────────────────────────
The previous inline mixed Python callable names ('subject_display',
'skill_display') into the 'fields' tuple alongside real model field
names.  Django's BaseInlineFormSet.full_clean() iterates 'fields' and
tries to resolve each entry as a model field name — callables aren't
field names so the formset silently dropped those columns and could
not build valid forms.  Result: still no visible rows / widgets.

WHAT THIS FILE DOES
────────────────────
1. PrepSkillEntryInline
   • readonly_fields lists ONLY real field names + callable strings
     that are defined as methods on the ModelAdmin/Inline class
   • fields lists ONLY real model field names
   • get_queryset returns none() on /add/ (no card pk yet)
   • formfield_for_foreignkey scopes 'selected_column' to this
     card's RatingScale columns only
   • formfield_for_foreignkey scopes 'skill' to skills active for
     this PrepClass — prevents selecting skills from other classes

2. PrepReportCardAdmin.save_model()
   • Stamps created_by on first save (readonly field, form skips it)
   • Calls _populate_card() immediately after first save so the
     change-page redirect already has skill rows ready

3. PrepReportCardAdmin custom URL + populate button
   • /admin/prep_reports/prepreportcard/<id>/populate-skills/
     lets admins fix any card that was created before this patch
   • change_form.html renders a status banner + button prominently

4. Bulk action 'repopulate_skill_entries'
   • Select multiple cards in list view → re-run _populate_card()
   • Safe: bulk_create uses ignore_conflicts=True in _populate_card()
"""
from django import forms
from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import get_object_or_404, redirect

from .models import (
    PrepClass, RatingScale, RatingColumn,
    PrepSubjectSkill, PrepAcademicPeriod,
    PrepReportCard, PrepSkillEntry,
    PrepDomainRating, PrepDomainTraitTemplate,
)


# ═══════════════════════════════════════════════════════════════════
# Inlines — unchanged from original
# ═══════════════════════════════════════════════════════════════════

class RatingColumnInline(admin.TabularInline):
    model = RatingColumn
    extra = 1
    ordering = ['order']
    fields = ['label', 'order']


class PrepSubjectSkillInline(admin.TabularInline):
    model = PrepSubjectSkill
    extra = 2
    ordering = ['order']
    fields = ['description', 'prep_class', 'order', 'is_active']


# class PrepDomainRatingInline(admin.TabularInline):
#     model = PrepDomainRating
#     extra = 0
#     fields = ['domain', 'trait_name', 'rating_text', 'order']
#     ordering = ['domain', 'order']

# ═══════════════════════════════════════════════════════════════════
# NEW — Scoped Domain Rating Form (surgical correction only)
# ═══════════════════════════════════════════════════════════════════

# class PrepDomainRatingForm(forms.ModelForm):
#     class Meta:
#         model = PrepDomainRating
#         fields = '__all__'

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

#         card = None

#         if self.instance and self.instance.pk:
#             card = self.instance.report_card

#         elif getattr(self, 'parent_instance', None):
#             card = self.parent_instance

#         if card and card.prep_class:
#             qs = PrepDomainTraitTemplate.objects.filter(
#                 prep_class=card.prep_class
#             ).order_by('domain', 'order')

#             choices = [('', '---------')]
#             seen = set()

#             for t in qs:
#                 key = (t.domain, t.trait_name)
#                 if key not in seen:
#                     seen.add(key)
#                     choices.append((t.trait_name, t.trait_name))

#             self.fields['trait_name'] = forms.ChoiceField(
#                 choices=choices,
#                 required=False,
#                 label='Trait',
#             )

#         # Only rating should be required
#         self.fields['rating_text'].required = False


# class PrepDomainRatingInline(admin.TabularInline):
#     model = PrepDomainRating
#     form = PrepDomainRatingForm
#     extra = 0
#     fields = ['domain', 'trait_name', 'rating_text', 'order']
#     ordering = ['domain', 'order']

#     def get_formset(self, request, obj=None, **kwargs):
#         formset = super().get_formset(request, obj, **kwargs)
#         formset.parent_instance = obj

#         original_init = formset.form.__init__

#         def form_init(form_self, *args, **kw):
#             original_init(form_self, *args, **kw)
#             form_self.parent_instance = obj

#         formset.form.__init__ = form_init
#         return formset


# # Remaining admin.py logic unchanged from user's working version.
# # Apply this block by replacing ONLY the old PrepDomainRatingInline
# # and adding PrepDomainRatingForm above it.


# """
# PrepDomainRatingInline — corrected for BOTH existing and NEW inline rows
# =======================================================================

# FIX APPLIED
# ───────────
# The previous patch only populated trait dropdowns for existing rows
# because it relied on instance/parent form binding.

# This correction makes BOTH dropdowns work on:

# ✓ Existing PrepDomainRating rows
# ✓ NEW "Add another Prep Domain Rating" rows
# ✓ Psychomotor domain
# ✓ Affective/Cognitive domain

# WITHOUT changing your existing logic.

# HOW IT WORKS
# ────────────
# 1. Domain remains dropdown (model choice/choices field)
# 2. Trait Name becomes dependent dropdown
# 3. Trait dropdown is scoped to:
#       current PrepReportCard
#       → current prep_class
#       → PrepDomainTraitTemplate
#       → selected domain
# 4. JS hook updates trait choices instantly when domain changes
# 5. rating_text remains the only real data entry

# No logic changes to:
# - _populate_card()
# - report workflow
# - approvals
# - save_model
# - skill entries
# - URLs
# - queryset logic
# """

# from django import forms
# from django.contrib import admin
# from .models import (
#     PrepDomainRating,
#     PrepDomainTraitTemplate,
# )


# # ═══════════════════════════════════════════════════════════════════
# # Dynamic form
# # ═══════════════════════════════════════════════════════════════════

# class PrepDomainRatingForm(forms.ModelForm):

#     class Meta:
#         model = PrepDomainRating
#         fields = '__all__'

#     def __init__(self, *args, **kwargs):
#         card = kwargs.pop('card', None)
#         super().__init__(*args, **kwargs)

#         self.fields['trait_name'].required = False
#         self.fields['rating_text'].required = False

#         trait_choices = [('', '---------')]

#         selected_domain = None

#         if self.instance and self.instance.pk:
#             selected_domain = self.instance.domain
#             if not card:
#                 card = self.instance.report_card

#         if self.data.get('domain'):
#             selected_domain = self.data.get('domain')

#         if card and card.prep_class and selected_domain:
#             qs = (
#                 PrepDomainTraitTemplate.objects
#                 .filter(
#                     prep_class=card.prep_class,
#                     domain=selected_domain,
#                 )
#                 .order_by('order')
#             )

#             trait_choices += [
#                 (t.trait_name, t.trait_name)
#                 for t in qs
#             ]

#         self.fields['trait_name'] = forms.ChoiceField(
#             label='Trait',
#             choices=trait_choices,
#             required=False,
#         )


# # ═══════════════════════════════════════════════════════════════════
# # Inline — corrected for Add Another rows
# # ═══════════════════════════════════════════════════════════════════

# class PrepDomainRatingInline(admin.TabularInline):
#     model = PrepDomainRating
#     form = PrepDomainRatingForm
#     extra = 1
#     fields = ['domain', 'trait_name', 'rating_text', 'order']
#     ordering = ['domain', 'order']

#     def get_formset(self, request, obj=None, **kwargs):
#         FormSet = super().get_formset(request, obj, **kwargs)

#         class ScopedFormSet(FormSet):
#             def _construct_form(self, i, **kw):
#                 kw['card'] = obj
#                 return super()._construct_form(i, **kw)

#         return ScopedFormSet

#     class Media:
#         js = (
#             'admin/js/jquery.init.js',
#             'prep_reports/js/domain_trait_filter.js',
#         )


# """
# Create this JS file:

# static/prep_reports/js/domain_trait_filter.js

# This enables NEW "Add another" rows to update Trait dropdown
# when Domain changes.
# """

# from django import forms
# from django.contrib import admin

# from .models import (
#     PrepDomainRating,
#     PrepDomainTraitTemplate,
# )


# # ═══════════════════════════════════════════════════════════════════
# # PrepDomainRatingForm
# # ═══════════════════════════════════════════════════════════════════

# class PrepDomainRatingForm(forms.ModelForm):

#     class Meta:
#         model = PrepDomainRating
#         fields = '__all__'

#     def __init__(self, *args, **kwargs):
#         card = kwargs.pop('card', None)
#         super().__init__(*args, **kwargs)

#         # Rating is the only required field
#         self.fields['rating_text'].required = True
#         self.fields['trait_name'].required = False

#         selected_domain = None

#         # Existing saved row
#         if self.instance and self.instance.pk:
#             selected_domain = self.instance.domain
#             if not card:
#                 card = self.instance.report_card

#         # Posted form row
#         posted_domain = self.data.get(
#             self.add_prefix('domain')
#         )
#         if posted_domain:
#             selected_domain = posted_domain

#         trait_choices = [
#             ('', '---------')
#         ]

#         if (
#             card
#             and card.prep_class
#             and selected_domain
#         ):
#             qs = (
#                 PrepDomainTraitTemplate.objects
#                 .filter(
#                     prep_class=card.prep_class,
#                     domain=selected_domain,
#                 )
#                 .order_by('order')
#             )

#             trait_choices += [
#                 (t.trait_name, t.trait_name)
#                 for t in qs
#             ]

#         self.fields['trait_name'] = forms.ChoiceField(
#             label='Trait',
#             choices=trait_choices,
#             required=False,
#         )


# # ═══════════════════════════════════════════════════════════════════
# # PrepDomainRatingInline
# # ═══════════════════════════════════════════════════════════════════

# class PrepDomainRatingInline(admin.TabularInline):
#     model = PrepDomainRating
#     form = PrepDomainRatingForm
#     extra = 1
#     fields = [
#         'domain',
#         'trait_name',
#         'rating_text',
#         'order',
#     ]
#     ordering = [
#         'domain',
#         'order',
#     ]

#     def get_formset(self, request, obj=None, **kwargs):
#         FormSet = super().get_formset(
#             request,
#             obj,
#             **kwargs
#         )

#         class ScopedFormSet(FormSet):
#             def _construct_form(
#                 self,
#                 i,
#                 **kw
#             ):
#                 kw['card'] = obj
#                 return super()._construct_form(
#                     i,
#                     **kw
#                 )

#         return ScopedFormSet

#     # Correct Django Media declaration
#     class Media:
#         js = (
#             'admin/js/jquery.init.js',
#             'static/prep_reports/js/domain_trait_filter.js',
#         )

# from django import forms
# from django.contrib import admin
# from django.core.exceptions import ValidationError
# from django.forms.models import BaseInlineFormSet
# from django.utils.safestring import mark_safe
# import json

# from .models import (
#     PrepDomainRating,
#     PrepDomainTraitTemplate,
# )


# # ═══════════════════════════════════════════════════════════════════
# # Inline Form
# # ═══════════════════════════════════════════════════════════════════

# class PrepDomainRatingForm(forms.ModelForm):

#     trait_name = forms.ChoiceField(
#         label='Trait',
#         required=False,
#         choices=[('', '---------')],
#     )

#     class Meta:
#         model = PrepDomainRating
#         fields = '__all__'

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

#         # Only rating required
#         self.fields['rating_text'].required = True
#         self.fields['trait_name'].required = False


# # ═══════════════════════════════════════════════════════════════════
# # Prevent duplicates
# # ═══════════════════════════════════════════════════════════════════

# class PrepDomainRatingInlineFormSet(BaseInlineFormSet):

#     def clean(self):
#         super().clean()

#         seen = set()

#         for form in self.forms:

#             if (
#                 not hasattr(form, 'cleaned_data')
#                 or form.cleaned_data.get('DELETE')
#             ):
#                 continue

#             domain = form.cleaned_data.get('domain')
#             trait = form.cleaned_data.get('trait_name')

#             if not domain or not trait:
#                 continue

#             key = (domain, trait)

#             if key in seen:
#                 raise ValidationError(
#                     f'Duplicate domain/trait entry: '
#                     f'{domain} → {trait}'
#                 )

#             seen.add(key)


# # ═══════════════════════════════════════════════════════════════════
# # Inline
# # ═══════════════════════════════════════════════════════════════════

# class PrepDomainRatingInline(admin.TabularInline):
#     model = PrepDomainRating
#     form = PrepDomainRatingForm
#     formset = PrepDomainRatingInlineFormSet
#     extra = 1

#     fields = [
#         'domain',
#         'trait_name',
#         'rating_text',
#         'order',
#     ]

#     ordering = [
#         'domain',
#         'order',
#     ]

#     class Media:
#         js = (
#             'admin/js/jquery.init.js',
#             'prep_reports/js/domain_trait_filter.js',
#         )

#     def get_formset(self, request, obj=None, **kwargs):

#         FormSet = super().get_formset(
#             request,
#             obj,
#             **kwargs
#         )

#         if obj and obj.prep_class:

#             qs = (
#                 PrepDomainTraitTemplate.objects
#                 .filter(
#                     prep_class=obj.prep_class
#                 )
#                 .order_by(
#                     'domain',
#                     'order'
#                 )
#             )

#             trait_map = {}

#             for t in qs:

#                 trait_map.setdefault(
#                     str(t.domain),
#                     []
#                 )

#                 trait_map[
#                     str(t.domain)
#                 ].append({
#                     'value': t.trait_name,
#                     'label': t.trait_name,
#                 })

#             request._prep_trait_map = mark_safe(
#                 json.dumps(trait_map)
#             )

#         else:
#             request._prep_trait_map = '{}'

#         return FormSet

#======================================================

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from .models import (
    PrepDomainRating,
    PrepDomainTraitTemplate,
)


# ==========================================================
# Form
# ==========================================================

# class PrepDomainRatingForm(forms.ModelForm):

#     class Meta:
#         model = PrepDomainRating
#         fields = '__all__'

#     def __init__(self, *args, **kwargs):
#         card = kwargs.pop('card', None)
#         super().__init__(*args, **kwargs)

#         self.fields['rating_text'].required = True
#         self.fields['trait_name'].required = False

#         trait_choices = [
#             ('', '---------')
#         ]

#         selected_domain = None

#         # Existing row
#         if self.instance and self.instance.pk:
#             selected_domain = self.instance.domain
#             if not card:
#                 card = self.instance.report_card

#         # POST / changed row
#         posted_domain = self.data.get(
#             self.add_prefix('domain')
#         )

#         if posted_domain:
#             selected_domain = posted_domain

#         # IMPORTANT:
#         # Always populate choices server-side
#         if (
#             card
#             and card.prep_class
#             and selected_domain
#         ):

#             qs = (
#                 PrepDomainTraitTemplate.objects
#                 .filter(
#                     prep_class=card.prep_class,
#                     domain=selected_domain,
#                 )
#                 .order_by('order')
#             )

#             trait_choices += [
#                 (
#                     t.trait_name,
#                     t.trait_name
#                 )
#                 for t in qs
#             ]

#         # preserve existing saved value
#         current_trait = getattr(
#             self.instance,
#             'trait_name',
#             None
#         )

#         if (
#             current_trait
#             and current_trait
#             not in [
#                 v
#                 for v, _ in trait_choices
#             ]
#         ):
#             trait_choices.append(
#                 (
#                     current_trait,
#                     current_trait
#                 )
#             )

#         self.fields['trait_name'].widget = (
#             forms.Select(
#                 choices=trait_choices
#             )
#         )

from django import forms
from django.core.exceptions import ValidationError

from .models import (
    PrepDomainRating,
    PrepDomainTraitTemplate,
)


class PrepDomainRatingForm(forms.ModelForm):

    class Meta:
        model = PrepDomainRating
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        card = kwargs.pop('card', None)
        super().__init__(*args, **kwargs)

        self.card = card

        self.fields['rating_text'].required = True
        self.fields['trait_name'].required = False

        trait_choices = [
            ('', '---------')
        ]

        selected_domain = None

        # Existing object
        if self.instance and self.instance.pk:
            selected_domain = self.instance.domain

            if not card:
                card = self.instance.report_card

        # POST row
        posted_domain = self.data.get(
            self.add_prefix('domain')
        )

        if posted_domain:
            selected_domain = posted_domain

        if (
            card
            and card.prep_class
            and selected_domain
        ):
            qs = (
                PrepDomainTraitTemplate.objects
                .filter(
                    prep_class=card.prep_class,
                    domain=selected_domain,
                )
                .order_by('order')
            )

            trait_choices += [
                (
                    t.trait_name,
                    t.trait_name
                )
                for t in qs
            ]

        current_trait = getattr(
            self.instance,
            'trait_name',
            None
        )

        if (
            current_trait
            and current_trait not in
            [v for v, _ in trait_choices]
        ):
            trait_choices.append(
                (
                    current_trait,
                    current_trait
                )
            )

        self.fields['trait_name'].widget = (
            forms.Select(
                choices=trait_choices
            )
        )

    # IMPORTANT
    # catches DB duplicates BEFORE save
    def clean(self):

        cleaned = super().clean()

        domain = cleaned.get('domain')
        trait = cleaned.get('trait_name')

        if not (
            self.card
            and self.card.pk
            and domain
            and trait
        ):
            return cleaned

        qs = (
            PrepDomainRating.objects
            .filter(
                report_card=self.card,
                domain=domain,
                trait_name=trait,
            )
        )

        if self.instance.pk:
            qs = qs.exclude(
                pk=self.instance.pk
            )

        if qs.exists():
            raise ValidationError(
                {
                    'trait_name':
                    (
                        f'"{trait}" already exists '
                        f'under {domain}.'
                    )
                }
            )

        return cleaned

# ==========================================================
# Duplicate prevention
# ==========================================================

# class PrepDomainRatingInlineFormSet(
#     BaseInlineFormSet
# ):

#     def clean(self):
#         super().clean()

#         seen = set()

#         for form in self.forms:

#             if (
#                 not hasattr(
#                     form,
#                     'cleaned_data'
#                 )
#                 or form.cleaned_data.get(
#                     'DELETE'
#                 )
#             ):
#                 continue

#             domain = form.cleaned_data.get(
#                 'domain'
#             )

#             trait = form.cleaned_data.get(
#                 'trait_name'
#             )

#             if not domain or not trait:
#                 continue

#             key = (
#                 str(domain),
#                 trait.strip().lower()
#             )

#             if key in seen:
#                 raise ValidationError(
#                     f'Duplicate entry: '
#                     f'{domain} → {trait}'
#                 )

#             seen.add(key)


# from django.core.exceptions import ValidationError
# from django.forms.models import BaseInlineFormSet


# class PrepDomainRatingInlineFormSet(
#     BaseInlineFormSet
# ):

#     def clean(self):
#         super().clean()

#         seen = set()

#         report_card = self.instance

#         # Existing DB rows excluding deleted ones
#         existing = set()

#         if report_card and report_card.pk:

#             existing_qs = (
#                 PrepDomainRating.objects
#                 .filter(
#                     report_card=report_card
#                 )
#             )

#             for obj in existing_qs:
#                 existing.add(
#                     (
#                         str(obj.domain),
#                         obj.trait_name.strip().lower(),
#                         obj.pk,
#                     )
#                 )

#         for form in self.forms:

#             if (
#                 not hasattr(form, 'cleaned_data')
#                 or not form.cleaned_data
#             ):
#                 continue

#             if form.cleaned_data.get('DELETE'):
#                 continue

#             domain = form.cleaned_data.get(
#                 'domain'
#             )

#             trait = form.cleaned_data.get(
#                 'trait_name'
#             )

#             if not domain or not trait:
#                 continue

#             key = (
#                 str(domain),
#                 trait.strip().lower(),
#             )

#             obj_pk = getattr(
#                 form.instance,
#                 'pk',
#                 None
#             )

#             # Prevent duplicate inside same submission
#             if key in seen:
#                 raise ValidationError(
#                     f'Duplicate domain/trait entry: '
#                     f'{domain} → {trait}'
#                 )

#             seen.add(key)

#             # Prevent duplicate against DB
#             for (
#                 db_domain,
#                 db_trait,
#                 db_pk,
#             ) in existing:

#                 if db_pk == obj_pk:
#                     continue

#                 if (
#                     db_domain == key[0]
#                     and db_trait == key[1]
#                 ):
#                     raise ValidationError(
#                         f'"{trait}" already exists under '
#                         f'{domain} for this report card.'
#                     )

from django.forms.models import BaseInlineFormSet
from django.core.exceptions import ValidationError


class PrepDomainRatingInlineFormSet(
    BaseInlineFormSet
):

    def clean(self):
        super().clean()

        seen = set()

        for form in self.forms:

            if (
                not hasattr(
                    form,
                    'cleaned_data'
                )
                or not form.cleaned_data
                or form.cleaned_data.get(
                    'DELETE'
                )
            ):
                continue

            domain = form.cleaned_data.get(
                'domain'
            )

            trait = form.cleaned_data.get(
                'trait_name'
            )

            if not domain or not trait:
                continue

            key = (
                str(domain),
                trait.strip().lower(),
            )

            if key in seen:
                raise ValidationError(
                    (
                        f'Duplicate entry in form: '
                        f'{domain} → {trait}'
                    )
                )

            seen.add(key)


# ==========================================================
# Inline
# ==========================================================

class PrepDomainRatingInline(
    admin.TabularInline
):
    model = PrepDomainRating
    form = PrepDomainRatingForm
    formset = PrepDomainRatingInlineFormSet

    extra = 1

    fields = [
        'domain',
        'trait_name',
        'rating_text',
        'order',
    ]

    ordering = [
        'domain',
        'order',
    ]

    class Media:
        js = (
            'admin/js/jquery.init.js',
            'prep_reports/js/domain_trait_filter.js',
        )

    def get_formset(
        self,
        request,
        obj=None,
        **kwargs
    ):

        BaseFormSet = super().get_formset(
            request,
            obj,
            **kwargs
        )

        class FormSet(
            BaseFormSet
        ):
            def _construct_form(
                self,
                i,
                **kw
            ):
                kw['card'] = obj
                return super()._construct_form(
                    i,
                    **kw
                )

        return FormSet




#==========================================================



class PrepDomainTraitTemplateInline(admin.TabularInline):
    model = PrepDomainTraitTemplate
    extra = 2
    fields = ['domain', 'trait_name', 'order']
    ordering = ['domain', 'order']


# ═══════════════════════════════════════════════════════════════════
# PrepSkillEntryInline — FULLY CORRECTED
# ═══════════════════════════════════════════════════════════════════

class PrepSkillEntryInline(admin.TabularInline):
    model = PrepSkillEntry
    extra = 0
    can_delete = False
    verbose_name = "Skill Entry"
    verbose_name_plural = "Skill Entries — select a rating column for each skill"
    show_change_link = False

    # ----------------------------------------------------------------
    # RULE: readonly_fields may contain real field names OR the string
    # names of methods defined on THIS inline class.  Nothing else.
    #
    # 'skill' is a real FK field rendered as read-only text (the teacher
    # should never re-assign a skill to a different PrepSubjectSkill).
    # 'entered_by' and 'entered_at' are audit fields — display only.
    # ----------------------------------------------------------------
    readonly_fields = ['skill', 'entered_by', 'entered_at']

    # ----------------------------------------------------------------
    # RULE: 'fields' must ONLY list real model field names.
    # Callable column names go in readonly_fields, NOT in fields.
    #
    # Model fields on PrepSkillEntry:
    #   report_card (excluded — it's the parent FK, auto-set by Django)
    #   skill            ← readonly identity
    #   selected_column  ← editable FK dropdown  ← THE ONE ADMINS FILL IN
    #   subject_comment  ← editable text
    #   entered_by       ← readonly audit
    #   entered_at       ← readonly audit
    # ----------------------------------------------------------------
    fields = ['skill', 'selected_column', 'subject_comment', 'entered_by', 'entered_at']

    # ----------------------------------------------------------------
    # Suppress on /add/ page — the card has no pk yet so _populate_card()
    # hasn't run and there are zero PrepSkillEntry rows in the DB.
    # After save_model() runs _populate_card() Django redirects to
    # /change/ where all rows exist and display correctly.
    # ----------------------------------------------------------------
    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related(
                'skill__subject',
                'selected_column',
                'entered_by',
            )
            .order_by('skill__subject__name', 'skill__order')
        )
        object_id = request.resolver_match.kwargs.get('object_id')
        if not object_id:
            return qs.none()
        return qs

    # Rows are created exclusively by _populate_card() — never manually.
    def has_add_permission(self, request, obj=None):
        return False

    # ----------------------------------------------------------------
    # Scope FK dropdowns to values that are valid for THIS card:
    #
    #  selected_column → only columns belonging to this card's RatingScale
    #  skill           → only active PrepSubjectSkills for this PrepClass
    #                    (or global skills where prep_class is NULL)
    #                    This prevents an admin accidentally re-assigning
    #                    a skill row to a skill from another class.
    # ----------------------------------------------------------------
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        object_id = request.resolver_match.kwargs.get('object_id')

        if db_field.name == 'selected_column':
            if object_id:
                try:
                    card = (
                        PrepReportCard.objects
                        .select_related('rating_scale')
                        .get(pk=object_id)
                    )
                    kwargs['queryset'] = (
                        RatingColumn.objects
                        .filter(scale=card.rating_scale)
                        .order_by('order')
                    )
                    # Allow blank so a rating can be cleared
                    kwargs['required'] = False
                except PrepReportCard.DoesNotExist:
                    kwargs['queryset'] = RatingColumn.objects.none()
            else:
                kwargs['queryset'] = RatingColumn.objects.none()

        elif db_field.name == 'skill':
            # Keep skill scoped so the read-only FK display is clean.
            # This does NOT make it editable — 'skill' stays in
            # readonly_fields above; this just prevents Django from
            # loading every PrepSubjectSkill row when building the form.
            if object_id:
                try:
                    card = PrepReportCard.objects.select_related(
                        'prep_class'
                    ).get(pk=object_id)
                    from django.db.models import Q
                    kwargs['queryset'] = PrepSubjectSkill.objects.filter(
                        is_active=True,
                    ).filter(
                        Q(prep_class=card.prep_class) |
                        Q(prep_class__isnull=True)
                    ).select_related('subject').order_by(
                        'subject__name', 'order'
                    )
                except PrepReportCard.DoesNotExist:
                    kwargs['queryset'] = PrepSubjectSkill.objects.none()
            else:
                kwargs['queryset'] = PrepSubjectSkill.objects.none()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ═══════════════════════════════════════════════════════════════════
# Unchanged model admins
# ═══════════════════════════════════════════════════════════════════

@admin.register(PrepClass)
class PrepClassAdmin(admin.ModelAdmin):
    list_display = ['standard', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['standard__name']
    inlines = [PrepDomainTraitTemplateInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('standard')


@admin.register(RatingScale)
class RatingScaleAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_default', 'column_summary', 'created_at']
    list_filter = ['is_default']
    search_fields = ['name']
    inlines = [RatingColumnInline]

    def column_summary(self, obj):
        cols = obj.columns.order_by('order').values_list('label', flat=True)
        return ' | '.join(cols) if cols else '—'
    column_summary.short_description = 'Columns'


@admin.register(PrepSubjectSkill)
class PrepSubjectSkillAdmin(admin.ModelAdmin):
    list_display = ['subject', 'description_short', 'prep_class', 'order', 'is_active']
    list_filter = ['subject', 'prep_class', 'is_active']
    search_fields = ['description', 'subject__name']
    list_editable = ['order', 'is_active']
    ordering = ['subject', 'order']

    def description_short(self, obj):
        return obj.description[:80] + ('…' if len(obj.description) > 80 else '')
    description_short.short_description = 'Skill / Objective'


@admin.register(PrepAcademicPeriod)
class PrepAcademicPeriodAdmin(admin.ModelAdmin):
    list_display = [
        '__str__', 'session', 'term', 'days_school_opened',
        'next_term_begins', 'is_current_display',
    ]
    list_filter = ['session', 'term']
    ordering = ['-session__start_date', 'term__start_date']

    def is_current_display(self, obj):
        if obj.is_current:
            return format_html(
                '<span style="color:green;font-weight:bold">✔ Current</span>'
            )
        return format_html('<span style="color:#aaa">—</span>')
    is_current_display.short_description = 'Current?'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('session', 'term')


# ═══════════════════════════════════════════════════════════════════
# PrepReportCardAdmin — FIXED
# ═══════════════════════════════════════════════════════════════════

@admin.register(PrepReportCard)
class PrepReportCardAdmin(admin.ModelAdmin):

    # ── List view ─────────────────────────────────────────────────
    list_display = [
        'student_name', 'prep_class', 'period', 'status',
        'skill_entry_count',
        'days_present', 'days_absent',
        'promoted_to', 'created_at',
    ]
    list_filter = ['status', 'prep_class', 'period']
    search_fields = [
        'student__user__last_name',
        'student__user__first_name',
        'student__usn',
    ]

    # ── Change / Add form ──────────────────────────────────────────
    # 'populate_button' is a readonly callable defined below — it renders
    # the populate link inline inside the fieldset so admins always see it.
    readonly_fields = [
        'created_by', 'approved_by', 'created_at', 'updated_at',
        'populate_button',
    ]
    fieldsets = [
        ('Student & Period', {
            'fields': [
                'student', 'prep_class', 'period', 'rating_scale', 'status',
            ],
        }),
        ('Attendance', {
            'fields': ['days_present', 'days_absent'],
        }),
        ('Remarks', {
            'fields': ['class_teacher_comment', 'head_teacher_comment'],
        }),
        ('Promotion', {
            'fields': ['promoted_to'],
        }),
        ('Audit', {
            'fields': ['created_by', 'approved_by', 'created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
        ('Skill Entry Population', {
            'fields': ['populate_button'],
            'description': (
                'After saving a new card, click the button below to pull all '
                'active PrepSubjectSkills for this prep class into the '
                'Skill Entries inline below.'
            ),
        }),
    ]
    inlines = [PrepSkillEntryInline, PrepDomainRatingInline]
    actions = ['approve_selected', 'publish_selected', 'repopulate_skill_entries']

    # Custom template — adds a prominent status banner above the form
    change_form_template = (
        'prep_reports/admin/prepreportcard/change_form.html'
    )

    # ── Custom URL: the populate action endpoint ───────────────────
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<int:card_id>/populate-skills/',
                self.admin_site.admin_view(self._populate_skills_view),
                name='prep_reports_prepreportcard_populate_skills',
            ),
        ]
        return custom + urls

    def _populate_skills_view(self, request, card_id):
        """
        Triggers _populate_card() for an existing card then redirects
        back to its change page.  Safe to call multiple times —
        _populate_card uses bulk_create(ignore_conflicts=True).
        """
        from .services import _populate_card

        card = get_object_or_404(PrepReportCard, pk=card_id)
        _populate_card(card, card.prep_class, request.user)

        count = card.skill_entries.count()
        self.message_user(
            request,
            (
                f'✔ Skill entries populated — {count} row(s) now exist for '
                f'{card.student_full_name}. '
                f'Scroll down to the Skill Entries section to enter ratings.'
            ),
            messages.SUCCESS,
        )
        return redirect(
            f'/admin/prep_reports/prepreportcard/{card_id}/change/'
        )

    # ── Readonly field: populate button rendered in fieldset ───────
    def populate_button(self, obj):
        if not (obj and obj.pk):
            return format_html(
                '<span style="color:#718096">'
                'Save this card first — skills will be auto-populated '
                'on first save, or use this button afterwards.'
                '</span>'
            )
        count = obj.skill_entries.count()
        url = (
            f'/admin/prep_reports/prepreportcard/{obj.pk}/populate-skills/'
        )
        if count:
            btn_style = 'background:#c8952a;'
            btn_label = f'↺ Re-populate ({count} entries already exist)'
            note = (
                'All existing entries are preserved (ignore_conflicts). '
                'Only missing rows are added.'
            )
        else:
            btn_style = 'background:#e53e3e;'
            btn_label = '⚡ Populate Skill Entries NOW'
            note = (
                'No skill entries found for this card. '
                'Click to pull them from the active PrepSubjectSkills.'
            )
        return format_html(
            '<a href="{}" style="{}color:#fff;padding:7px 16px;'
            'border-radius:4px;text-decoration:none;font-weight:600;'
            'font-size:13px;display:inline-block;margin-bottom:6px">{}</a>'
            '<br><small style="color:#718096">{}</small>',
            url, btn_style, btn_label, note,
        )
    populate_button.short_description = 'Populate Skill Entries'

    # ── save_model: stamp created_by + auto-populate on first save ─
    def save_model(self, request, obj, form, change):
        is_new = (obj.pk is None)

        if is_new and not obj.created_by_id:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)

        if is_new:
            from .services import _populate_card
            _populate_card(obj, obj.prep_class, request.user)
            count = obj.skill_entries.count()
            self.message_user(
                request,
                (
                    f'Report card created and {count} skill entry row(s) '
                    f'auto-populated from the active PrepSubjectSkills for '
                    f'{obj.prep_class.standard}. '
                    f'Scroll down to Skill Entries to enter the ratings.'
                ),
                messages.SUCCESS,
            )

    # ── List display helpers ───────────────────────────────────────
    def student_name(self, obj):
        return obj.student_full_name
    student_name.short_description = 'Student'
    student_name.admin_order_field = 'student__user__last_name'

    def skill_entry_count(self, obj):
        count = obj._skill_entry_count   # set by annotate in get_queryset
        if count == 0:
            return format_html(
                '<span style="color:#e53e3e;font-weight:bold">'
                '0 ⚠ needs populate'
                '</span>'
            )
        return format_html(
            '<span style="color:#276749;font-weight:bold">{}</span>',
            count,
        )
    skill_entry_count.short_description = '# Skills'
    skill_entry_count.admin_order_field = '_skill_entry_count'

    # ── Bulk actions ───────────────────────────────────────────────
    def approve_selected(self, request, queryset):
        updated = queryset.filter(status='submitted').update(
            status='approved', approved_by=request.user
        )
        self.message_user(request, f'{updated} report card(s) approved.')
    approve_selected.short_description = 'Approve selected report cards'

    def publish_selected(self, request, queryset):
        updated = queryset.filter(status='approved').update(status='published')
        self.message_user(request, f'{updated} report card(s) published.')
    publish_selected.short_description = 'Publish selected report cards'

    def repopulate_skill_entries(self, request, queryset):
        """
        Bulk-fix cards that have zero skill entries (created before this fix).
        Also safe to run on cards that already have entries.
        """
        from .services import _populate_card
        total_cards = 0
        total_entries = 0
        for card in queryset.select_related('prep_class'):
            before = card.skill_entries.count()
            _populate_card(card, card.prep_class, request.user)
            after = card.skill_entries.count()
            total_entries += (after - before)
            total_cards += 1
        self.message_user(
            request,
            (
                f'Processed {total_cards} card(s). '
                f'{total_entries} new skill entry row(s) created.'
            ),
            messages.SUCCESS,
        )
    repopulate_skill_entries.short_description = (
        '⚡ Populate / re-populate skill entries for selected cards'
    )

    # ── Queryset with annotation ───────────────────────────────────
    def get_queryset(self, request):
        from django.db.models import Count
        return (
            super()
            .get_queryset(request)
            .select_related('student__user', 'prep_class__standard', 'period')
            .annotate(_skill_entry_count=Count('skill_entries'))
        )
    
    # New Def
    def changeform_view(
        self,
        request,
        object_id=None,
        form_url='',
        extra_context=None
    ):

        extra_context = extra_context or {}

        extra_context[
            'prep_trait_map'
        ] = getattr(
            request,
            '_prep_trait_map',
            '{}'
        )

        return super().changeform_view(
            request,
            object_id,
            form_url,
            extra_context,
        )


# ═══════════════════════════════════════════════════════════════════
# Unchanged
# ═══════════════════════════════════════════════════════════════════

@admin.register(PrepDomainTraitTemplate)
class PrepDomainTraitTemplateAdmin(admin.ModelAdmin):
    list_display = ['trait_name', 'domain', 'prep_class', 'order']
    list_filter = ['domain', 'prep_class']
    list_editable = ['order']
    ordering = ['domain', 'order']
