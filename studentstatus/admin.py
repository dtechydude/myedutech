from django.contrib import admin

from .models import StudentStatusLog


@admin.register(StudentStatusLog)
class StudentStatusLogAdmin(admin.ModelAdmin):
    """Read-only: the audit trail must not be editable or deletable."""
    list_display = ('changed_at', 'student_name', 'student_usn', 'old_status', 'new_status', 'changed_by_name')
    list_filter = ('new_status', 'old_status')
    search_fields = ('student_name', 'student_usn', 'reason', 'changed_by_name')
    date_hierarchy = 'changed_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False