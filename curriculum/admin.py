from django.contrib import admin
from curriculum.models import SchoolIdentity, Lesson, Subject, Session, Standard, ClassGroup, Term
from embed_video.admin import AdminVideoMixin
from django.contrib.auth import get_user_model
from django.http import HttpResponse
import csv, datetime
from import_export.admin import ImportExportModelAdmin


class SchoolIdentityAdmin(admin.ModelAdmin):
           
    list_display=('name', 'phone1', 'email')
    exclude = ['slug',]
  
class SessionAdmin(ImportExportModelAdmin, admin.ModelAdmin):
   
    list_display=('name', 'start_date', 'end_date')
    exclude = ['slug']

class StandardAdmin(ImportExportModelAdmin, admin.ModelAdmin):
   
    list_display=('name',)
    exclude = ['slug']


class ClassGroupAdmin(ImportExportModelAdmin, admin.ModelAdmin):
       
    list_display=('name', 'description')
    exclude = ['slug']

class SubjectAdmin(ImportExportModelAdmin, admin.ModelAdmin):
       
    list_display=('subject_id', 'name', 'standard')
    exclude = ['slug']

class LessonAdmin(ImportExportModelAdmin, admin.ModelAdmin):
       
    list_display=(  'standard', 'subject', 'lesson_id', 'name' )
    list_filter = ['standard',]
    search_fields = ('standard__name', 'subject__name')
    raw_id_fields = ['created_by',]
    exclude = ['slug']

class TermAdmin(admin.ModelAdmin):
       
    list_display=('name', 'start_date', 'end_date')




admin.site.register(Session, SessionAdmin)
admin.site.register(Standard, StandardAdmin)
admin.site.register(ClassGroup, ClassGroupAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(Lesson, LessonAdmin)
admin.site.register(SchoolIdentity, SchoolIdentityAdmin)
admin.site.register(Term, TermAdmin)






class MyModelAdmin(AdminVideoMixin, admin.ModelAdmin):
    pass
