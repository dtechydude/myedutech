# """
# KwikSchools — Prep Report Card Permissions
# ============================================
# Reusable permission classes / mixins for CBV and DRF.
# """

# from django.contrib.auth.mixins import UserPassesTestMixin
# from django.core.exceptions import PermissionDenied


# class PrepReportEditPermissionMixin(UserPassesTestMixin):
#     """
#     Mixin for views that require the user to be able to edit the report card.
#     The view must set self.report_card before calling test_func.
#     """
#     def test_func(self):
#         from .services import user_can_edit_report
#         report_card = getattr(self, 'report_card', None)
#         if report_card is None:
#             return False
#         return user_can_edit_report(self.request.user, report_card)

#     def handle_no_permission(self):
#         raise PermissionDenied


# class FormTeacherOnlyMixin(UserPassesTestMixin):
#     """
#     Mixin: only the form teacher of the prep class (or admin) may access.
#     View must set self.report_card.
#     """
#     def test_func(self):
#         from .services import user_can_edit_domain_ratings
#         report_card = getattr(self, 'report_card', None)
#         if report_card is None:
#             return False
#         return user_can_edit_domain_ratings(self.request.user, report_card)

#     def handle_no_permission(self):
#         raise PermissionDenied


# class AdminOrStaffRequiredMixin(UserPassesTestMixin):
#     """Only superusers and is_staff can access."""
#     def test_func(self):
#         return self.request.user.is_superuser or self.request.user.is_staff

#     def handle_no_permission(self):
#         raise PermissionDenied


"""
KwikSchools — Prep Report Card Permissions
============================================
Reusable permission classes / mixins for CBV and DRF.
"""

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied


class PrepReportEditPermissionMixin(UserPassesTestMixin):
    """
    Mixin for workspace entry validation. Ensures the teacher is assigned 
    to the target class layout or teaches at least one subject in it.
    """
    def test_func(self):
        from .services import user_can_edit_report
        report_card = getattr(self, 'report_card', None)
        if report_card is None:
            return False
        return user_can_edit_report(self.request.user, report_card)

    def handle_no_permission(self):
        raise PermissionDenied


class FormTeacherOnlyMixin(UserPassesTestMixin):
    """
    Strict structural mixin. Ensures only the dedicated Form Teacher, 
    Admins, or Staff can access high-level components.
    """
    def test_func(self):
        from .services import user_can_modify_class_metadata
        report_card = getattr(self, 'report_card', None)
        if report_card is None:
            return False
        return user_can_modify_class_metadata(self.request.user, report_card)

    def handle_no_permission(self):
        raise PermissionDenied


class AdminOrStaffRequiredMixin(UserPassesTestMixin):
    """Bypasses custom teacher trees entirely—restricting access exclusively to platform administrators."""
    def test_func(self):
        return self.request.user.is_superuser or self.request.user.is_staff

    def handle_no_permission(self):
        raise PermissionDenied