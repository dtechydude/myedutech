from django.contrib import admin
from curriculum.models import SchoolIdentity, Lesson, Subject, ELearningSubject, Session, Standard, ClassGroup, Term
from embed_video.admin import AdminVideoMixin
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.http import HttpResponse
import csv, datetime
from import_export.admin import ImportExportModelAdmin


class SchoolIdentityAdmin(admin.ModelAdmin):
    # This will prevent the "Add School Identity" button from showing
    # if a SchoolIdentity instance already exists.
    def has_add_permission(self, request):
        if self.model.objects.exists():
            return False
        return super().has_add_permission(request)

    # This method is called before saving the model instance.
    def save_model(self, request, obj, form, change):
        if not change and self.model.objects.exists():
            # If the user is trying to add a new instance and one already exists,
            # display a user-friendly message and prevent saving.
            messages.error(request, "There can be only one school identity instance. Please edit the existing one.")
            # Do not call obj.save() here
        else:
            try:
                # Call the original save method on the object.
                # This will trigger the model's clean method and save logic.
                obj.save()
            except ValidationError as e:
                # Catch the ValidationError and add it to the messages framework.
                for error_msg in e.messages:
                    messages.error(request, error_msg)
           
    list_display=('name', 'phone1', 'email')
    exclude = ['slug',]
  
class SessionAdmin(ImportExportModelAdmin, admin.ModelAdmin):
   
    list_display=('name', 'start_date', 'end_date')
    exclude = ['slug']

class StandardAdmin(ImportExportModelAdmin, admin.ModelAdmin):
   
    list_display=('name', 'promotion_order', 'form_teacher', 'desc')
    exclude = ['slug']
    search_fields = ['name',]
    autocomplete_fields = ['form_teacher']


class ClassGroupAdmin(ImportExportModelAdmin, admin.ModelAdmin):
       
    list_display=('name', 'standard', 'form_teacher')
    list_filter = ['standard']
    list_filter = ['standard__name']
    search_fields = ('standard__name', 'name')
    autocomplete_fields = ['form_teacher']

    # exclude = ['slug']

class SubjectAdmin(ImportExportModelAdmin, admin.ModelAdmin):
       
    list_display=('subject_id', 'name', 'description')
    # list_filter = ['standard']
    search_fields = ('subject_id', 'name')
    exclude = ['slug']

class ELearningSubjectAdmin(ImportExportModelAdmin, admin.ModelAdmin):

    list_display=('subject_id', 'name', 'standard', 'description')
    list_filter = ['standard__name']
    search_fields = ('standard__name', 'subject_id')
    exclude = ['slug']

class LessonAdmin(ImportExportModelAdmin, admin.ModelAdmin):
       
    list_display=(  'standard', 'subject', 'lesson_id', 'name' )
    list_filter = ['standard',]
    search_fields = ('standard__name', 'subject__name')
    raw_id_fields = ['created_by',]
    exclude = ['slug']

class TermAdmin(admin.ModelAdmin):
       
    list_display=('name', 'start_date', 'end_date')
    raw_id_fields = ('session')
    # raw_id_fields = ['session',]




admin.site.register(Session, SessionAdmin)
admin.site.register(Standard, StandardAdmin)
admin.site.register(ClassGroup, ClassGroupAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(ELearningSubject, ELearningSubjectAdmin)
admin.site.register(Lesson, LessonAdmin)
admin.site.register(SchoolIdentity, SchoolIdentityAdmin)
admin.site.register(Term, TermAdmin)






class MyModelAdmin(AdminVideoMixin, admin.ModelAdmin):
    pass
