from django.contrib import admin
from .models import Route, StudentOnRoute
from import_export.admin import ImportExportModelAdmin



class RouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'route_id', 'bus_fee', 'direction', 'staff_in_charge', 'driver', 'driver_phone')
    search_fields = ('name', 'staff_in_charge__full_name',)
    ordering = ['name',]
    raw_id_fields = ['staff_in_charge']
    exclude = ('slug',)

@admin.register(StudentOnRoute)
class StudentOnRouteAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = (
        'student_full_name',  # This will be a custom method
        'route',
        'signup_date',
        'amount_paid',
        'is_approved',
        'payment_date',
    )
    list_filter = ('route', 'signup_date', 'is_active_on_bus')
    search_fields = (
        'student__first_name', # Corrected: Access directly from User
        'student__last_name',  # Corrected: Access directly from User
        # 'student__student_id', # Remove this if student is a User, as User has no student_id
        'route__name'
    )
    raw_id_fields = ['student', 'route']
    date_hierarchy = 'signup_date'

    # Custom method to get the student's full name
    def student_full_name(self, obj):
        # If obj.student is a User object directly
        if obj.student: # obj.student is already the User instance
            return f"{obj.student.first_name} {obj.student.last_name}"
        return "N/A"
    
    student_full_name.short_description = 'Student Name' # Column header name
    student_full_name.admin_order_field = 'student__first_name' # Allows sorting by first name (direct from User)

admin.site.register(Route, RouteAdmin)
# admin.site.register(StudentOnRoute, StudentOnRouteAdmin)
