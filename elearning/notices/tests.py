import unittest
from datetime import timedelta
from io import StringIO
from unittest import mock

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.template import engines
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from . import services
from .models import Notification

User = get_user_model()


def make_standard():
    Standard = apps.get_model('curriculum', 'Standard')
    try:
        return Standard.objects.first() or Standard.objects.create(name='JSS 1', slug='jss-1')
    except Exception as exc:  # pragma: no cover
        raise unittest.SkipTest(f'Cannot create a curriculum.Standard automatically: {exc}')


def make_student(user, standard, status='active'):
    Student = apps.get_model('students', 'Student')
    try:
        return Student.objects.create(user=user, current_class=standard, student_status=status)
    except Exception as exc:  # pragma: no cover
        raise unittest.SkipTest(f'Cannot create a students.Student automatically: {exc}')


def make_lesson(standard, creator):
    ELearningSubject = apps.get_model('elearning', 'ELearningSubject')
    Lesson = apps.get_model('elearning', 'Lesson')
    subject = ELearningSubject.objects.create(subject_id='MATH-1', name='Mathematics', standard=standard)
    return Lesson.objects.create(lesson_id='L1', standard=standard, subject=subject, name='Fractions',
                                 position=1, created_by=creator)


class NotifyServiceTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('a', password='x')
        self.b = User.objects.create_user('b', password='x')
        self.gone = User.objects.create_user('gone', password='x', is_active=False)

    def test_creates_one_per_distinct_active_recipient(self):
        n = services.notify([self.a, self.b, self.a, self.gone, None], 'general', 'Hello', 'Body', url='/x/')
        self.assertEqual(n, 2)
        self.assertEqual(Notification.objects.filter(recipient=self.a).count(), 1)

    def test_dedupe_key_prevents_repeats(self):
        services.notify([self.a], 'general', 'T', dedupe_key='k1')
        self.assertEqual(services.notify([self.a, self.b], 'general', 'T', dedupe_key='k1'), 1)  # only b is new
        self.assertEqual(Notification.objects.filter(dedupe_key='k1').count(), 2)

    def test_only_internal_urls_are_kept(self):
        for bad in ('//evil.com', 'https://evil.com', 'javascript:alert(1)', '\\evil'):
            self.assertEqual(services.safe_url(bad), '', bad)
        self.assertEqual(services.safe_url('/elearning/a/b/#homework-section'), '/elearning/a/b/#homework-section')

    def test_long_text_is_trimmed_and_failures_never_raise(self):
        services.notify([self.a], 'general', 'T' * 500, 'M' * 900)
        n = Notification.objects.get()
        self.assertEqual((len(n.title), len(n.message)), (120, 255))
        self.assertEqual(services.notify(None, 'general', 'x'), 0)   # bad input is swallowed, not raised


class RecipientTests(TestCase):
    def test_only_active_students_of_that_class_are_recipients(self):
        std = make_standard()
        Standard = apps.get_model('curriculum', 'Standard')
        other = Standard.objects.create(name='JSS 2', slug='jss-2')
        mine = User.objects.create_user('mine', password='x'); make_student(mine, std)
        suspended = User.objects.create_user('susp', password='x'); make_student(suspended, std, 'suspended')
        elsewhere = User.objects.create_user('else', password='x'); make_student(elsewhere, other)
        got = set(services.students_of_class(std).values_list('username', flat=True))
        self.assertEqual(got, {'mine'})

    def test_reviewers(self):
        User.objects.create_user('t', password='x'); s = User.objects.create_user('s', is_staff=True, password='x')
        boss = User.objects.create_superuser('boss', 'b@x.com', 'x')
        self.assertEqual(set(services.reviewers().values_list('username', flat=True)), {'s', 'boss'})
        self.assertEqual(set(services.reviewers(exclude=boss).values_list('username', flat=True)), {'s'})


class TriggerTests(TestCase):
    """New lesson / new assignment / graded work notify the right people (recipients are mocked here
    so the wiring is tested without needing a full Student record)."""

    def setUp(self):
        self.std = make_standard()
        self.teacher = User.objects.create_user('teach', password='x')
        self.pupil = User.objects.create_user('pupil', password='x')
        self.patch = mock.patch.object(services, 'students_of_class',
                                       side_effect=lambda std: User.objects.filter(pk=self.pupil.pk))
        self.patch.start(); self.addCleanup(self.patch.stop)

    def test_new_lesson_notifies_the_class(self):
        with self.captureOnCommitCallbacks(execute=True):
            lesson = make_lesson(self.std, self.teacher)
        n = Notification.objects.get(recipient=self.pupil)
        self.assertEqual((n.category, n.title), ('lesson', 'New lesson available'))
        self.assertEqual(n.message, 'Mathematics: Fractions')
        self.assertTrue(n.url.startswith('/elearning/') and lesson.slug in n.url)
        # saving the lesson again (an edit) must not notify again
        with self.captureOnCommitCallbacks(execute=True):
            lesson.name = 'Fractions 2'; lesson.save()
        self.assertEqual(Notification.objects.count(), 1)

    def test_new_assignment_notifies_with_due_date_and_anchor(self):
        with self.captureOnCommitCallbacks(execute=True):
            lesson = make_lesson(self.std, self.teacher)
        Notification.objects.all().delete()
        Assignment = apps.get_model('elearning', 'Assignment')
        with self.captureOnCommitCallbacks(execute=True):
            Assignment.objects.create(lesson=lesson, title='Worksheet 1', created_by=self.teacher,
                                      due_date=timezone.now() + timedelta(days=2))
        n = Notification.objects.get(recipient=self.pupil)
        self.assertEqual(n.title, 'New assignment: Worksheet 1')
        self.assertIn('Due ', n.message)
        self.assertTrue(n.url.endswith('#homework-section'))

    def test_grading_notifies_the_student_once_per_score(self):
        student = make_student(self.pupil, self.std)
        Assignment = apps.get_model('elearning', 'Assignment')
        Submission = apps.get_model('elearning', 'AssignmentSubmission')
        with self.captureOnCommitCallbacks(execute=True):
            lesson = make_lesson(self.std, self.teacher)
            a = Assignment.objects.create(lesson=lesson, title='HW', created_by=self.teacher)
        Notification.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            sub = Submission.objects.create(assignment=a, student=student, submission_link='https://x.com/a')
        self.assertEqual(Notification.objects.count(), 0)            # submitting is not grading
        with self.captureOnCommitCallbacks(execute=True):
            sub.score = 85; sub.save()
        n = Notification.objects.get()
        self.assertEqual((n.category, n.recipient, n.message), ('grade', self.pupil, 'You scored 85/100.'))
        with self.captureOnCommitCallbacks(execute=True):
            sub.teacher_feedback = 'Well done'; sub.save()           # same score -> nothing new
        self.assertEqual(Notification.objects.count(), 1)
        with self.captureOnCommitCallbacks(execute=True):
            sub.score = 90; sub.save()                               # corrected score -> told again
        self.assertEqual(Notification.objects.count(), 2)


class ReminderCommandTests(TestCase):
    def test_reminds_only_students_who_have_not_submitted_and_only_once(self):
        std = make_standard()
        teacher = User.objects.create_user('teach', password='x')
        done = User.objects.create_user('done', password='x'); s_done = make_student(done, std)
        late = User.objects.create_user('late', password='x'); make_student(late, std)
        with self.captureOnCommitCallbacks(execute=True):
            lesson = make_lesson(std, teacher)
        Assignment = apps.get_model('elearning', 'Assignment')
        a = Assignment.objects.create(lesson=lesson, title='HW', created_by=teacher,
                                      due_date=timezone.now() + timedelta(hours=5))
        Assignment.objects.create(lesson=lesson, title='Far away', created_by=teacher,
                                  due_date=timezone.now() + timedelta(days=9))
        apps.get_model('elearning', 'AssignmentSubmission').objects.create(
            assignment=a, student=s_done, submission_link='https://x.com/a')
        Notification.objects.all().delete()

        call_command('send_assignment_reminders', stdout=StringIO())
        got = Notification.objects.values_list('recipient__username', 'title')
        self.assertEqual(list(got), [('late', 'Due soon: HW')])
        call_command('send_assignment_reminders', stdout=StringIO())   # run again -> no repeat
        self.assertEqual(Notification.objects.count(), 1)


class PruneCommandTests(TestCase):
    def test_deletes_only_old_read_notifications(self):
        u = User.objects.create_user('u', password='x')
        old_read = Notification.objects.create(recipient=u, title='old read', is_read=True)
        old_unread = Notification.objects.create(recipient=u, title='old unread')
        fresh_read = Notification.objects.create(recipient=u, title='fresh read', is_read=True)
        Notification.objects.filter(pk__in=[old_read.pk, old_unread.pk]).update(
            created_at=timezone.now() - timedelta(days=200))
        call_command('prune_notifications', stdout=StringIO())
        self.assertEqual(set(Notification.objects.values_list('title', flat=True)), {'old unread', 'fresh read'})


class NotificationViewTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user('u', password='x')
        self.other = User.objects.create_user('o', password='x')
        self.n = Notification.objects.create(recipient=self.u, title='Hi', url='/elearning/x/')
        self.theirs = Notification.objects.create(recipient=self.other, title='Secret')

    def test_login_required(self):
        self.assertEqual(self.client.get(reverse('notices:list')).status_code, 302)

    def test_list_shows_only_my_notifications_and_filters_unread(self):
        self.client.force_login(self.u)
        page = self.client.get(reverse('notices:list'))
        self.assertContains(page, 'Hi'); self.assertNotContains(page, 'Secret')
        self.n.mark_read()
        self.assertNotContains(self.client.get(reverse('notices:list') + '?filter=unread'), 'Hi')

    def test_open_marks_read_and_redirects_but_not_for_someone_elses(self):
        self.client.force_login(self.u)
        r = self.client.get(reverse('notices:open', args=[self.n.pk]))
        self.assertRedirects(r, '/elearning/x/', fetch_redirect_response=False)
        self.n.refresh_from_db(); self.assertTrue(self.n.is_read)
        self.assertEqual(self.client.get(reverse('notices:open', args=[self.theirs.pk])).status_code, 404)

    def test_stored_external_url_is_never_followed(self):
        Notification.objects.filter(pk=self.n.pk).update(url='https://evil.com')
        self.client.force_login(self.u)
        r = self.client.get(reverse('notices:open', args=[self.n.pk]))
        self.assertRedirects(r, reverse('notices:list'), fetch_redirect_response=False)

    def test_mark_read_and_all_read_are_post_only_and_scoped(self):
        self.client.force_login(self.u)
        Notification.objects.create(recipient=self.u, title='Second')
        self.assertEqual(self.client.get(reverse('notices:read_all')).status_code, 405)
        self.client.post(reverse('notices:read_all'), {'next': 'https://evil.com/'})
        self.assertEqual(Notification.objects.filter(recipient=self.u, is_read=False).count(), 0)
        self.assertEqual(Notification.objects.get(pk=self.theirs.pk).is_read, False)   # others untouched
        self.assertEqual(self.client.post(reverse('notices:read', args=[self.theirs.pk])).status_code, 404)


class BellTagTests(TestCase):
    def render(self, user, source='{% load notice_tags %}{% notice_bell %}'):
        request = RequestFactory().get('/somewhere/'); request.user = user
        return engines['django'].from_string(source).render({'user': user}, request)

    def test_bell_is_a_theme_matched_list_item_with_unread_count(self):
        u = User.objects.create_user('u', password='x')
        Notification.objects.create(recipient=u, title='Fresh one')
        Notification.objects.create(recipient=u, title='Old one', is_read=True)
        html = self.render(u)
        self.assertTrue(html.strip().startswith('<li class="nav-item dropdown notification_dropdown">'))
        self.assertIn('data-bs-toggle="dropdown"', html)
        self.assertIn('Fresh one', html); self.assertIn('csrfmiddlewaretoken', html)
        self.assertRegex(html, r'rounded-circle">1<')
        self.assertIn('fa-graduation-cap', html)
        self.assertIn('fa-bell', self.render(u, '{% load notice_tags %}{% notice_bell icon="fa-bell" %}'))

    def test_nothing_is_rendered_for_anonymous_users(self):
        anon = type('A', (), {'is_authenticated': False})()
        self.assertEqual(self.render(anon).strip(), '')

    def test_a_failure_never_breaks_the_page(self):
        u = User.objects.create_user('u', password='x')
        with mock.patch.object(services, 'unread_count', side_effect=RuntimeError('table missing')):
            self.assertEqual(self.render(u).strip(), '')