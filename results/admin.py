from doctest import Example
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from results.models import Examination, Result, Score, MotorAbilityScore
from curriculum.models import Term

# class ExamSubjectAdmin(admin.ModelAdmin):
       
#     list_display=('subject_id', 'name',)
#     exclude =['slug']

# class MotorAbility1Inline(admin.TabularInline):
#     model = MotorAbility1
#     max_num = 1
    
#     def has_delete_permission(self, request, obj=None):
#         return False

# class ResultImage1Inline(admin.TabularInline):
#     model = ResultImage1
#     exclude =['f_1', 'f_2', 'f_3']
#     max_num = 1
    
#     def has_delete_permission(self, request, obj=None):
#         return False

class ResultAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    pass
    # inlines = [MotorAbility1Inline, ResultImage1Inline] 
    # exclude =['remark', 'student_id']
    # list_display=('student_detail', 'exam',)
    # list_filter  = ['student_detail__standard']
    # search_fields = ('student_detail__student_username', 'student_detail__full_name')
    # raw_id_fields = ['student_id', 'student_detail',]



class ExaminationAdmin(admin.ModelAdmin):
       
    list_display=('name', 'standard', 'term')

class ResultAdmin(admin.ModelAdmin):
       
    list_display=('student', 'subject', 'exam', 'score')

#works well 001
class ScoreAdmin(admin.ModelAdmin):
       
    list_display=('student', 'subject', 'term', 'ca1', 'ca2', 'exam_score', 'total_score')



# Admin for MotorAbilityScore (still useful for viewing all at once)
@admin.register(MotorAbilityScore)
class MotorAbilityScoreAdmin(admin.ModelAdmin):
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
            'fields': ('honesty', 'politeness', 'neatness', 'cooperation', 'obedience', 'punctuality',)
        }),
        ('Other Abilities (Score out of 5)', {
            'fields': ('physical_education', 'games',)
        }),
    )


# --- New Inline for MotorAbilityScore ---
class MotorAbilityScoreInline(admin.TabularInline): # Use TabularInline for a compact table
    model = MotorAbilityScore
    extra = 1 # Number of empty forms to display for new entries
    # Optionally, specify which fields to show in the inline
    fields = (
        'student', 'honesty', 'politeness', 'neatness', 'cooperation',
        'obedience', 'punctuality', 'physical_education', 'games'
    )
    raw_id_fields = ('student',) # Use raw_id_fields for the student foreign key for better performance with many students

# --- Modify/Register TermAdmin to include the inline ---

# IMPORTANT: If your 'Term' model is already registered in 'curriculum/admin.py'
# and you want to manage it here, you should unregister it first:
try:
    admin.site.unregister(Term)
except admin.sites.NotRegistered:
    pass # Term was not registered, so no need to unregister


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'session')
    list_filter = ('session',)
    search_fields = ('name', 'session__name')
    # Add the MotorAbilityScoreInline here
    inlines = [MotorAbilityScoreInline]

    # Optional: You could also add an inline for academic Scores if you want to
    # manage them directly from the Term admin page.
    # class ScoreInline(admin.TabularInline):
    #     model = Score
    #     extra = 1
    #     fields = ('student', 'subject', 'score')
    # # To add multiple inlines:
    # # inlines = [MotorAbilityScoreInline, ScoreInline]






# admin.site.register(MarkedSheet, MarkedSheetAdmin)
admin.site.register(Examination, ExaminationAdmin)
# admin.site.register(UploadCertificate, UploadCertificateAdmin)
# admin.site.register(ExamSubject, ExamSubjectAdmin)
admin.site.register(Result, ResultAdmin)
admin.site.register(Score, ScoreAdmin)
# admin.site.register(ResultSheet3, ResultSheet3Admin)
# # admin.site.register(ResultImage, ResultImageAdmin)
