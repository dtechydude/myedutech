from django.contrib import admin
from .models import Hostel, Student, Badge, StudentId
from import_export.admin import ImportExportModelAdmin



class HostelAdmin(admin.ModelAdmin):
    list_display = ('name', 'hostel_master')
    search_fields = ('name',)
    ordering = ['name',]
    exclude = ('slug',)

class StudentIdInline(admin.TabularInline):
    model = StudentId
    exclude =['f_1', 'f_2', 'f_3']
    max_num = 1
    
    def has_delete_permission(self, request, obj=None):
        return False

class StudentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    inlines = [StudentIdInline] 
    list_display=('user', 'first_name', 'last_name', 'current_class','date_admitted', 'guardian_phone')
    list_filter = ['current_class']
    search_fields = ('first_name', 'last_name', 'user__username')
    raw_id_fields = ['user', 'form_teacher', 'badge', 'current_class', 'class_on_admission', 'hostel_name']


class BadgeAdmin(ImportExportModelAdmin, admin.ModelAdmin):
       
    list_display=('name',)
    exclude=('slug',)

# admin.site.register(StaffCategory)
admin.site.register(Hostel, HostelAdmin)
admin.site.register(Student, StudentAdmin)
admin.site.register(Badge, BadgeAdmin)


