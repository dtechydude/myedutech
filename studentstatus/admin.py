# from django.contrib import admin
# from django.contrib.auth.admin import UserAdmin
# from django.contrib.auth.models import User
# from django.utils.html import format_html

# from students.models import Parent, Student

# from .constants import ACTIVE, STATUS_LABELS
# from .models import StudentStatusLog


# @admin.register(StudentStatusLog)
# class StudentStatusLogAdmin(admin.ModelAdmin):
#     list_display = ('changed_at', 'student_name', 'student_usn', 'old_status', 'new_status', 'changed_by_name')
#     list_filter = ('new_status', 'old_status')
#     search_fields = ('student_name', 'student_usn', 'reason', 'changed_by_name')
#     date_hierarchy = 'changed_at'

#     def has_add_permission(self, request):
#         return False

#     def has_change_permission(self, request, obj=None):
#         return False

#     def has_delete_permission(self, request, obj=None):
#         return False


# # ---------------------------------------------------------------------------
# # User admin: shows the REAL portal-access status next to Django's own
# # "Active" column. is_active itself is left untouched — Django and other
# # packages rely on its normal meaning — this only adds a column so admins
# # aren't misled by is_active showing a green check for a suspended, dropped,
# # expelled, inactive or graduated student (or a parent with no active
# # children) who in fact cannot log in.
# # ---------------------------------------------------------------------------

# admin.site.unregister(User)


# @admin.register(User)
# class StatusAwareUserAdmin(UserAdmin):
#     list_display = UserAdmin.list_display + ('portal_access_status',)

#     def get_queryset(self, request):
#         # select_related avoids one extra query per row for the student and
#         # teacher case. Parent is a reverse one-to-one with an extra
#         # .children filter, which can't be select_related — the parent
#         # branch below costs one small extra query per parent row.
#         return super().get_queryset(request).select_related('student', 'teacher')

#     @admin.display(description='Portal Access')
#     def portal_access_status(self, obj):
#         if obj.is_superuser:
#             return format_html('<span style="color:#1a7f37;">●</span> {}', 'Superuser')
#         if obj.is_staff:
#             return format_html('<span style="color:#1a7f37;">●</span> {}', 'Staff')

#         student = getattr(obj, 'student', None)
#         if student is not None:
#             if student.student_status == ACTIVE:
#                 return format_html('<span style="color:#1a7f37;">●</span> {}', 'Active')
#             label = STATUS_LABELS.get(student.student_status, student.student_status)
#             return format_html('<span style="color:#b30000; font-weight:600;">●</span> {}', label)

#         parent = getattr(obj, 'parent', None)
#         if parent is not None:
#             if parent.has_active_children:
#                 return format_html('<span style="color:#1a7f37;">●</span> {}', 'Active (Parent)')
#             return format_html(
#                 '<span style="color:#b30000; font-weight:600;">●</span> {}',
#                 'Blocked — no active children',
#             )

#         teacher = getattr(obj, 'teacher', None)
#         if teacher is not None:
#             return format_html('<span style="color:#1a7f37;">●</span> {}', 'Teacher')

#         return '—'  # account type with no portal-status concept


from django.contrib import admin
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils.html import format_html

# Importing from users.admin guarantees it has already run, so CustomUserAdmin
# (which carries the Import/Export buttons) exists no matter the INSTALLED_APPS order.
from users.admin import CustomUserAdmin

from students.models import Student

from .constants import ACTIVE, STATUS_LABELS
from .models import StudentStatusLog

User = get_user_model()


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
# User admin: keeps everything from CustomUserAdmin (Import/Export buttons,
# CSV action, UserResource) and adds the REAL portal-access status next to
# Django's own "Active" column. is_active itself is left untouched: Django and
# other packages rely on its normal meaning. This only stops admins being
# misled by a green is_active tick for a suspended, dropped, expelled,
# inactive or graduated student (or a parent with no active children) who in
# fact cannot log in.
# ---------------------------------------------------------------------------

# Replace whatever is currently registered (Django's default or CustomUserAdmin)
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

_GREEN, _RED = '#1a7f37', '#b30000'


def _dot(colour, text, bold=False):
    style = f'color:{colour};' + ('font-weight:600;' if bold else '')
    return format_html('<span style="{}">●</span> {}', style, text)


@admin.register(User)
class StatusAwareUserAdmin(CustomUserAdmin):
    list_display = CustomUserAdmin.list_display + ('portal_access_status',)

    def get_queryset(self, request):
        # Reverse one-to-ones CAN be select_related, so parent is included too:
        # no extra query per row for student, teacher or parent.
        return super().get_queryset(request).select_related('student', 'teacher', 'parent')

    def _active_children(self, request):
        """{parent pk: number of active children}: ONE query per page load, not one per parent row."""
        if not hasattr(request, '_active_children_map'):
            rows = (Student.objects.filter(student_status=ACTIVE)
                    .exclude(parent__isnull=True)
                    .values('parent').annotate(n=Count('pk')))
            request._active_children_map = {r['parent']: r['n'] for r in rows}
        return request._active_children_map

    def portal_access_status(self, obj):
        # list_display methods don't receive the request, so read it from the current changelist
        request = getattr(self, '_current_request', None)

        if obj.is_superuser:
            return _dot(_GREEN, 'Superuser')
        if obj.is_staff:
            return _dot(_GREEN, 'Staff')

        student = getattr(obj, 'student', None)
        if student is not None:
            if student.student_status == ACTIVE:
                return _dot(_GREEN, 'Active')
            label = STATUS_LABELS.get(student.student_status, student.student_status)
            return _dot(_RED, label, bold=True)

        parent = getattr(obj, 'parent', None)
        if parent is not None:
            has_active = (self._active_children(request).get(parent.pk, 0) > 0
                          if request is not None else parent.has_active_children)
            if has_active:
                return _dot(_GREEN, 'Active (Parent)')
            return _dot(_RED, 'Blocked — no active children', bold=True)

        if getattr(obj, 'teacher', None) is not None:
            return _dot(_GREEN, 'Teacher')

        return '—'  # account type with no portal-status concept

    portal_access_status.short_description = 'Portal Access'

    def changelist_view(self, request, extra_context=None):
        # Make the request available to portal_access_status for the one-query lookup
        self._current_request = request
        try:
            return super().changelist_view(request, extra_context)
        finally:
            self._current_request = None