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

  
from django.contrib import admin

from .models import (
    AttendanceConfiguration,
    AttendanceSummary
)


@admin.register(AttendanceConfiguration)
class AttendanceConfigurationAdmin(admin.ModelAdmin):

    list_display = (
        'session',
        'term',
        'total_school_days'
    )

    list_filter = (
        'session',
        'term'
    )


@admin.register(AttendanceSummary)
class AttendanceSummaryAdmin(admin.ModelAdmin):

    list_display = (
        'student',
        'session',
        'term',
        'days_present',
        'days_absent',
        'attendance_percentage'
    )

    search_fields = (
        'student__first_name',
        'student__last_name',
        'student__USN'
    )

    list_filter = (
        'session',
        'term'
    )

