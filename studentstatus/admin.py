from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html

from students.models import Parent, Student

from .constants import ACTIVE, STATUS_LABELS
from .models import StudentStatusLog


@admin.register(StudentStatusLog)
class StudentStatusLogAdmin(admin.ModelAdmin):
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


# ---------------------------------------------------------------------------
# User admin: shows the REAL portal-access status next to Django's own
# "Active" column. is_active itself is left untouched — Django and other
# packages rely on its normal meaning — this only adds a column so admins
# aren't misled by is_active showing a green check for a suspended, dropped,
# expelled, inactive or graduated student (or a parent with no active
# children) who in fact cannot log in.
# ---------------------------------------------------------------------------

admin.site.unregister(User)


@admin.register(User)
class StatusAwareUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ('portal_access_status',)

    def get_queryset(self, request):
        # select_related avoids one extra query per row for the student and
        # teacher case. Parent is a reverse one-to-one with an extra
        # .children filter, which can't be select_related — the parent
        # branch below costs one small extra query per parent row.
        return super().get_queryset(request).select_related('student', 'teacher')

    @admin.display(description='Portal Access')
    def portal_access_status(self, obj):
        if obj.is_superuser:
            return format_html('<span style="color:#1a7f37;">●</span> {}', 'Superuser')
        if obj.is_staff:
            return format_html('<span style="color:#1a7f37;">●</span> {}', 'Staff')

        student = getattr(obj, 'student', None)
        if student is not None:
            if student.student_status == ACTIVE:
                return format_html('<span style="color:#1a7f37;">●</span> {}', 'Active')
            label = STATUS_LABELS.get(student.student_status, student.student_status)
            return format_html('<span style="color:#b30000; font-weight:600;">●</span> {}', label)

        parent = getattr(obj, 'parent', None)
        if parent is not None:
            if parent.has_active_children:
                return format_html('<span style="color:#1a7f37;">●</span> {}', 'Active (Parent)')
            return format_html(
                '<span style="color:#b30000; font-weight:600;">●</span> {}',
                'Blocked — no active children',
            )

        teacher = getattr(obj, 'teacher', None)
        if teacher is not None:
            return format_html('<span style="color:#1a7f37;">●</span> {}', 'Teacher')

        return '—'  # account type with no portal-status concept