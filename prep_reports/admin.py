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


class PrepDomainRatingInline(admin.TabularInline):
    model = PrepDomainRating
    extra = 0
    fields = ['domain', 'trait_name', 'rating_text', 'order']
    ordering = ['domain', 'order']


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


# ═══════════════════════════════════════════════════════════════════
# Unchanged
# ═══════════════════════════════════════════════════════════════════

@admin.register(PrepDomainTraitTemplate)
class PrepDomainTraitTemplateAdmin(admin.ModelAdmin):
    list_display = ['trait_name', 'domain', 'prep_class', 'order']
    list_filter = ['domain', 'prep_class']
    list_editable = ['order']
    ordering = ['domain', 'order']
