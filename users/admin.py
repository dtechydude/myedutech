from django.contrib import admin
from users.models import Profile, Dept
from django.contrib.auth import get_user_model
from django.http import HttpResponse
import csv, datetime
from import_export.admin import ImportExportModelAdmin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin # Import the default UserAdmin
from import_export import resources # You might need this if you customize resource


User = get_user_model()
# 1. Unregister the default UserAdmin
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass # Already unregistered or not registered in the first place

# 2. Define your custom UserResource (optional, but good for control)
# This allows you to specify exactly which fields to export/import
class UserResource(resources.ModelResource):
    class Meta:
        model = User
        # Define the fields you want to export.
        # Ensure these fields exist on your User model.
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined', 'last_login')
        export_order = ('id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined', 'last_login') # Order of fields in export

# 3. Register your ImportExportModelAdmin with the User model
@admin.register(User)
class CustomUserAdmin(ImportExportModelAdmin, DefaultUserAdmin): # Inherit from DefaultUserAdmin for base functionality
    resource_class = UserResource
    # You can still add your list_display, search_fields, etc. from DefaultUserAdmin
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active')
    search_fields = ('username', 'email', 'first_name', 'last_name')

    # If you have custom fields in your User model (if you extended it),
    # you might need to adjust fieldsets here as well.
    # For example, if you added a 'phone_number' field:
    # fieldsets = DefaultUserAdmin.fieldsets + (
    #     (('Contact Info'), {'fields': ('phone_number',)}),
    # )


class StudentClassFilter(admin.SimpleListFilter):
    title = 'Student Class'
    parameter_name = 'current_class'

    def lookups(self, request, model_admin):
        from students.models import Standard
        return [(cls.id, cls.name) for cls in Standard.objects.all()]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(user__student__current_class_id=self.value())
        return queryset
 

class UserProfileAdmin(ImportExportModelAdmin):
           
    list_display=('user', 'last_name', 'first_name', 'code', 'user_type', 'phone', 'state_of_origin', 'code')
    def last_name(self, obj):
        return obj.user.last_name

    def first_name(self, obj):
        return obj.user.first_name

    last_name.admin_order_field = 'user__last_name'
    first_name.admin_order_field = 'user__first_name'

    list_filter  = [StudentClassFilter, 'user_type',]
    search_fields = ('user__username', 'user_type', 'user__last_name', 'user__first_name', 'code')
    raw_id_fields = ['user',]


class DeptAdmin(ImportExportModelAdmin):
       
    list_display=('id', 'name')
    list_filter  = ['name',]
    search_fields = ('name',)
    # raw_id_fields = ['name',]




# Register your models here.
admin.site.register(Profile, UserProfileAdmin)
admin.site.register(Dept, DeptAdmin)
