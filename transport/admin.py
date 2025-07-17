from django.contrib import admin
from .models import Route, StudentOnRoute
from import_export.admin import ImportExportModelAdmin



class RouteAdmin(admin.ModelAdmin):
    list_display = ('name', 'route_id', 'direction', 'staff_in_charge', 'driver')
    search_fields = ('name', 'staff_in_charge__full_name',)
    ordering = ['name',]
    exclude = ('slug',)

class StudentOnRouteAdmin(admin.ModelAdmin):
    list_display = ('student', 'route',)
    search_fields = ('student', 'student__current_standard')
    ordering = ['route',]
    exclude = ('slug',)



admin.site.register(Route, RouteAdmin)
admin.site.register(StudentOnRoute, StudentOnRouteAdmin)
