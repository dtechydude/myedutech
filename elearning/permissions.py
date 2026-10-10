from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied


def get_student(user):
    """Student profile for `user`, or None (safe for the reverse one-to-one)."""
    return getattr(user, 'student', None)


def is_teacher_or_staff(user):
    return bool(
        user.is_authenticated
        and (user.is_superuser or user.is_staff or hasattr(user, 'teacher'))
    )


def can_access_standard(user, standard_id):
    """Teachers/staff: every class. Students: only their own class."""
    if is_teacher_or_staff(user):
        return True
    student = get_student(user)
    return bool(student and student.current_class_id == standard_id)


class TeacherRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_teacher_or_staff(self.request.user)


class ClassAccessMixin(LoginRequiredMixin):
    """
    Login required, and a student may only open content belonging to their
    own class. Subclasses implement get_standard_id(obj).
    """

    def get_standard_id(self, obj):
        raise NotImplementedError

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if not can_access_standard(self.request.user, self.get_standard_id(obj)):
            raise PermissionDenied
        return obj