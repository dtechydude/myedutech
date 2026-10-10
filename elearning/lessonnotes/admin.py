from django.contrib import admin

from .models import LessonNote, LessonNoteEvent


class LessonNoteEventInline(admin.TabularInline):
    model = LessonNoteEvent
    extra = 0
    can_delete = False
    readonly_fields = ('actor', 'action', 'remark', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LessonNote)
class LessonNoteAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'standard', 'subject_name', 'academic_session',
                    'term', 'week', 'status', 'submitted_at')
    list_filter = ('status', 'term', 'academic_session', 'standard')
    search_fields = ('title', 'subject_name', 'teacher__username',
                     'teacher__first_name', 'teacher__last_name')
    list_select_related = ('teacher', 'standard')
    readonly_fields = ('submitted_at', 'updated_at', 'reviewed_at')
    inlines = [LessonNoteEventInline]