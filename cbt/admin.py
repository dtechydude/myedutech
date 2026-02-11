from django.contrib import admin
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
from .models import Quiz, Question, QuizResult
from django.core.exceptions import ValidationError
from django.utils import timezone
from django import forms
from django_ckeditor_5.widgets import CKEditor5Widget
from django.utils.html import format_html
from django.utils.text import Truncator
from django.utils.html import strip_tags


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

    # def is_currently_available(self, obj):
    #     today = timezone.localdate()
    #     now = timezone.localtime().time()

    #     return (
    #         obj.active and
    #         obj.start_date <= today <= obj.end_date and
    #         obj.start_time <= now <= obj.end_time
    #     )

    # is_currently_available.boolean = True
    # is_currently_available.short_description = "Available Now"

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



# --- 4. RESULTS ADMIN ---
@admin.register(QuizResult)
class QuizResultAdmin(ImportExportModelAdmin):
    list_display = ['user', 'quiz', 'score', 'passed', 'timestamp']
    list_filter = ['passed', 'quiz',  'quiz__standard', 'quiz__session',  'timestamp']
    readonly_fields = ['user', 'quiz', 'score', 'passed', 'timestamp']

    def has_add_permission(self, request):
        return False
    

