from __future__ import annotations
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
 

# class UserProfileAdmin(ImportExportModelAdmin):
           
#     list_display=('user', 'last_name', 'first_name', 'code', 'user_type', 'phone', 'state_of_origin', 'code')
#     def last_name(self, obj):
#         return obj.user.last_name

#     def first_name(self, obj):
#         return obj.user.first_name

#     last_name.admin_order_field = 'user__last_name'
#     first_name.admin_order_field = 'user__first_name'

#     list_filter  = [StudentClassFilter, 'user_type',]
#     search_fields = ('user__username', 'user_type', 'user__last_name', 'user__first_name', 'code')
#     raw_id_fields = ['user',]


class DeptAdmin(ImportExportModelAdmin):
       
    list_display=('id', 'name')
    list_filter  = ['name',]
    search_fields = ('name',)
    # raw_id_fields = ['name',]



"""
admin.py — Profile Admin with Auto Image Cleanup
KwikSchools — Smarter Schools!

Merge this into your existing users/admin.py.
The save_model() override handles old image deletion independently
of the signals.py logic — works for both inline and standalone admin saves.
"""
# from __future__ import annotations

import logging
import os

from django.contrib import admin
from django.contrib.auth import get_user_model

# ── Change this import to match your app ─────────────────────────────────────
from users.models import Profile
# from users.models import Profile  ← use this if your app is named 'users'

User = get_user_model()
logger = logging.getLogger(__name__)

DEFAULT_IMAGE_NAME = 'default.jpg'


def _delete_old_image_if_changed(old_image_field, new_image_field) -> None:
    """
    Delete the old profile image file from disk when it has been replaced.
    Safe: never deletes the default image, never raises on missing files.
    """
    if not old_image_field:
        return

    old_name = str(old_image_field)
    new_name = str(new_image_field) if new_image_field else ''

    if old_name == new_name:
        return  # image unchanged — nothing to do

    if os.path.basename(old_name) == DEFAULT_IMAGE_NAME:
        return  # never delete the fallback default

    try:
        old_path = old_image_field.path
        if os.path.isfile(old_path):
            os.remove(old_path)
            logger.info(f'[Admin] Deleted old profile image: {old_path}')
        else:
            logger.debug(f'[Admin] Old image already missing from disk: {old_path}')
    except (ValueError, AttributeError):
        pass  # blank/empty ImageField — nothing to delete
    except OSError as e:
        logger.warning(f'[Admin] Could not delete old profile image "{old_name}": {e}')


# ── Inline: edit Profile directly from the User admin page ───────────────────

class ProfileInline(admin.StackedInline):
    model   = Profile
    can_delete  = False
    verbose_name = 'Profile'
    verbose_name_plural = 'Profile'
    extra   = 0
    fields  = (
        'image', 'phone', 'user_type', 'state_of_origin',
        'address', 'bio', 'activate',
    )

    # ── Inline save hook ──────────────────────────────────────────────────────
    def save_model(self, request, obj, form, change):
        """Called when saving the inline from the User change page."""
        if change and 'image' in form.changed_data:
            try:
                old = Profile.objects.get(pk=obj.pk)
                _delete_old_image_if_changed(old.image, obj.image)
            except Profile.DoesNotExist:
                pass
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        """
        save_formset is what actually fires for inlines — override this
        in addition to save_model for full inline coverage.
        """
        instances = formset.save(commit=False)
        for instance in instances:
            if instance.pk:
                try:
                    old = Profile.objects.get(pk=instance.pk)
                    _delete_old_image_if_changed(old.image, instance.image)
                except Profile.DoesNotExist:
                    pass
            instance.save()
        formset.save_m2m()


# ── Standalone Profile admin ──────────────────────────────────────────────────

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display  = (
        'get_username', 'get_full_name', 'user_type',
        'phone', 'state_of_origin', 'activate', 'has_custom_photo',
    )
    list_filter   = ('user_type', 'activate', 'state_of_origin')
    search_fields = (
        'user__username', 'user__first_name',
        'user__last_name', 'user__email', 'phone',
    )
    readonly_fields  = ('code', 'created', 'updated', 'get_current_image_preview')
    list_per_page    = 50
    ordering         = ('user__last_name', 'user__first_name')

    fieldsets = (
        ('User Account', {
            'fields': ('user',),
        }),
        ('Profile Photo', {
            'fields': ('get_current_image_preview', 'image'),
            'description': (
                'Uploading a new image will automatically delete '
                'the previous one from the server.'
            ),
        }),
        ('Personal Details', {
            'fields': ('phone', 'state_of_origin', 'address', 'bio'),
        }),
        ('Account Settings', {
            'fields': ('user_type', 'activate', 'recommended_by'),
        }),
        ('System Info', {
            'fields': ('code', 'created', 'updated'),
            'classes': ('collapse',),
        }),
    )

    # ── Display helpers ───────────────────────────────────────────────────────

    @admin.display(description='Username', ordering='user__username')
    def get_username(self, obj):
        return obj.user.username

    @admin.display(description='Full Name', ordering='user__last_name')
    def get_full_name(self, obj):
        return f'{obj.user.last_name} {obj.user.first_name}'.strip() or '—'

    @admin.display(description='Has Photo', boolean=True)
    def has_custom_photo(self, obj):
        return bool(obj.image) and os.path.basename(str(obj.image)) != DEFAULT_IMAGE_NAME

    @admin.display(description='Current Photo')
    def get_current_image_preview(self, obj):
        """Show a small thumbnail of the current photo in the change form."""
        from django.utils.html import format_html
        if obj.image:
            try:
                url = obj.image.url
                return format_html(
                    '<img src="{}" style="'
                    'width:80px;height:80px;object-fit:cover;'
                    'border-radius:8px;border:2px solid #e2e8f0;'
                    '" />',
                    url,
                )
            except Exception:
                pass
        return '— no photo —'

    # ── Core save hook — fires for every admin save ───────────────────────────

    def save_model(self, request, obj, form, change):
        """
        Override the admin save to delete the old image whenever
        the image field has changed.

        `change` is True  → existing record being updated
        `change` is False → brand-new profile being created
        """
        if change and 'image' in form.changed_data:
            try:
                # Re-fetch from DB to get the CURRENT (old) image before saving
                old_profile = Profile.objects.get(pk=obj.pk)
                _delete_old_image_if_changed(old_profile.image, obj.image)
            except Profile.DoesNotExist:
                pass  # shouldn't happen on `change=True`, but guard anyway

        super().save_model(request, obj, form, change)


# ── Optionally extend the built-in UserAdmin with Profile inline ──────────────
# Uncomment the block below if you want to edit Profile photos
# directly from the User page in the admin.
#
# from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
# from django.contrib.auth.models import User as AuthUser
#
# admin.site.unregister(AuthUser)
#
# @admin.register(AuthUser)
# class UserAdmin(BaseUserAdmin):
#     inlines = (ProfileInline,)
#
#     def save_formset(self, request, form, formset, change):
#         """Catches inline Profile saves from the User admin page."""
#         instances = formset.save(commit=False)
#         for instance in instances:
#             if isinstance(instance, Profile) and instance.pk:
#                 try:
#                     old = Profile.objects.get(pk=instance.pk)
#                     _delete_old_image_if_changed(old.image, instance.image)
#                 except Profile.DoesNotExist:
#                     pass
#             instance.save()
#         formset.save_m2m()





# Register your models here.
# admin.site.register(Profile, UserProfileAdmin)
admin.site.register(Dept, DeptAdmin)
