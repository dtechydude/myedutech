"""
KwikSchools — Prep Report Card Admin (Fully Refactored & Consolidated)
===================================================================
1. Integrates virtual 'motor_*' fields dynamically directly into the ModelForm
   at the class attribute level to bypass Django's validation engine FieldError checks.
2. Synchronizes data directly to/from results.models.MotorAbilityScore.
3. Preserves all explicit skill assessment inline features, bulk actions, and
   custom template extensions.
4. Cleans out all legacy/unused PrepDomainRating components.
"""
from django import forms
from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import path
from django.utils.html import format_html

from results.models import MotorAbilityScore
from .models import (
    PrepClass, RatingScale, RatingColumn,
    PrepSubjectSkill, PrepAcademicPeriod,
    PrepReportCard, PrepSkillEntry
)
from .services import MOTOR_ABILITY_FIELDS, save_motor_ability_scores


# ═══════════════════════════════════════════════════════════════════
# 1. CORE INLINES
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


class PrepSkillEntryInline(admin.TabularInline):
    model = PrepSkillEntry
    extra = 0
    can_delete = False
    verbose_name = "Skill Entry"
    verbose_name_plural = "Skill Entries — select a rating column for each skill"
    show_change_link = False

    readonly_fields = ['skill', 'entered_by', 'entered_at']
    fields = ['skill', 'selected_column', 'subject_comment', 'entered_by', 'entered_at']

    def get_queryset(self, request):
        qs = (
            super()
            .get_queryset(request)
            .select_related('skill__subject', 'selected_column', 'entered_by')
            .order_by('skill__subject__name', 'skill__order')
        )
        object_id = request.resolver_match.kwargs.get('object_id')
        if not object_id:
            return qs.none()
        return qs

    def has_add_permission(self, request, obj=None):
        return False

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        object_id = request.resolver_match.kwargs.get('object_id')

        if db_field.name == 'selected_column':
            if object_id:
                try:
                    card = PrepReportCard.objects.select_related('rating_scale').get(pk=object_id)
                    kwargs['queryset'] = RatingColumn.objects.filter(scale=card.rating_scale).order_by('order')
                    kwargs['required'] = False
                except PrepReportCard.DoesNotExist:
                    kwargs['queryset'] = RatingColumn.objects.none()
            else:
                kwargs['queryset'] = RatingColumn.objects.none()

        elif db_field.name == 'skill':
            if object_id:
                try:
                    card = PrepReportCard.objects.select_related('prep_class').get(pk=object_id)
                    from django.db.models import Q
                    kwargs['queryset'] = PrepSubjectSkill.objects.filter(is_active=True).filter(
                        Q(prep_class=card.prep_class) | Q(prep_class__isnull=True)
                    ).select_related('subject').order_by('subject__name', 'order')
                except PrepReportCard.DoesNotExist:
                    kwargs['queryset'] = PrepSubjectSkill.objects.none()
            else:
                kwargs['queryset'] = PrepSubjectSkill.objects.none()

        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ═══════════════════════════════════════════════════════════════════
# 2. DYNAMIC MODELFORM GENERATION (Fixes FieldError safely)
# ═══════════════════════════════════════════════════════════════════

# Build form class configurations using meta dictionaries to satisfy modelform_factory checks at runtime
form_fields_dict = {
    'Meta': type('Meta', (), {
        'model': PrepReportCard,
        'fields': '__all__'
    })
}

# Explicitly register every single psychomotor and behavioral parameter at the class layout level
for field_name, label in MOTOR_ABILITY_FIELDS:
    form_fields_dict[f'motor_{field_name}'] = forms.IntegerField(
        label=label,
        required=False,
        min_value=1,
        max_value=5,
        widget=forms.NumberInput(attrs={'style': 'width: 60px; text-align: center;'})
    )

# Subclass dynamic initialization to fetch current data profiles from MotorAbilityScore securely
def form_init(self, *args, **kwargs):
    super(PrepReportCardAdminForm, self).__init__(*args, **kwargs)
    if self.instance and self.instance.pk:
        try:
            score_record = MotorAbilityScore.objects.filter(
                student=self.instance.student,
                term=self.instance.period.term
            ).first()
            if score_record:
                for f_name, _ in MOTOR_ABILITY_FIELDS:
                    val = getattr(score_record, f_name, None)
                    if val is not None:
                        self.initial[f'motor_{f_name}'] = val
        except Exception:
            pass

form_fields_dict['__init__'] = form_init

# Create the final ModelForm blueprint dynamically
PrepReportCardAdminForm = type('PrepReportCardAdminForm', (forms.ModelForm,), form_fields_dict)


# ═══════════════════════════════════════════════════════════════════
# 3. MASTER PREPREPORTCARD MODELADMIN
# ═══════════════════════════════════════════════════════════════════

@admin.register(PrepReportCard)
class PrepReportCardAdmin(admin.ModelAdmin):
    form = PrepReportCardAdminForm
    change_form_template = 'prep_reports/admin/prepreportcard/change_form.html'
    inlines = [PrepSkillEntryInline]
    actions = ['approve_selected', 'publish_selected', 'repopulate_skill_entries']

    # ── List Dashboard ────────────────────────────────────────────
    list_display = [
        'student_name', 'prep_class', 'period', 'status',
        'skill_entry_count', 'days_present', 'days_absent',
        'promoted_to', 'created_at',
    ]
    raw_id_fields = ['student']
    list_filter = ['status', 'prep_class', 'period']
    search_fields = [
        'student__user__last_name',
        'student__user__first_name',
        'student__usn',
    ]

    # ── Change Form Component Fieldsets ───────────────────────────
    readonly_fields = [
        'created_by', 'approved_by', 'created_at', 'updated_at',
        'populate_button',
    ]
    
    fieldsets = [
        ('Student & Period', {
            'fields': ['student', 'prep_class', 'period', 'rating_scale', 'status'],
        }),
        ('Attendance', {
            'fields': ['days_present', 'days_absent'],
        }),
        ('Pupil Behavioral Traits (1-5)', {
            'fields': [
                'motor_honesty', 'motor_politeness', 'motor_neatness', 
                'motor_cooperation', 'motor_obedience', 'motor_attentiveness', 
                'motor_punctuality', 'motor_perseverance', 'motor_emotional_stability', 
                'motor_attitude', 'motor_leadership'
            ],
            'description': 'Enter ratings out of 5 for behavioral benchmarks.',
        }),
        ('Pupil Practical Motor Abilities (1-5)', {
            'fields': [
                'motor_physical_education', 'motor_musical', 'motor_games', 
                'motor_handwriting', 'motor_reading', 'motor_verbal_fluency', 
                'motor_handling_tools'
            ],
            'description': 'Enter ratings out of 5 for practical development metrics.',
        }),
        ('Remarks', {
            'fields': ['class_teacher_comment', 'head_teacher_comment'],
        }),
        ('Promotion', {
            'fields': ['promoted_to'],
        }),
        ('Audit Trail', {
            'fields': ['created_by', 'approved_by', 'created_at', 'updated_at'],
            'classes': ['collapse'],
        }),
        ('Skill Entry Population', {
            'fields': ['populate_button'],
            'description': (
                'After saving a new card, click the button below to pull all '
                'active PrepSubjectSkills into the Skill Entries inline below.'
            ),
        }),
    ]

    # ── Database Layer Interception ────────────────────────────────
    def save_model(self, request, obj, form, change):
        is_new = (obj.pk is None)

        if is_new and not obj.created_by_id:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)

        # Build scores payload dictionary cleanly out of cleaned_data
        scores_payload = {}
        for field_name, _ in MOTOR_ABILITY_FIELDS:
            form_key = f'motor_{field_name}'
            if form_key in form.cleaned_data and form.cleaned_data[form_key] is not None:
                scores_payload[field_name] = form.cleaned_data[form_key]

        if scores_payload:
            save_motor_ability_scores(request.user, obj, scores_payload)

        if is_new:
            from .services import _populate_card
            _populate_card(obj, obj.prep_class, request.user)
            count = obj.skill_entries.count()
            self.message_user(
                request,
                f'Report card created and {count} skill entry row(s) auto-populated.',
                messages.SUCCESS,
            )

    # ── Action URL Endpoints ───────────────────────────────────────
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
        from .services import _populate_card
        card = get_object_or_404(PrepReportCard, pk=card_id)
        _populate_card(card, card.prep_class, request.user)
        count = card.skill_entries.count()
        self.message_user(
            request,
            f'✔ Skill entries populated — {count} row(s) now exist. Scroll down to update.',
            messages.SUCCESS,
        )
        return redirect(f'/admin/prep_reports/prepreportcard/{card_id}/change/')

    # ── Form Helpers & Callables ───────────────────────────────────
    def populate_button(self, obj):
        if not (obj and obj.pk):
            return format_html('<span style="color:#718096">Save this card first to activate tracking setup.</span>')
        count = obj.skill_entries.count()
        url = f'/admin/prep_reports/prepreportcard/{obj.pk}/populate-skills/'
        if count:
            btn_style, btn_label = 'background:#c8952a;', f'↺ Re-populate ({count} entries exist)'
            note = 'All existing entries are preserved. Only missing rows are added.'
        else:
            btn_style, btn_label = 'background:#e53e3e;', '⚡ Populate Skill Entries NOW'
            note = 'No skill entries found. Click to pull parameters.'
        return format_html(
            '<a href="{}" style="{}color:#fff;padding:7px 16px;border-radius:4px;'
            'text-decoration:none;font-weight:600;font-size:13px;display:inline-block;'
            'margin-bottom:6px">{}</a><br><small style="color:#718096">{}</small>',
            url, btn_style, btn_label, note,
        )
    populate_button.short_description = 'Populate Skill Entries'

    def student_name(self, obj):
        return obj.student_full_name
    student_name.short_description = 'Student'
    student_name.admin_order_field = 'student__user__last_name'

    def skill_entry_count(self, obj):
        count = obj._skill_entry_count
        if count == 0:
            return format_html('<span style="color:#e53e3e;font-weight:bold">0 ⚠ needs populate</span>')
        return format_html('<span style="color:#276749;font-weight:bold">{}</span>', count)
    skill_entry_count.short_description = '# Skills'
    skill_entry_count.admin_order_field = '_skill_entry_count'

    # ── Bulk Management Actions ────────────────────────────────────
    def approve_selected(self, request, queryset):
        updated = queryset.filter(status='submitted').update(status='approved', approved_by=request.user)
        self.message_user(request, f'{updated} report card(s) approved.')
    approve_selected.short_description = 'Approve selected report cards'

    def publish_selected(self, request, queryset):
        updated = queryset.filter(status='approved').update(status='published')
        self.message_user(request, f'{updated} report card(s) published.')
    publish_selected.short_description = 'Publish selected report cards'

    def repopulate_skill_entries(self, request, queryset):
        from .services import _populate_card
        total_cards, total_entries = 0, 0
        for card in queryset.select_related('prep_class'):
            before = card.skill_entries.count()
            _populate_card(card, card.prep_class, request.user)
            after = card.skill_entries.count()
            total_entries += (after - before)
            total_cards += 1
        self.message_user(request, f'Processed {total_cards} card(s). {total_entries} new rows created.', messages.SUCCESS)
    repopulate_skill_entries.short_description = '⚡ Populate / re-populate skill entries for selected cards'

    def get_queryset(self, request):
        from django.db.models import Count
        return (
            super().get_queryset(request)
            .select_related('student__user', 'prep_class__standard', 'period')
            .annotate(_skill_entry_count=Count('skill_entries'))
        )
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        # Safely defaults to empty json if JavaScript parsing mapping attributes are absent
        extra_context['prep_trait_map'] = getattr(request, '_prep_trait_map', '{}')
        return super().changeform_view(request, object_id, form_url, extra_context)


# ═══════════════════════════════════════════════════════════════════
# 4. UNCHANGED APP CONFIGURATIONS
# ═══════════════════════════════════════════════════════════════════

@admin.register(PrepClass)
class PrepClassAdmin(admin.ModelAdmin):
    list_display = ['standard', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['standard__name']

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
            return format_html('<span style="color:green;font-weight:bold">✔ Current</span>')
        return format_html('<span style="color:#aaa">—</span>')
    is_current_display.short_description = 'Current?'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('session', 'term')