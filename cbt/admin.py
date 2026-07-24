from django.contrib import admin
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
from .models import Quiz, Question, QuizResult, QuizAttempt
from django.core.exceptions import ValidationError
from django.utils import timezone
from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from django.utils.html import format_html
from django.utils.text import Truncator
from django.utils.html import strip_tags
from django.utils import timezone
from django.urls import reverse
from .models import Examination



@admin.register(Examination)
class ExaminationAdmin(admin.ModelAdmin):
    list_display = ['name', 'session', 'standard', 'term', 'view_quizzes_link']

    def view_quizzes_link(self, obj):
        # This creates a URL to the Quiz Admin filtered by this specific Examination ID
        # Replace 'cbt' with the actual name of your app if it differs
        url = reverse('admin:cbt_quiz_changelist') + f'?examination__id__exact={obj.id}'
        return format_html('<a class="button" style="background-color: #2c3e50; color: white; padding: 5px 10px;" href="{}">Manage CBT</a>', url)

    view_quizzes_link.short_description = "CBT Control"



# --- 1. RESOURCE FOR CSV IMPORT/EXPORT ---

class QuestionResource(resources.ModelResource):
    # This allows you to type the Examination Name in your CSV 'quiz' column
    quiz = fields.Field(
        column_name='quiz',
        attribute='quiz',
        widget=ForeignKeyWidget(Quiz, 'examination__name')
    )

    class Meta:
        model = Question
        fields = (
            'id',
            'quiz',
            'content',
            'question_type',
            'option_a',
            'option_b',
            'option_c',
            'option_d',
            'correct_answer',
            'image_url'
        )
        export_order = fields


class QuestionAdminForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = "__all__"
        labels = {
            "content": "Question Text",
        }
        widgets = {
            "content": CKEditor5Widget(config_name="extends"),
        }


@admin.register(Question)
class QuestionAdmin(ImportExportModelAdmin):
    resource_class = QuestionResource
    form = QuestionAdminForm

    fieldsets = (
        ('General Information', {
            'fields': ('quiz', 'content', 'question_type', 'image_url')
        }),
        ('Multiple Choice Options', {
            'description': "Fill these only if question type is MCQ.",
            'fields': ('option_a', 'option_b', 'option_c', 'option_d'),
        }),
        ('Correct Answer', {
            'fields': ('correct_answer',),
        }),
    )

    # ✅ Clean preview (removes HTML tags and truncates)
    list_display = ('formatted_content', 'quiz', 'question_type', 'correct_answer')
    list_filter = ('quiz', 'question_type', 'quiz__standard__name', 'quiz__subject__name')
    search_fields = ('content', 'quiz__examination__name')

    def formatted_content(self, obj):
        clean_text = strip_tags(obj.content)
        return Truncator(clean_text).chars(100)

    formatted_content.short_description = "Question Text"


# --- 3. QUIZ ADMIN (The Fix for E108) ---

@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):

    list_display = [
        'get_exam_name',
        'get_subject_name',
        'term',
        'standard',
        'start_date',
        'end_date',
        'start_time',
        'end_time',
        'is_currently_available',
        'active',
    ]

    list_filter = [
        'term',
        'subject',
        'standard',
        'active',
        'start_date',
        'end_date',
    ]

    search_fields = [
        'examination__name',
        'subject__name',
    ]

    readonly_fields = ['is_currently_available']

    fieldsets = (
        ('Exam Details', {
            'fields': (
                'examination',
                'subject',
                'term',
                'session',
                'standard',
            )
        }),
        ('Exam Configuration', {
            'fields': (
                'number_of_questions',
                'time',
                'required_score_to_pass',
            )
        }),
        ('Availability', {
            'fields': (
                'start_date',
                'end_date',
                'start_time',
                'end_time',
                'active',
                'is_currently_available',
            )
        }),
    )

    # ===============================
    # Display helpers
    # ===============================

    def get_exam_name(self, obj):
        return obj.examination.name if obj.examination else "No Exam Linked"
    get_exam_name.short_description = 'Exam Name'

    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else "No Subject Linked"
    get_subject_name.short_description = 'Subject Name'


    def is_currently_available(self, obj):
    # If availability fields are not yet set, treat as NOT available
        if not all([
            obj.start_date,
            obj.end_date,
            obj.start_time,
            obj.end_time,
        ]):
            return False

        today = timezone.localdate()
        now = timezone.localtime().time()

        return (
            obj.active and
            obj.start_date <= today <= obj.end_date and
            obj.start_time <= now <= obj.end_time
        )

    is_currently_available.boolean = True
    is_currently_available.short_description = "Available Now"


    # ===============================
    # Validation
    # ===============================

    def save_model(self, request, obj, form, change):
        # Prevent invalid time ranges
        if obj.end_time <= obj.start_time:
            raise ValidationError("End time must be later than start time.")

        # Prevent invalid date ranges
        if obj.end_date < obj.start_date:
            raise ValidationError("End date cannot be before start date.")

        # Auto-toggle active based on dates
        today = timezone.localdate()
        if obj.start_date <= today <= obj.end_date:
            obj.active = True
        else:
            obj.active = False

        super().save_model(request, obj, form, change)

    # ===============================
    # Lock fields after attempts (SAFE)
    # ===============================

    def get_readonly_fields(self, request, obj=None):
        readonly = list(self.readonly_fields)

        if obj and hasattr(obj, 'attempt_set') and obj.attempt_set.exists():
            readonly += [
                'examination',
                'subject',
                'standard',
                'number_of_questions',
                'time',
                'start_date',
                'end_date',
                'start_time',
                'end_time',
            ]

        return readonly


# @admin.register(QuizResult)
# class QuizResultAdmin(ImportExportModelAdmin):

#     list_display = (
#         'user',
#         'quiz',
#         'score',
#         'passed',
#         'cancelled',
#         'timestamp'
#     )

#     list_filter = (
#         'quiz',
#         'passed',
#         'cancelled',
#         'timestamp'
#     )

#     search_fields = (
#         'user__username',
#         'quiz__subject__name'
#     )

#     list_editable = ('cancelled',)

#     readonly_fields = (
#         'user',
#         'quiz',
#         'score',
#         'passed',
#         'timestamp'
#     )

#     actions = ['cancel_results_and_reset_attempt']

#     def cancel_results_and_reset_attempt(self, request, queryset):
#         updated = 0

#         for result in queryset:
#             if not result.cancelled:
#                 result.cancelled = True
#                 result.save()

#                 # ✅ ALSO reset attempts
#                 QuizAttempt.objects.filter(
#                     user=result.user,
#                     quiz=result.quiz
#                 ).update(
#                     cancelled=True,
#                     completed=False
#                 )

#                 updated += 1

#         self.message_user(
#             request,
#             f"{updated} result(s) cancelled and attempts reset successfully."
#         )

#     cancel_results_and_reset_attempt.short_description = (
#         "Cancel Result & Reset Attempt (Allow Retake)"
#     )


"""
admin.py — QuizResult Admin (Refactored)
KwikSchools — Smarter Schools!

Changes:
  - score displayed as one decimal place (e.g. 90.8 not 90.8888888888)
  - score column is sortable
  - score shown with % suffix for clarity
  - model __str__ also cleaned up to one decimal place
"""

@admin.register(QuizResult)
class QuizResultAdmin(ImportExportModelAdmin):

    list_display = (
        'user',
        'quiz',
        'display_score',   # ← replaces raw 'score'
        'passed',
        'cancelled',
        'timestamp',
    )

    list_filter = (
        'quiz',
        'passed',
        'cancelled',
        'timestamp',
    )

    search_fields = (
        'user__username',
        'quiz__subject__name',
    )

    list_editable = ('cancelled',)

    readonly_fields = (
        'user',
        'quiz',
        'display_score',   # ← use formatted version in detail view too
        'passed',
        'timestamp',
    )

    actions = ['cancel_results_and_reset_attempt']

    # ── Formatted score column ────────────────────────────────────────────────

    @admin.display(description='Score', ordering='score')
    def display_score(self, obj):
        """Show score rounded to 1 decimal place with a % suffix."""
        return f'{obj.score:.1f}%'

    # ── Bulk cancel action ────────────────────────────────────────────────────

    @admin.action(description='Cancel Result & Reset Attempt (Allow Retake)')
    def cancel_results_and_reset_attempt(self, request, queryset):
        updated = 0

        for result in queryset:
            if not result.cancelled:
                result.cancelled = True
                result.save()

                QuizAttempt.objects.filter(
                    user=result.user,
                    quiz=result.quiz,
                ).update(
                    cancelled=True,
                    completed=False,
                )

                updated += 1

        self.message_user(
            request,
            f'{updated} result(s) cancelled and attempt(s) reset successfully.',
        )


# ── Also update your QuizResult model __str__ ─────────────────────────────────
#
# Find the QuizResult model in models.py and update __str__ to match:
#
# BEFORE:
#   def __str__(self):
#       return f"{self.user} - {self.quiz} ({self.score}%)"
#
# AFTER:
#   def __str__(self):
#       return f"{self.user} - {self.quiz} ({self.score:.1f}%)"
#
# The :.1f format specifier rounds to exactly one decimal place everywhere
# the model is displayed — admin, shell, logs, and any template using {{ result }}.





@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):

    list_display = (
        'user', 'get_first_name', 'get_last_name',
        'quiz',
        'start_time',
        'completed',
        'cancelled',
        'time_left_display',
    )

    list_filter = (
        'completed',
        'cancelled',
        'quiz',
    )

    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'quiz__subject__name',
    )

    actions = ['cancel_attempts']
    
    raw_id_fields = ['user', 'quiz',]

    readonly_fields = (
        'start_time',
        'cancelled_at',
        'cancelled_by',
    )

    def time_left_display(self, obj):
        if obj.cancelled:
            return "Cancelled"
        return obj.get_time_left()

    time_left_display.short_description = "Time Left (seconds)"

    def cancel_attempts(self, request, queryset):
        updated_count = 0

        for attempt in queryset:
            if not attempt.cancelled:
                attempt.cancelled = True
                attempt.completed = False
                attempt.cancelled_by = request.user
                attempt.cancelled_at = timezone.now()
                attempt.save()

                # ✅ ALSO cancel related result
                QuizResult.objects.filter(
                    user=attempt.user,
                    quiz=attempt.quiz
                ).update(cancelled=True)

                updated_count += 1

        self.message_user(
            request,
            f"{updated_count} attempt(s) cancelled and result reset. Students can now retake."
        )

    cancel_attempts.short_description = (
        "Cancel selected attempts (Allow Retake)"
    )

    # Define the method to get first name
    @admin.display(description='First Name', ordering='user__first_name')
    def get_first_name(self, obj):
        return obj.user.first_name

    # Define the method to get last name
    @admin.display(description='Last Name', ordering='user__last_name')
    def get_last_name(self, obj):
        return obj.user.last_name