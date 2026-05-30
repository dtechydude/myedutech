"""
KwikSchools — Prep Report Card Tests
======================================
Run with:  python manage.py test prep_reports
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch, MagicMock

from .models import (
    PrepClass, RatingScale, RatingColumn,
    PrepSubjectSkill, PrepAcademicPeriod,
    PrepReportCard, PrepSkillEntry, PrepDomainRating,
    PrepDomainTraitTemplate,
)
from .services import (
    create_report_card,
    save_subject_skill_entries,
    submit_report_card,
    approve_report_card,
    user_can_edit_report,
    user_can_edit_domain_ratings,
    _get_teacher,
)

User = get_user_model()


class PrepReportCardModelTest(TestCase):
    """Basic model creation & relationship tests."""

    def setUp(self):
        # Minimal mocked Standard and Subject for FK resolution
        pass

    def test_rating_scale_default_uniqueness(self):
        """Only one RatingScale can be default at a time."""
        s1 = RatingScale.objects.create(name="Scale A", is_default=True)
        s2 = RatingScale.objects.create(name="Scale B", is_default=True)
        s1.refresh_from_db()
        self.assertFalse(s1.is_default)
        self.assertTrue(s2.is_default)

    def test_academic_period_current_uniqueness(self):
        """Only one PrepAcademicPeriod can be current."""
        p1 = PrepAcademicPeriod.objects.create(
            session="2023/2024", term="1", is_current=True
        )
        p2 = PrepAcademicPeriod.objects.create(
            session="2024/2025", term="1", is_current=True
        )
        p1.refresh_from_db()
        self.assertFalse(p1.is_current)
        self.assertTrue(p2.is_current)

    def test_rating_column_ordering(self):
        scale = RatingScale.objects.create(name="Test Scale")
        RatingColumn.objects.create(scale=scale, label="C", order=3)
        RatingColumn.objects.create(scale=scale, label="A", order=1)
        RatingColumn.objects.create(scale=scale, label="B", order=2)
        labels = list(scale.columns.values_list('label', flat=True))
        self.assertEqual(labels, ["A", "B", "C"])


class PermissionServiceTest(TestCase):
    """Test permission helper functions."""

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin', password='admin', email='admin@test.com'
        )
        self.staff_user = User.objects.create_user(
            username='staff', password='staff', is_staff=True
        )
        self.regular_user = User.objects.create_user(
            username='teacher', password='teacher'
        )

    def test_superuser_can_edit_any_report(self):
        mock_card = MagicMock()
        self.assertTrue(user_can_edit_report(self.admin_user, mock_card))

    def test_staff_can_edit_any_report(self):
        mock_card = MagicMock()
        self.assertTrue(user_can_edit_report(self.staff_user, mock_card))

    def test_regular_user_without_teacher_record_cannot_edit(self):
        mock_card = MagicMock()
        result = user_can_edit_report(self.regular_user, mock_card)
        self.assertFalse(result)

    def test_superuser_can_edit_domain_ratings(self):
        mock_card = MagicMock()
        self.assertTrue(user_can_edit_domain_ratings(self.admin_user, mock_card))


class WorkflowTest(TestCase):
    """Test report card status workflow."""

    def _make_card(self, status='draft'):
        """Creates a minimal PrepReportCard with required FKs mocked."""
        user = User.objects.create_superuser('wf_admin', 'a@a.com', 'pass')
        scale = RatingScale.objects.create(name="WF Scale")
        period = PrepAcademicPeriod.objects.create(
            session="2024/2025", term="1"
        )
        # We need a real Student and PrepClass — but those require
        # curriculum/students apps to be installed.
        # In isolated tests, patch the FK checks.
        return user, scale, period

    def test_submit_requires_draft_status(self):
        """Submitting a non-draft card raises ValueError."""
        user = User.objects.create_superuser('sub_admin', 'b@b.com', 'pass')
        mock_card = MagicMock()
        mock_card.status = 'submitted'
        with self.assertRaises(ValueError):
            submit_report_card(user, mock_card)

    def test_approve_requires_admin(self):
        """Non-admin cannot approve a card."""
        from django.core.exceptions import PermissionDenied
        regular = User.objects.create_user('reg2', password='pass')
        mock_card = MagicMock()
        mock_card.status = 'submitted'
        with self.assertRaises(PermissionDenied):
            approve_report_card(regular, mock_card)
