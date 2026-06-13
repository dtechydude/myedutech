
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    AIToolCategory,
    AITool,
    PromptCategory,
    PromptLibrary,
)


# =====================================================
# AI TOOL CATEGORY
# =====================================================


class ReadOnlyAdminMixin:

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False



@admin.register(AIToolCategory)
class AIToolCategoryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):

    list_display = (
        'name',
        'display_order',
        'is_active',
    )

    list_editable = (
        'display_order',
        'is_active',
    )

    search_fields = (
        'name',
    )

    ordering = (
        'display_order',
        'name',
    )


# =====================================================
# AI TOOL
# =====================================================

@admin.register(AITool)
class AIToolAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):

    list_display = (
        'name',
        'category',
        'tool_link',
        'is_featured',
        'is_active',
        'display_order',
        'created_at',
    )

    list_filter = (
        'category',
        'is_featured',
        'is_active',
        'created_at',
    )

    search_fields = (
        'name',
        'description',
        'best_for',
    )

    list_editable = (
        'is_featured',
        'is_active',
        'display_order',
    )

    autocomplete_fields = (
        'category',
    )

    ordering = (
        'display_order',
        'name',
    )

    readonly_fields = (
        'created_at',
    )

    fieldsets = (

        ('Basic Information', {
            'fields': (
                'category',
                'name',
                'description',
                'best_for',
            )
        }),

        ('Website Information', {
            'fields': (
                'website_url',
                'icon_class',
            )
        }),

        ('Display Settings', {
            'fields': (
                'is_featured',
                'is_active',
                'display_order',
            )
        }),

        ('System Information', {
            'fields': (
                'created_at',
            )
        }),

    )

    def tool_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank">Open</a>',
            obj.website_url
        )

    tool_link.short_description = "Website"


# =====================================================
# PROMPT CATEGORY
# =====================================================

@admin.register(PromptCategory)
class PromptCategoryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):

    list_display = (
        'name',
        'slug',
        'display_order',
        'is_active',
    )

    list_editable = (
        'display_order',
        'is_active',
    )

    search_fields = (
        'name',
    )

    ordering = (
        'display_order',
        'name',
    )


# =====================================================
# PROMPT LIBRARY
# =====================================================

@admin.register(PromptLibrary)
class PromptLibraryAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):

    list_display = (
        'title',
        'category',
        'school_level',
        'subject',
        'usage_count',
        'is_featured',
        'is_active',
        'created_at',
    )

    list_filter = (
        'category',
        'school_level',
        'is_featured',
        'is_active',
        'created_at',
    )

    search_fields = (
        'title',
        'subject',
        'prompt_text',
    )

    list_editable = (
        'is_featured',
        'is_active',
    )

    autocomplete_fields = (
        'category',
    )

    readonly_fields = (
        'usage_count',
        'created_at',
        'updated_at',
    )

    ordering = (
        'title',
    )

    fieldsets = (

        ('Prompt Information', {
            'fields': (
                'title',
                'category',
                'school_level',
                'subject',
            )
        }),

        ('Prompt Content', {
            'fields': (
                'prompt_text',
            )
        }),

        ('Visibility', {
            'fields': (
                'is_featured',
                'is_active',
            )
        }),

        ('Statistics', {
            'fields': (
                'usage_count',
            )
        }),

        ('Dates', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),

    )

    actions = [
        'make_featured',
        'remove_featured',
        'activate_prompts',
        'deactivate_prompts',
    ]

    def make_featured(self, request, queryset):

        queryset.update(
            is_featured=True
        )

        self.message_user(
            request,
            f'{queryset.count()} prompt(s) marked as featured.'
        )

    make_featured.short_description = (
        'Mark selected prompts as featured'
    )

    def remove_featured(self, request, queryset):

        queryset.update(
            is_featured=False
        )

        self.message_user(
            request,
            f'{queryset.count()} prompt(s) unfeatured.'
        )

    remove_featured.short_description = (
        'Remove featured status'
    )

    def activate_prompts(self, request, queryset):

        queryset.update(
            is_active=True
        )

        self.message_user(
            request,
            f'{queryset.count()} prompt(s) activated.'
        )

    activate_prompts.short_description = (
        'Activate selected prompts'
    )

    def deactivate_prompts(self, request, queryset):

        queryset.update(
            is_active=False
        )

        self.message_user(
            request,
            f'{queryset.count()} prompt(s) deactivated.'
        )

    deactivate_prompts.short_description = (
        'Deactivate selected prompts'
    )