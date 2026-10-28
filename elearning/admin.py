from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import ELearningSubject, Lesson, Comment, Reply, Assignment, AssignmentSubmission
from .lessonnotes import admin as _lessonnotes_admin  # noqa: F401
from .notices import admin as _notices_admin  # noqa: F401
from curriculum.models import Standard

# @admin.register(ELearningSubject)
# class ELearningSubjectAdmin(ImportExportModelAdmin):
#     list_display = ('subject_id', 'name', 'standard', 'description')
#     list_filter = ['standard__name']
#     search_fields = ('standard__name', 'subject_id')
#     exclude = ['slug']


class StandardFilter(admin.SimpleListFilter):
    title = "Standard"
    parameter_name = "standard"

    def lookups(self, request, model_admin):
        standards = Standard.objects.exclude(name="Alumni")

        return [
            (standard.id, standard.name)
            for standard in standards
        ]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(standard_id=self.value())
        return queryset


@admin.register(ELearningSubject)
class ELearningSubjectAdmin(ImportExportModelAdmin):
    list_display = ("subject_id", "name", "standard", "description")
    list_filter = (StandardFilter,)
    search_fields = ("standard__name", "subject_id")
    exclude = ["slug"]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.exclude(standard__name="Alumni")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "standard":
            kwargs["queryset"] = Standard.objects.exclude(
                name="Alumni"
            )
        return super().formfield_for_foreignkey(
            db_field, request, **kwargs
        )


@admin.register(Lesson)
class LessonAdmin(ImportExportModelAdmin):
    list_display = ('standard', 'subject', 'lesson_id', 'name', 'notes')
    list_filter = ['standard']
    search_fields = ('standard__name', 'subject__name')
    raw_id_fields = ['created_by']
    exclude = ['slug']


# NOTE: Comment/Reply were not registered in Django admin previously —
# adding basic registration here is purely additive (new visibility for
# staff), it doesn't change any existing behavior.

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('lesson_name', 'author', 'date_added')
    search_fields = ('author__username', 'body')
    list_filter = ('date_added',)
    raw_id_fields = ('lesson_name', 'author')


@admin.register(Reply)
class ReplyAdmin(admin.ModelAdmin):
    list_display = ('comment_name', 'author', 'date_added')
    search_fields = ('author__username', 'reply_body')
    raw_id_fields = ('comment_name', 'author')


# =====================================================================
# ✅ NEW — Assignments / Homework
# =====================================================================

class AssignmentSubmissionInline(admin.TabularInline):
    model = AssignmentSubmission
    extra = 0
    fields = ('student', 'submission_link', 'submitted_at', 'score', 'teacher_feedback', 'graded_by')
    readonly_fields = ('submitted_at',)
    raw_id_fields = ('student', 'graded_by')


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'lesson', 'due_date', 'max_score', 'created_by', 'created_at')
    list_filter = ('lesson__standard', 'lesson__subject')
    search_fields = ('title', 'lesson__name')
    raw_id_fields = ('lesson', 'created_by')
    exclude = ['slug']
    inlines = [AssignmentSubmissionInline]


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    """
    Grading happens right here: open a submission (or edit inline from
    the list) and set `score` + `teacher_feedback` — no separate grading
    UI/package needed for a simple k-12 workflow.
    """
    list_display = ('student', 'assignment', 'submitted_at', 'score', 'is_graded', 'graded_by')
    list_editable = ('score',)
    list_filter = ('assignment__lesson__standard', 'assignment')
    search_fields = ('student__first_name', 'student__last_name', 'assignment__title')
    raw_id_fields = ('assignment', 'student', 'graded_by')

    def save_model(self, request, obj, form, change):
        if 'score' in form.changed_data and obj.graded_by_id is None:
            obj.graded_by = request.user
        super().save_model(request, obj, form, change)
