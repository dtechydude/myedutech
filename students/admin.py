from django.contrib import admin
from .models import Hostel, Student, Badge, Parent
from import_export.admin import ImportExportModelAdmin


class HostelAdmin(admin.ModelAdmin):
    list_display = ('name', 'hostel_master')
    search_fields = ('name',)
    ordering = ['name',]
    raw_id_fields = ['hostel_master']
    exclude = ('slug',)



class StudentAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ('user', 'USN', 'first_name', 'last_name', 'current_class','date_admitted', 'guardian_phone', 'student_status')
    list_filter = ['current_class', 'student_status',]

    # This is the corrected search_fields tuple
    search_fields = ('first_name', 'last_name', 'user__username', 'current_class__name', 'USN')

    raw_id_fields = ['user', 'form_teacher', 'badge', 'class_on_admission', 'hostel_name', 'parent',]
    autocomplete_fields = ['current_class', 'class_on_admission']
    exclude=('fee_balance',)





class BadgeAdmin(ImportExportModelAdmin, admin.ModelAdmin):
       
    list_display=('name', 'desc')
    exclude=('slug',)

# Register the Parent model so it's visible in the admin panel.
@admin.register(Parent)
class ParentAdmin(admin.ModelAdmin):
    # This will display the associated user in the Parent list view.
    list_display = ('user', 'guardian_name', 'guardian_address', 'guardian_phone')
    search_fields = ('user__username',)
    raw_id_fields = ['user',]



# admin.site.register(StaffCategory)
admin.site.register(Hostel, HostelAdmin)
admin.site.register(Student, StudentAdmin)
admin.site.register(Badge, BadgeAdmin)
# admin.site.register(Parent, ParentAdmin)


