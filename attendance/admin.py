from datetime import timedelta, datetime
from django.contrib import admin
from .models import Attendance


class AttendanceAdmin(admin.ModelAdmin):   
 
    list_display = ('student', 'date',  'present')
    list_filter = ['student__current_class']
    search_fields = ('student__first_name', 'student__last_name', 'student__user__username', 'student__USN')
    raw_id_fields = ['student',]

  

admin.site.register(Attendance, AttendanceAdmin)
