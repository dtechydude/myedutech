from django.contrib import admin
from .models import Event
from import_export.admin import ImportExportModelAdmin

@admin.register(Event)
class EventAdmin(ImportExportModelAdmin):
    """
    Customizes the Django admin interface for the Event model.
    """
    list_display = ('title', 'organizer', 'start_time', 'end_time', 'visibility')
    list_filter = ('visibility', 'organizer', 'start_time')
    search_fields = ('title', 'description', 'organizer__username')
    date_hierarchy = 'start_time'
    ordering = ('start_time',)

    fieldsets = (
        (None, {
            'fields': ('title', 'description')
        }),
        ('Event Details', {
            'fields': ('start_time', 'end_time', 'visibility'),
        }),
        ('Organizer', {
            'fields': ('organizer',),
            'classes': ('collapse',),
        }),
    )

    # Automatically set the organizer to the current logged-in user
    def save_model(self, request, obj, form, change):
        if not change:
            obj.organizer = request.user
        super().save_model(request, obj, form, change)