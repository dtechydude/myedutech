from django.contrib import admin
from users.models import Profile
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



class UserProfileAdmin(ImportExportModelAdmin, admin.ModelAdmin):
           
    list_display=('user', 'code', 'user_type', 'phone', 'state_of_origin')
    list_filter  = ['user_type',]
    search_fields = ('user__username', 'code', 'user_type')


# # User = get_user_model()

# def export_to_csv(modeladmin, request, queryset):
#     opts = modeladmin.model._meta
#     response = HttpResponse(content_type='text/csv')
#     response['Content-Disposition'] = 'attachment;' 'filename={}.csv'.format(opts.verbose_name)
#     writer = csv.writer(response)
#     fields = [field for field in opts.get_fields() if not field.many_to_many and not field.one_to_many]
#     # Write a first row with header information
#     writer.writerow([field.verbose_name for field in fields])
#     # Write data rows
#     for obj in queryset:
#         data_row = []
#         for field in fields:
#             value = getattr(obj, field.name)
#             if isinstance(value, datetime.datetime):
#                 value = value.strftime('%d/%m/%Y')
#             data_row.append(value)
#         writer.writerow(data_row)

#     return response

# export_to_csv.short_description = 'Export to CSV'  #short description

# # @admin.register(User)
# class UserAdmin(admin.ModelAdmin):
#     '''
#     Registers the action in your model admin
#     '''
#     actions = [export_to_csv] 



# Register your models here.
admin.site.register(Profile, UserProfileAdmin)
