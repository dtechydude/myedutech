from datetime import timedelta, datetime
from django.contrib import admin
from .models import Attendance
from import_export.admin import ImportExportModelAdmin

@admin.register(Attendance)
class AttendanceAdmin(ImportExportModelAdmin):   
 
    list_display = ('student', 'date',  'present')
    list_filter = ['student__current_class']
    search_fields = ('student__first_name', 'student__last_name', 'student__user__username', 'student__USN')
    raw_id_fields = ['student',]

  


