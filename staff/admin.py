from django.contrib import admin
from .models import StaffPosition, Teacher, StaffAttendance
from import_export.admin import ImportExportModelAdmin


class StaffPositionAdmin(ImportExportModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)
    ordering = ['name',]
    exclude = ('slug',)

    
class TeacherAdmin(ImportExportModelAdmin):
    list_display = ( 'user', 'last_name', 'first_name', 'staff_role', 'phone_home', 'qualification' )
    search_fields = ('first_name', 'last_name')
    list_filter = ['staff_role',]
    ordering = ['dept__name', 'first_name']
    raw_id_fields = ['user', 'dept']



# attendance/admin.py

@admin.register(StaffAttendance)
class StaffAttendanceAdmin(admin.ModelAdmin):

    list_display = (
        'teacher',
        'date',
        'check_in_time',
        'check_out_time',
        'status',
        'is_late',
    )
    raw_id_fields = (
        'teacher',
        'checked_in_by',
        'checked_out_by',
    )

    list_filter = (
        'status',
        'is_late',
        'date',
    )

    search_fields = (
        'teacher__user__first_name',
        'teacher__user__last_name',
        'teacher__staff_id',
    )

    ordering = ('-date',)






# admin.site.register(StaffCategory)
admin.site.register(StaffPosition, StaffPositionAdmin)
admin.site.register(Teacher, TeacherAdmin)

