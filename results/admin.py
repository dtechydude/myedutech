from doctest import Example
from django.contrib import admin
from import_export.admin import ImportExportModelAdmin
from results.models import Examination, Score, MotorAbilityScore, MidTermScore, ResultPublication
from curriculum.models import Term




class ExaminationAdmin(admin.ModelAdmin):
       
    list_display=('name', 'standard', 'term')
    autocomplete_fields = ['standard']

# class ResultAdmin(admin.ModelAdmin):
       
#     list_display=('student', 'subject', 'exam', 'score')

#works well 001
class ScoreAdmin(admin.ModelAdmin):
       
    list_display=('student', 'subject', 'term', 'ca1', 'ca2', 'exam_score', 'total_score')
    search_fields = ('student__USN', 'subject__name')
    raw_id_fields = ['student', 'subject', 'term']
    list_filter  = ['term', 'student__current_class']



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
try:
    admin.site.unregister(Term)
except admin.sites.NotRegistered:
    pass # Term was not registered, so no need to unregister


@admin.register(Term)
class TermAdmin(admin.ModelAdmin):
    list_display = ('name', 'session', 'start_date', 'end_date', 'is_current')
    list_filter = ('session',)
    search_fields = ('name', 'session__name')
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

    


# Mid Term Admin Logic
@admin.register(MidTermScore)
class MidTermScoreAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'term', 'exam_total_score', 'student_class')
    search_fields = ('student__USN', 'student__user__first_name', 'subject__name')
    # Allows filtering by term, subject, and the student's current class
    list_filter = ('term', 'subject', 'student__current_class') 
    raw_id_fields = ('student', 'subject', 'term')
    
    # Custom method to display student's current class in the admin list
    def student_class(self, obj):
        # Assumes obj.student.current_class exists and has a 'name' attribute
        return obj.student.current_class.name
    student_class.short_description = 'Class'

    # --- 1. Limit QuerySet (What records a user sees in the list) ---
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        
        # Superuser and Staff see everything
        if request.user.is_superuser or request.user.is_staff:
            return qs
        
        # Filter for teachers: only allow editing scores for their classes/subjects
        if hasattr(request.user, 'teacher'):
            teacher = request.user.teacher
            # Returns scores where the student is in the teacher's assigned class 
            # AND the score's subject is one the teacher teaches
            return qs.filter(
                student__current_class=teacher.class_assigned,
                subject__in=teacher.subjects_taught.all()
            )
        # Hide scores if not staff/teacher
        return qs.none() 
    
    # --- 2. Limit Change Permission (What records a user can modify) ---
    def has_change_permission(self, request, obj=None):
        # Superuser and Staff can change anything
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # For teachers, check if they are authorized to modify this specific score object (obj)
        if obj is not None and hasattr(request.user, 'teacher'):
            teacher = request.user.teacher
            # Allow change if the teacher teaches this subject AND the student belongs to their class
            return (obj.subject in teacher.subjects_taught.all() and 
                    obj.student.current_class == teacher.class_assigned)
        
        # Block change permission if not an admin/staff or an authorized teacher
        return False
        
    # --- 3. Optional: Block Add/Delete for Teachers ---
    # Teachers should generally use the dedicated front-end entry view (MidTermScoreEntryView).
    def has_add_permission(self, request):
        # Only allow staff/superusers to add new records manually via admin
        return request.user.is_staff or request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        # Only allow staff/superusers to delete records
        return request.user.is_staff or request.user.is_superuser



# admin.site.register(MarkedSheet, MarkedSheetAdmin)
admin.site.register(Examination, ExaminationAdmin)
# admin.site.register(UploadCertificate, UploadCertificateAdmin)
# admin.site.register(ExamSubject, ExamSubjectAdmin)
# admin.site.register(Result, ResultAdmin)
admin.site.register(Score, ScoreAdmin)
# admin.site.register(ResultSheet3, ResultSheet3Admin)
# # admin.site.register(ResultImage, ResultImageAdmin)
