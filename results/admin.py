from doctest import Example
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from results.models import Score, MotorAbilityScore, MidTermScore, ResultPublication, SessionResultStatus, ExamSetting, ClassPositionSetting,  ReportComments
from curriculum.models import Term
# add this because of the cbt
from django.utils.html import format_html
from django.urls import reverse
from .utils import mdterm_get_overall_remark
from django.db.models import Avg, Sum
from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import SchoolYearSettings, MidTermReportRemark, MidTermScore,  MidTermReportRemark, MidTermComponentScore, MidTermComponent
from .models import MidTermReportRemark, MidTermScore, ExamSetting, SessionReportComments
from .utils import mdterm_get_overall_remark



# @admin.register(Examination)
# class ExaminationAdmin(admin.ModelAdmin):
#     list_display = ['name', 'session', 'standard', 'term', 'view_quizzes_link']

#     def view_quizzes_link(self, obj):
#         # This creates a URL to the Quiz Admin filtered by this specific Examination ID
#         # Replace 'cbt' with the actual name of your app if it differs
#         url = reverse('admin:cbt_quiz_changelist') + f'?examination__id__exact={obj.id}'
#         return format_html('<a class="button" style="background-color: #2c3e50; color: white; padding: 5px 10px;" href="{}">Manage CBT</a>', url)

#     view_quizzes_link.short_description = "CBT Control"



#works well 001
class ScoreAdmin(ImportExportModelAdmin):
       
    list_display=('student', 'subject', 'term', 'ca1', 'ca2', 'ca3', 'exam_score', 'total_score')
    search_fields = ('student__USN', 'subject__name')
    raw_id_fields = ['student', 'subject', 'term']
    list_filter  = ['term', 'student__current_class']



# Admin for MotorAbilityScore (still useful for viewing all at once)
@admin.register(MotorAbilityScore)
class MotorAbilityScoreAdmin(ImportExportModelAdmin):
    list_display = (
        'student', 'term', 'honesty', 'politeness', 'neatness', 'cooperation',
        'obedience', 'punctuality', 'physical_education', 'games'
    )
    list_filter = ('term', 'student__current_class', 'student')
    search_fields = ('student__first_name', 'student__last_name', 'term__name')
    raw_id_fields = ('student', 'term') # Use raw_id_fields for FKs if many instances
    fieldsets = (
        (None, {
            'fields': ('student', 'term',)
        }),
        ('Behavioral Traits (Score out of 5)', {
            'fields': ('honesty', 'politeness', 'neatness', 'cooperation', 'leadership', 'attitude', 'emotional_stability', 'perseverance', 'attentiveness', 'obedience', 'punctuality')
        }),
        ('Other Abilities (Score out of 5)', {
            'fields': ('musical', 'physical_education', 'handwriting', 'games', 'reading', 'verbal_fluency', 'handling_tools')
        }),
    )


# --- New Inline for MotorAbilityScore ---
class MotorAbilityScoreInline(admin.TabularInline): # Use TabularInline for a compact table
    model = MotorAbilityScore
    extra = 1 # Number of empty forms to display for new entries
    # Optionally, specify which fields to show in the inline
    fields = (
        'student', 'honesty', 'politeness', 'neatness', 'cooperation', 'leadership', 'attitude', 'emotional_stability', 'perseverance', 'attentiveness',
        'obedience', 'punctuality', 'musical', 'physical_education', 'handwriting', 'games', 'reading', 'verbal_fluency', 'handling_tools'
    )
    raw_id_fields = ('student',) # Use raw_id_fields for the student foreign key for better performance with many students

# --- Modify/Register TermAdmin to include the inline ---

# IMPORTANT: If your 'Term' model is already registered in 'curriculum/admin.py'
# and you want to manage it here, you should unregister it first:
# try:
#     admin.site.unregister(Term)
# except admin.sites.NotRegistered:
#     pass # Term was not registered, so no need to unregister


# @admin.register(Term)
# class TermAdmin(ImportExportModelAdmin):
#     list_display = ('name', 'session', 'start_date', 'end_date', 'is_current')
#     list_filter = ('session', 'name')
#     search_fields = ('name', 'session__name')
    # Add the MotorAbilityScoreInline here
    # inlines = [MotorAbilityScoreInline]

    # Optional: You could also add an inline for academic Scores if you want to
    # manage them directly from the Term admin page.
    # class ScoreInline(admin.TabularInline):
    #     model = Score
    #     extra = 1
    #     fields = ('student', 'subject', 'score')
    # # To add multiple inlines:
    # # inlines = [MotorAbilityScoreInline, ScoreInline]

# Result Publication Logic
@admin.register(ResultPublication)
class ResultPublicationAdmin(admin.ModelAdmin):
    # The actions list enables the bulk actions dropdown
    # We rename the actions to be clearer for the Admin
    actions = ['publish_reports', 'block_reports'] 
    
    list_display = ('student', 'term', 'is_published')
    search_fields = ('student__USN', 'student__user__first_name', 'term__name')
    list_filter = ('term', 'is_published', 'student__current_class')
    raw_id_fields = ('student', 'term')

    # --- BULK ACTION 1: PUBLISH (Allow Viewing) ---
    def publish_reports(self, request, queryset):
        # Action to allow viewing for selected records
        updated_count = queryset.update(is_published=True)
        self.message_user(request, f"{updated_count} selected reports have been set to PUBLISHED (Students can view).", level='success')
    publish_reports.short_description = "✅ Publish selected reports (Allow Student Viewing)"

    # --- BULK ACTION 2: BLOCK (Unpublish/Restrict Viewing) ---
    def block_reports(self, request, queryset):
        # Action to block viewing for selected records (e.g., for fees)
        updated_count = queryset.update(is_published=False)
        self.message_user(request, f"{updated_count} selected reports have been set to BLOCKED (Students cannot view).", level='warning')
    block_reports.short_description = "❌ Block selected reports (Restrict Student Viewing)"

    

@admin.register(SessionResultStatus)
class SessionResultStatusAdmin(admin.ModelAdmin):
    # This adds the search bar and filter sidebar you need
    list_display = ['student', 'session', 'get_class', 'is_published']
    list_filter = ['session', 'student__current_class', 'is_published']
    search_fields = ['student__first_name', 'student__last_name', 'student__admission_number']
    list_editable = ['is_published'] # Edit checkboxes directly from the list!
    raw_id_fields = ('student',)

    
    # Helper to show the class in the list
    def get_class(self, obj):
        return obj.student.current_class
    get_class.short_description = 'Class'



# ----------------------------- Exam Setting Admin ----------------------------- #
@admin.register(ExamSetting)
class ExamSettingAdmin(ImportExportModelAdmin):
    list_display = ('term', 'exam_type', 'max_score')
    list_filter = ('term', 'exam_type')
    search_fields = ('term__name', 'exam_type')
    
    fieldsets = (
        ('Exam Configuration', {
            'fields': ('term', 'exam_type', 'max_score'),
            'description': 'Set the maximum score for a given exam type and term. This is used centrally for all score entries.',
        }),
    )

    def save_model(self, request, obj, form, change):
        # Prevent duplicate settings for the same term + exam_type
        if not change:
            exists = ExamSetting.objects.filter(term=obj.term, exam_type=obj.exam_type).exists()
            if exists:
                from django.core.exceptions import ValidationError
                raise ValidationError(f"An ExamSetting already exists for term '{obj.term}' and exam type '{obj.exam_type}'.")
        super().save_model(request, obj, form, change)




# Class Position And Comments
@admin.register(ClassPositionSetting)
class ClassPositionSettingAdmin(admin.ModelAdmin):
    list_display = (
        'standard',
        'term',
        'session',
        'show_class_position',
        'updated_at'
    )

    list_filter = (
        'standard',
        'term',
        'session',
        'show_class_position'
    )

    search_fields = (
        'standard__name',
        'term__name',
        'session__name'
    )
    
    list_editable = ('show_class_position',)

    ordering = ('-session', 'standard', 'term')

    # Prevent duplicate entries manually
    def save_model(self, request, obj, form, change):
        obj.save()

## Principal and Teachers comment
@admin.register(ReportComments)
class ReportCommentsAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'standard',
        'term',
        'session',
        'short_teacher_comment',
        'short_principal_comment',
        'created_by',
        'updated_at'
    )

    list_filter = (
        'standard',
        'term',
        'session',
    )

    search_fields = (
        'student__first_name',
        'student__last_name',
        'teacher_comment',
        'principal_comment'
    )

    readonly_fields = ('created_by', 'created_at', 'updated_at')
    
    raw_id_fields = ('student', 'standard')

    ordering = ('-session', 'standard', 'student')

    # Auto-assign creator
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Only on create
            obj.created_by = request.user
        obj.save()

    # Short previews for admin list
    def short_teacher_comment(self, obj):
        return (obj.teacher_comment[:50] + '...') if obj.teacher_comment else '---'
    short_teacher_comment.short_description = "Teacher Comment"

    def short_principal_comment(self, obj):
        return (obj.principal_comment[:50] + '...') if obj.principal_comment else '---'
    short_principal_comment.short_description = "Principal Comment"



# Setting Exams Scores

@admin.register(SchoolYearSettings)
class SchoolYearSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'max_ca_total', 'max_exam_score', 'is_active')
    list_editable = ('is_active',)
    
    fieldsets = (
        ('Grading Weights', {
            'fields': ('max_ca_total', 'max_exam_score'),
            'description': "Set the maximum points for Continuous Assessment and Examinations. Their sum must equal 100."
        }),
        ('Status', {
            'fields': ('is_active',),
        }),
    )

    def save_model(self, request, obj, form, change):
        """
        Ensures that if this configuration is set to active, 
        all other configurations are deactivated.
        """
        if obj.is_active:
            # Deactivate all other settings
            SchoolYearSettings.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        """
        Optional: Limit to only one configuration record total to keep it simple.
        If you want to keep a history of past years, remove this method.
        """
        if SchoolYearSettings.objects.count() >= 1:
            return False
        return super().has_add_permission(request)
    




# Midterm setting 
# ============================================
# ADMIN.PY
# ============================================


# ============================================
# INLINE: COMPONENT SCORES
# ============================================

class MidTermComponentScoreInline(admin.TabularInline):
    model = MidTermComponentScore
    extra = 0

    fields = (
        'component',
        'score',
    )

    autocomplete_fields = (
        'component',
    )


# ============================================
# MIDTERM COMPONENT ADMIN
# ============================================

@admin.register(MidTermComponent)
class MidTermComponentAdmin(admin.ModelAdmin):

    list_display = (
        'title',
        'term',
        'max_score',
        'order',
        'is_active',
        'total_term_score',
    )

    list_filter = (
        'term',
        'is_active',
    )

    search_fields = (
        'title',
        'term__name',
    )

    ordering = (
        'term',
        'order',
    )

    list_editable = (
        'order',
        'is_active',
    )

    def total_term_score(self, obj):
        """
        Shows cumulative configured component score
        for the term.
        """

        total = MidTermComponent.objects.filter(
            term=obj.term,
            is_active=True
        ).aggregate(
            total=Sum('max_score')
        )['total'] or 0

        return total

    total_term_score.short_description = (
        'Configured Total'
    )


# ============================================
# MIDTERM SCORE ADMIN
# ============================================

@admin.register(MidTermScore)
class MidTermScoreAdmin(admin.ModelAdmin):

    list_display = (
        'student',
        'subject',
        'term',
        'exam_total_score',
        'percentage_display',
    )
    raw_id_fields = (
        'student',
        'subject',
    )

    list_filter = (
        'term',
        'subject',
        'student__current_class',
    )

    search_fields = (
        'student__first_name',
        'student__last_name',
        'subject__name',
    )

    ordering = (
        'student__last_name',
        'subject__name',
    )

    inlines = [
        MidTermComponentScoreInline
    ]

    readonly_fields = (
        'exam_total_score',
    )

    def percentage_display(self, obj):

        try:
            return f"{obj.percentage():.2f}%"

        except Exception:
            return "-"

    percentage_display.short_description = (
        'Percentage'
    )


# ============================================
# COMPONENT SCORE ADMIN
# ============================================

@admin.register(MidTermComponentScore)
class MidTermComponentScoreAdmin(admin.ModelAdmin):

    list_display = (
        'midterm_score',
        'component',
        'score',
        'component_max_score',
    )

    list_filter = (
        'component__term',
        'component',
    )

    search_fields = (
        'midterm_score__student__first_name',
        'midterm_score__student__last_name',
        'component__title',
    )

    ordering = (
        'component__term',
        'component__order',
    )

    def component_max_score(self, obj):
        return obj.component.max_score

    component_max_score.short_description = (
        'Component Max'
    )



# ============================================
# ADMIN.PY
# UPDATED REPORT REMARK ADMIN
# ============================================

@admin.register(MidTermReportRemark)
class MidTermReportRemarkAdmin(admin.ModelAdmin):

    list_display = (
        'student',
        'term',
        'overall_average_display',
        'display_teacher_remark',
        'display_head_teacher_remark',
        'updated_at',
    )

    list_filter = (
        'term',
    )

    search_fields = (
        'student__first_name',
        'student__last_name',
        'teacher_remark',
        'head_teacher_remark',
    )
    raw_id_fields = (
            'student',
        )

    readonly_fields = (
        'overall_average_display',
        'auto_teacher_remark_preview',
        'auto_head_teacher_remark_preview',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        ('Student Information', {
            'fields': (
                'student',
                'term',
                'overall_average_display',
            )
        }),

        ('System Generated Remarks Preview', {
            'fields': (
                'auto_teacher_remark_preview',
                'auto_head_teacher_remark_preview',
            )
        }),

        ('Teacher Remark Override', {
            'fields': (
                'teacher_remark',
            )
        }),

        ('Head Teacher Remark Override', {
            'fields': (
                'head_teacher_remark',
            )
        }),

        ('Timestamps', {
            'fields': (
                'created_at',
                'updated_at',
            )
        }),
    )

    # ============================================
    # AVERAGE CALCULATION
    # ============================================

    def get_overall_average(self, obj):
        return MidTermScore.objects.filter(
            student=obj.student,
            term=obj.term,
            exam_total_score__isnull=False
        ).aggregate(
            avg=Avg('exam_total_score')
        )['avg']

    def overall_average_display(self, obj):
        avg = self.get_overall_average(obj)
        return round(avg, 2) if avg else "No Scores Available"

    overall_average_display.short_description = "Overall Average"

    # ============================================
    # MAX SCORE
    # ============================================

    def get_max_score(self, obj):
        setting = ExamSetting.objects.filter(
            term=obj.term,
            exam_type="Midterm"
        ).first()

        return setting.max_score if setting else 100

    # ============================================
    # AUTO REMARKS
    # ============================================

    def auto_teacher_remark_preview(self, obj):
        return mdterm_get_overall_remark(
            average_score=self.get_overall_average(obj),
            max_score=self.get_max_score(obj),
            remark_type='teacher'
        )

    auto_teacher_remark_preview.short_description = "Auto Teacher Remark"

    def auto_head_teacher_remark_preview(self, obj):
        return mdterm_get_overall_remark(
            average_score=self.get_overall_average(obj),
            max_score=self.get_max_score(obj),
            remark_type='head_teacher'
        )

    auto_head_teacher_remark_preview.short_description = "Auto Head Teacher Remark"

    # ============================================
    # DISPLAY (DB VALUE FIRST, AUTO FALLBACK)
    # ============================================

    def display_teacher_remark(self, obj):
        if obj.teacher_remark:
            return obj.teacher_remark
        return self.auto_teacher_remark_preview(obj)

    display_teacher_remark.short_description = "Teacher Remark"

    def display_head_teacher_remark(self, obj):
        if obj.head_teacher_remark:
            return obj.head_teacher_remark
        return self.auto_head_teacher_remark_preview(obj)

    display_head_teacher_remark.short_description = "Head Teacher Remark"

# Session Report Card Comment
@admin.register(SessionReportComments)
class SessionReportCommentsAdmin(admin.ModelAdmin):
    list_display = ('student', 'standard', 'session', 'created_by', 'updated_at')
    list_filter = ('session', 'standard')
    search_fields = ('student__first_name', 'student__last_name')
    autocomplete_fields = ('student', 'standard', 'session')

admin.site.register(Score, ScoreAdmin)