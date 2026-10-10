from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


def is_reviewer(user):
    """School management: superusers and staff review every teacher's notes."""
    return bool(user.is_authenticated and (user.is_superuser or user.is_staff))


def is_teacher(user):
    return bool(user.is_authenticated and hasattr(user, 'teacher'))


def is_author(user):
    """May submit/manage their own lesson notes (teachers; superusers who teach)."""
    return bool(user.is_authenticated and (is_teacher(user) or user.is_superuser))


class ReviewerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_reviewer(self.request.user)


class AuthorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_author(self.request.user)