import unittest
from datetime import date, timedelta
from io import StringIO

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Teacher, TeacherStatusLog
from .teacher_status import (deactivate_teacher, deactivation_warnings, mark_selected_former,
                             reactivate_selected, reactivate_teacher)

User = get_user_model()


def make_teacher(username='t1', first='Ada', last='Obi', password='x', **kwargs):
    """A teacher with a linked login. (dept / staff_role default to non-existent ids in some
    deployments, so they are set to None explicitly.)"""
    user = User.objects.create_user(username, first_name=first, last_name=last, password=password)
    fields = {f.name for f in Teacher._meta.get_fields()}
    for name in ('dept', 'staff_role'):
        if name in fields:
            kwargs.setdefault(name, None)
    return Teacher.objects.create(user=user, first_name=first, last_name=last, **kwargs)


class QuerySetTests(TestCase):
    def test_current_and_former(self):
        a, b = make_teacher('a'), make_teacher('b')
        Teacher.objects.filter(pk=b.pk).update(active=False)
        self.assertEqual(list(Teacher.objects.current()), [a])
        self.assertEqual(list(Teacher.objects.former()), [b])
        self.assertEqual(Teacher.objects.count(), 2)          # existing Teacher.objects.* is untouched

    def test_new_teachers_are_active_by_default(self):
        self.assertTrue(make_teacher().active)


class StatusChangeTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', is_staff=True, password='x')
        self.teacher = make_teacher()

    def test_deactivation_switches_login_off_sets_dates_and_logs_it(self):
        deactivate_teacher(self.teacher, by=self.admin, reason='Resigned', date_left=date(2026, 7, 31))
        self.teacher.refresh_from_db(); self.teacher.user.refresh_from_db()
        self.assertFalse(self.teacher.active)
        self.assertFalse(self.teacher.user.is_active)
        self.assertEqual((self.teacher.date_left, self.teacher.left_reason), (date(2026, 7, 31), 'Resigned'))
        log = TeacherStatusLog.objects.get()
        self.assertEqual((log.action, log.reason, log.changed_by, log.effective_date),
                         ('deactivated', 'Resigned', self.admin, date(2026, 7, 31)))

    def test_ticking_active_off_in_the_admin_does_the_same_automatically(self):
        self.teacher.active = False            # what the admin tick-box / any plain save does
        self.teacher.save()
        self.teacher.refresh_from_db(); self.teacher.user.refresh_from_db()
        self.assertFalse(self.teacher.user.is_active)
        self.assertEqual(self.teacher.date_left, timezone.localdate())   # filled in automatically
        self.assertIsNone(TeacherStatusLog.objects.get().changed_by)     # admin tick-box: actor unknown

    def test_reactivation_restores_the_login_and_clears_the_dates(self):
        deactivate_teacher(self.teacher, by=self.admin, reason='Contract ended')
        self.teacher.refresh_from_db()
        reactivate_teacher(self.teacher, by=self.admin)
        self.teacher.refresh_from_db(); self.teacher.user.refresh_from_db()
        self.assertTrue(self.teacher.active and self.teacher.user.is_active)
        self.assertEqual((self.teacher.date_left, self.teacher.left_reason), (None, ''))
        self.assertEqual(list(TeacherStatusLog.objects.values_list('action', flat=True).order_by('id')),
                         ['deactivated', 'reactivated'])      # the history survives

    def test_a_superusers_login_is_never_switched_off(self):
        boss = User.objects.create_superuser('boss', 'b@x.com', 'x')
        t = Teacher.objects.create(user=boss, first_name='Head', last_name='Teacher',
                                   **{n: None for n in ('dept', 'staff_role') if n in {f.name for f in Teacher._meta.get_fields()}})
        deactivate_teacher(t, by=self.admin, reason='Test')
        boss.refresh_from_db()
        self.assertTrue(boss.is_active)

    def test_creating_a_teacher_never_touches_the_login(self):
        t = make_teacher('newbie', active=False)     # even added as already-inactive
        t.user.refresh_from_db()
        self.assertTrue(t.user.is_active)
        self.assertEqual(TeacherStatusLog.objects.count(), 0)

    def test_saving_other_fields_of_an_already_inactive_teacher_changes_nothing(self):
        # rollout safety: legacy rows with active=False are not mass-locked-out by an ordinary save
        Teacher.objects.filter(pk=self.teacher.pk).update(active=False)
        self.teacher.refresh_from_db()
        self.teacher.first_name = 'Changed'
        self.teacher.save()
        self.teacher.user.refresh_from_db()
        self.assertTrue(self.teacher.user.is_active)
        self.assertEqual(TeacherStatusLog.objects.count(), 0)

    def test_cannot_deactivate_or_reactivate_twice(self):
        with self.assertRaises(ValidationError):
            reactivate_teacher(self.teacher)
        deactivate_teacher(self.teacher, by=self.admin, reason='x')
        self.teacher.refresh_from_db()
        with self.assertRaises(ValidationError):
            deactivate_teacher(self.teacher, by=self.admin, reason='again')

    def test_login_is_refused_and_a_running_session_is_ended(self):
        self.client.force_login(self.teacher.user)
        self.assertEqual(self.client.get(reverse('staff:teacher_archive')).status_code, 403)   # logged in, but not an admin
        deactivate_teacher(self.teacher, by=self.admin, reason='Resigned')
        self.assertFalse(self.client.login(username='t1', password='x'))                        # cannot log in any more
        self.assertEqual(self.client.get(reverse('staff:teacher_archive')).status_code, 302)    # old session is gone

    def test_admin_actions(self):
        class FakeAdmin:
            def __init__(self): self.messages = []
            def message_user(self, request, text): self.messages.append(text)
        fake, request = FakeAdmin(), type('R', (), {'user': self.admin})()
        mark_selected_former(fake, request, Teacher.objects.all())
        self.assertEqual(Teacher.objects.former().count(), 1)
        self.assertIn('1 teacher(s) marked as left', fake.messages[-1])
        reactivate_selected(fake, request, Teacher.objects.all())
        self.assertEqual(Teacher.objects.current().count(), 1)
        self.teacher.user.refresh_from_db(); self.assertTrue(self.teacher.user.is_active)


class WarningTests(TestCase):
    def test_form_teacher_staff_and_parent_warnings(self):
        t = make_teacher('ft')
        Standard = apps.get_model('curriculum', 'Standard')
        try:
            Standard.objects.create(name='JSS 1', form_teacher=t)
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f'Cannot create a Standard automatically: {exc}')
        self.assertTrue(any('Form teacher of: JSS 1' in w for w in deactivation_warnings(t)))

        t.user.is_staff = True; t.user.save()
        self.assertTrue(any('Admin (staff) rights' in w for w in deactivation_warnings(t)))

        try:
            Parent = User._meta.get_field('parent').related_model
            Student = User._meta.get_field('student').related_model
            parent = Parent.objects.create(user=t.user)
            Student.objects.create(parent=parent, student_status='active')
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f'Cannot create a Parent/Student automatically: {exc}')
        self.assertTrue(any('parent of 1 active student' in w for w in deactivation_warnings(t)))


class ActivateExistingCommandTests(TestCase):
    def test_marks_working_teachers_active_and_leaves_the_rest(self):
        working = make_teacher('working')
        disabled = make_teacher('disabled'); User.objects.filter(pk=disabled.user_id).update(is_active=False)
        nologin = Teacher.objects.create(first_name='No', last_name='Login',
                                         **{n: None for n in ('dept', 'staff_role') if n in {f.name for f in Teacher._meta.get_fields()}})
        Teacher.objects.update(active=False)                     # how legacy data looks (old default was False)
        out = StringIO()
        call_command('activate_existing_teachers', '--dry-run', stdout=out)
        self.assertEqual(Teacher.objects.current().count(), 0)    # dry run changes nothing
        call_command('activate_existing_teachers', stdout=out)
        working.refresh_from_db(); disabled.refresh_from_db(); nologin.refresh_from_db()
        self.assertTrue(working.active)
        self.assertFalse(disabled.active)
        self.assertFalse(nologin.active)
        self.assertEqual(TeacherStatusLog.objects.count(), 0)    # nothing logged, no login touched
        working.user.refresh_from_db(); self.assertTrue(working.user.is_active)
        self.assertIn('Marked 1 teacher(s) as active', out.getvalue())


class ViewTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', is_staff=True, first_name='Head', last_name='Admin', password='x')
        self.current = make_teacher('current', 'Cora', 'Current')
        self.left = make_teacher('left', 'Lena', 'Left')
        deactivate_teacher(self.left, by=self.admin, reason='Resigned', date_left=date(2026, 7, 31))
        self.plain = User.objects.create_user('plain', password='x')

    def test_only_school_admins_can_use_the_pages(self):
        urls = [reverse('staff:teacher_archive'), reverse('staff:teacher_deactivate', args=[self.current.pk]),
                reverse('staff:teacher_reactivate', args=[self.left.pk])]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)           # anonymous -> login
        self.client.force_login(self.plain)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_archive_defaults_to_former_teachers_and_can_show_current_or_everyone(self):
        self.client.force_login(self.admin)
        page = self.client.get(reverse('staff:teacher_archive')).content.decode()
        self.assertIn('Lena Left', page); self.assertNotIn('Cora Current', page)
        self.assertIn('Resigned', page); self.assertIn('Jul 31, 2026', page)
        current = self.client.get(reverse('staff:teacher_archive') + '?show=current').content.decode()
        self.assertIn('Cora Current', current); self.assertNotIn('Lena Left', current)
        everyone = self.client.get(reverse('staff:teacher_archive') + '?show=all').content.decode()
        self.assertIn('Cora Current', everyone); self.assertIn('Lena Left', everyone)
        found = self.client.get(reverse('staff:teacher_archive') + '?show=all&q=lena').content.decode()
        self.assertIn('Lena Left', found); self.assertNotIn('Cora Current', found)

    def test_deactivate_flow(self):
        self.client.force_login(self.admin)
        url = reverse('staff:teacher_deactivate', args=[self.current.pk])
        self.assertContains(self.client.get(url), 'switched off automatically')
        bad = self.client.post(url, {'date_left': (timezone.localdate() + timedelta(days=3)).isoformat(), 'reason': 'x'})
        self.assertContains(bad, 'cannot be in the future')
        self.current.refresh_from_db(); self.assertTrue(self.current.active)
        ok = self.client.post(url, {'date_left': '2026-09-30', 'reason': 'Retired'})
        self.assertRedirects(ok, reverse('staff:teacher_archive'), fetch_redirect_response=False)
        self.current.refresh_from_db(); self.current.user.refresh_from_db()
        self.assertFalse(self.current.active or self.current.user.is_active)
        self.assertEqual(TeacherStatusLog.objects.filter(changed_by=self.admin, reason='Retired').count(), 1)
        self.assertRedirects(self.client.get(url), reverse('staff:teacher_archive'), fetch_redirect_response=False)  # already left

    def test_reason_is_required_and_date_cannot_precede_employment(self):
        self.client.force_login(self.admin)
        url = reverse('staff:teacher_deactivate', args=[self.current.pk])
        self.assertContains(self.client.post(url, {'date_left': '2026-01-01', 'reason': ''}), 'This field is required')
        Teacher.objects.filter(pk=self.current.pk).update(date_employed=date(2025, 1, 1))
        self.assertContains(self.client.post(url, {'date_left': '2024-12-31', 'reason': 'x'}), 'before the date employed')

    def test_reactivate_flow(self):
        self.client.force_login(self.admin)
        url = reverse('staff:teacher_reactivate', args=[self.left.pk])
        self.assertContains(self.client.get(url), 'Reactivating switches their portal login back on')
        self.assertRedirects(self.client.post(url), reverse('staff:teacher_archive') + '?show=current',
                             fetch_redirect_response=False)
        self.left.refresh_from_db(); self.left.user.refresh_from_db()
        self.assertTrue(self.left.active and self.left.user.is_active)

    def test_admins_cannot_change_their_own_status(self):
        mine = Teacher.objects.create(user=self.admin, first_name='Head', last_name='Admin',
                                      **{n: None for n in ('dept', 'staff_role') if n in {f.name for f in Teacher._meta.get_fields()}})
        self.client.force_login(self.admin)
        r = self.client.post(reverse('staff:teacher_deactivate', args=[mine.pk]), {'date_left': '2026-09-30', 'reason': 'x'})
        self.assertRedirects(r, reverse('staff:teacher_archive'), fetch_redirect_response=False)
        mine.refresh_from_db(); self.assertTrue(mine.active)

    def test_teacher_without_a_login_can_still_be_archived(self):
        names = {f.name for f in Teacher._meta.get_fields()}
        orphan = Teacher.objects.create(first_name='Old', last_name='Timer', **{n: None for n in ('dept', 'staff_role') if n in names})
        deactivate_teacher(orphan, by=self.admin, reason='Retired')
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('staff:teacher_archive')), 'Old Timer')