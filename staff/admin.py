from django.contrib import admin
from .models import StaffPosition, Teacher
from import_export.admin import ImportExportModelAdmin



class StaffPositionAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    ordering = ['name',]
    exclude = ('slug',)

    
class TeacherAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ( 'user', 'first_name', 'staff_role', 'phone_home' )
    search_fields = ('first_name',)
    ordering = ['dept__name', 'first_name']
    raw_id_fields = ['user',]



# admin.site.register(StaffCategory)
admin.site.register(StaffPosition, StaffPositionAdmin)
admin.site.register(Teacher, TeacherAdmin)

