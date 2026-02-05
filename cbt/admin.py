from django.contrib import admin
from import_export import resources, fields
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget
from .models import Quiz, Question, QuizResult

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
        fields = ('id', 'quiz', 'content', 'question_type', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_answer', 'image_url')
        export_order = fields


# --- 2. QUESTION ADMIN ---
@admin.register(Question)
class QuestionAdmin(ImportExportModelAdmin):
    resource_class = QuestionResource
    
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
    # Using 'quiz' here works because 'quiz' is still a direct ForeignKey on Question
    list_display = ('content', 'quiz', 'question_type', 'correct_answer')
    list_filter = ('quiz', 'question_type')
    search_fields = ('content', 'quiz__examination__name')


# --- 3. QUIZ ADMIN (The Fix for E108) ---
@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    # Use function names instead of property names to avoid E108 error
    list_display = ['get_exam_name', 'get_subject_name', 'term', 'number_of_questions', 'time', 'standard']
    list_filter = ['term', 'subject', 'standard']
    search_fields = ['examination__name', 'subject__name']

    # Helper function to display linked Examination Name
    def get_exam_name(self, obj):
        return obj.examination.name if obj.examination else "No Exam Linked"
    get_exam_name.short_description = 'Exam Name'

    # Helper function to display linked Subject Name
    def get_subject_name(self, obj):
        return obj.subject.name if obj.subject else "No Subject Linked"
    get_subject_name.short_description = 'Subject Name'


# --- 4. RESULTS ADMIN ---
@admin.register(QuizResult)
class QuizResultAdmin(ImportExportModelAdmin):
    list_display = ['user', 'quiz', 'score', 'passed', 'timestamp']
    list_filter = ['passed', 'quiz', 'timestamp']
    readonly_fields = ['user', 'quiz', 'score', 'passed', 'timestamp']

    def has_add_permission(self, request):
        return False
    

