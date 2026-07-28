from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from .models import ELearningSubject, Lesson, Comment, Reply, Assignment, AssignmentSubmission


@admin.register(ELearningSubject)
class ELearningSubjectAdmin(ImportExportModelAdmin):
    list_display = ('subject_id', 'name', 'standard', 'description')
    list_filter = ['standard__name']
    search_fields = ('standard__name', 'subject_id')
    exclude = ['slug']


@admin.register(Lesson)
class LessonAdmin(ImportExportModelAdmin):
    list_display = ('standard', 'subject', 'lesson_id', 'name')
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
